import io
import os
from decimal import Decimal
from datetime import date
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from core.i18n import prepare_arabic_text_for_pdf, format_currency
from academy.models import Subject
from finance.models import Payment, Expense, ExpenseCategory

NAVY = colors.HexColor("#001B57")
GOLD = colors.HexColor("#B45309")
GREEN = colors.HexColor("#047857")
RED = colors.HexColor("#B91C1C")
LIGHT_BLUE = colors.HexColor("#EFF6FF")
LIGHT_GREEN = colors.HexColor("#F0FDF4")
LIGHT_RED = colors.HexColor("#FEF2F2")
GRAY_BG = colors.HexColor("#F8FAFC")
BORDER_COLOR = colors.HexColor("#CBD5E1")
DARK_TEXT = colors.HexColor("#0F172A")

_FONTS_INITIALIZED = False

def init_fonts():
    global _FONTS_INITIALIZED
    if _FONTS_INITIALIZED:
        return
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    font_candidates = [
        ("Amiri-Bold", os.path.join(base_dir, "static", "fonts", "Amiri-Bold.ttf")),
        ("Amiri-Regular", os.path.join(base_dir, "static", "fonts", "Amiri-Regular.ttf")),
        ("Amiri", os.path.join(base_dir, "static", "fonts", "Amiri-Regular.ttf")),
        ("Amiri-Bold-Static", os.path.join(base_dir, "staticfiles", "fonts", "Amiri-Bold.ttf")),
        ("Amiri-Regular-Static", os.path.join(base_dir, "staticfiles", "fonts", "Amiri-Regular.ttf")),
    ]
    for font_name, font_path in font_candidates:
        if os.path.exists(font_path):
            try:
                pdfmetrics.registerFont(TTFont(font_name, font_path))
            except Exception:
                pass
    _FONTS_INITIALIZED = True


def get_preferred_font(lang="fr"):
    init_fonts()
    registered = pdfmetrics.getRegisteredFontNames()
    if lang in ["ar", "bilingual"]:
        for fname in ["Amiri-Bold", "Amiri-Bold-Static", "Amiri", "Amiri-Regular"]:
            if fname in registered:
                return fname
    for fname in ["Amiri", "Amiri-Regular", "Amiri-Regular-Static", "Helvetica"]:
        if fname in registered:
            return fname
    return "Helvetica"


def generate_annual_report_pdf(closing, lang="fr"):
    """
    Génère le Rapport Financier Officiel de l'Assemblée Générale (PDF A4 haute qualité)
    pour l'Association جمعية الشطرنج القاسمي et Genius Chess Academy.
    Prend en charge le français, l'arabe et le bilingue.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=14 * mm,
        rightMargin=14 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm
    )

    init_fonts()
    font_family = get_preferred_font(lang)
    styles = getSampleStyleSheet()

    # Styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName=font_family,
        fontSize=15,
        leading=19,
        textColor=NAVY,
        alignment=1, # Center
        spaceAfter=3
    )

    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName=font_family,
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#64748B"),
        alignment=1,
        spaceAfter=10
    )

    h2_style = ParagraphStyle(
        'H2Style',
        parent=styles['Normal'],
        fontName=font_family,
        fontSize=11,
        leading=14,
        textColor=NAVY,
        spaceBefore=8,
        spaceAfter=4
    )

    cell_style = ParagraphStyle(
        'CellStyle',
        parent=styles['Normal'],
        fontName=font_family,
        fontSize=8.5,
        leading=11,
        textColor=DARK_TEXT
    )

    cell_bold_style = ParagraphStyle(
        'CellBoldStyle',
        parent=styles['Normal'],
        fontName=font_family,
        fontSize=8.5,
        leading=11,
        textColor=NAVY
    )

    elements = []

    # 1. En-Tête Officiel Association & Académie
    if lang == "ar":
        header_text = prepare_arabic_text_for_pdf("المملكة المغربية — جمعية الشطرنج القاسمي — أكاديمية الشطرنج")
        doc_title = prepare_arabic_text_for_pdf(f"التقرير المالي الرسمي — {closing.get_period_label('ar')}")
        sub_text = prepare_arabic_text_for_pdf("سيدي قاسم • www.geniuschess.ma • هاتف: 06 060424142")
    elif lang == "bilingual":
        header_text = "ROYAUME DU MAROC — جمعية الشطرنج القاسمي — GENIUS CHESS ACADEMY"
        doc_title = f"RAPPORT FINANCIER OFFICIEL — {closing.get_period_label('fr')} / التقرير المالي الرسمي"
        sub_text = "Sidi Kacem • www.geniuschess.ma • Tél: 06 060424142"
    else: # fr
        header_text = "ROYAUME DU MAROC — جمعية الشطرنج القاسمي — GENIUS CHESS ACADEMY"
        doc_title = f"RAPPORT FINANCIER OFFICIEL — {closing.get_period_label('fr').upper()}"
        sub_text = "Sidi Kacem • www.geniuschess.ma • Tél: 06 060424142"

    elements.append(Paragraph(f"<b>{header_text}</b>", title_style))
    elements.append(Paragraph(doc_title, ParagraphStyle('MainTitle', parent=title_style, fontSize=13, textColor=GOLD)))
    elements.append(Paragraph(sub_text, subtitle_style))
    elements.append(HRFlowable(width="100%", thickness=1.5, color=NAVY, spaceAfter=8))

    # Métadonnées du Rapport
    close_date_str = closing.closing_date.strftime("%d/%m/%Y") if closing.closing_date else date.today().strftime("%d/%m/%Y")
    status_label = dict(closing.STATUS_CHOICES).get(closing.status, closing.status)
    
    meta_data = [
        [
            Paragraph(f"<b>Période / Exercice :</b> {closing.get_period_label('fr')}", cell_style),
            Paragraph(f"<b>Date de Clôture :</b> {close_date_str}", cell_style),
            Paragraph(f"<b>Statut :</b> {status_label}", cell_style),
            Paragraph(f"<b>Réf :</b> CLOT-{closing.year}-{closing.id:03d}", cell_style)
        ]
    ]
    meta_table = Table(meta_data, colWidths=[50*mm, 45*mm, 45*mm, 42*mm])
    meta_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), GRAY_BG),
        ('BOX', (0,0), (-1,-1), 0.5, BORDER_COLOR),
        ('INNERGRID', (0,0), (-1,-1), 0.5, BORDER_COLOR),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    elements.append(meta_table)
    elements.append(Spacer(1, 8))

    # 2. Section Synthèse Globale & Résultat Net
    sec1_title = "1. SYNTHÈSE BUDGÉTAIRE ET RÉSULTAT NET / الخلاصة المالية" if lang != "ar" else prepare_arabic_text_for_pdf("1. الخلاصة المالية والنتيجة الصافية")
    elements.append(Paragraph(f"<b>{sec1_title}</b>", h2_style))

    is_positive = closing.net_result >= Decimal('0.00')
    net_label = "EXCÉDENT NET D'EXPLOITATION" if is_positive else "DÉFICIT NET D'EXPLOITATION"
    if lang == "ar":
        net_label = prepare_arabic_text_for_pdf("فائض مالي إيجابي" if is_positive else "عجز مالي مؤقت")

    kpi_data = [
        [
            Paragraph("<b>TOTAL RECETTES ENCAISSÉES</b><br/><font size=7 color='#64748B'>Cotisations & droits</font>", cell_style),
            Paragraph("<b>TOTAL DÉPENSES & CHARGES</b><br/><font size=7 color='#64748B'>Coûts d'exploitation</font>", cell_style),
            Paragraph(f"<b>{net_label}</b><br/><font size=7 color='#64748B'>Résultat = Recettes - Dépenses</font>", cell_style)
        ],
        [
            Paragraph(f"<font size=13 color='#16A34A'><b>{closing.total_collected:,.2f} DH</b></font>", cell_style),
            Paragraph(f"<font size=13 color='#DC2626'><b>{closing.total_expense:,.2f} DH</b></font>", cell_style),
            Paragraph(f"<font size=13 color='{'#047857' if is_positive else '#B91C1C'}'><b>{closing.net_result:,.2f} DH</b></font>", cell_style)
        ]
    ]
    kpi_table = Table(kpi_data, colWidths=[61*mm, 61*mm, 60*mm])
    kpi_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (0,-1), LIGHT_GREEN),
        ('BACKGROUND', (1,0), (1,-1), LIGHT_RED),
        ('BACKGROUND', (2,0), (2,-1), LIGHT_GREEN if is_positive else LIGHT_RED),
        ('BOX', (0,0), (-1,-1), 1, BORDER_COLOR),
        ('INNERGRID', (0,0), (-1,-1), 0.5, BORDER_COLOR),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
    ]))
    elements.append(kpi_table)
    elements.append(Spacer(1, 10))

    # 3. Section Détail des Recettes par Activité
    sec2_title = "2. VENTILATION DES RECETTES PAR ACTIVITÉ / تفصيل المداخيل" if lang != "ar" else prepare_arabic_text_for_pdf("2. تفصيل المداخيل حسب الأنشطة")
    elements.append(Paragraph(f"<b>{sec2_title}</b>", h2_style))

    # Calcul des paiements de la période par activité
    p_qs = Payment.objects.all()
    if closing.period_type == 'year':
        p_qs = p_qs.filter(payment_date__year=closing.year)
    else:
        p_qs = p_qs.filter(payment_date__year=closing.year, payment_date__month=closing.month)

    subjects = Subject.objects.all()
    rev_rows = [
        [
            Paragraph("<b>Activité / Source de Recette</b>", cell_bold_style),
            Paragraph("<b>Nombre de Règlements</b>", cell_bold_style),
            Paragraph("<b>Part (%)</b>", cell_bold_style),
            Paragraph("<b>Montant Encaissé (DH)</b>", cell_bold_style)
        ]
    ]

    total_rev_check = closing.total_collected if closing.total_collected > 0 else Decimal('1.00')

    for sub in subjects:
        sub_payments = p_qs.filter(invoice__group__subject=sub)
        from django.db.models import Sum
        sub_amt = sub_payments.aggregate(t=Sum('amount'))['t'] or Decimal('0.00')
        sub_cnt = sub_payments.count()
        if sub_amt > 0 or sub_cnt > 0:
            pct = round(float((sub_amt / total_rev_check) * 100), 1)
            sub_name = sub.get_name(lang) if hasattr(sub, 'get_name') else sub.name_fr
            rev_rows.append([
                Paragraph(f"• {sub_name}", cell_style),
                Paragraph(str(sub_cnt), cell_style),
                Paragraph(f"{pct}%", cell_style),
                Paragraph(f"{sub_amt:,.2f} DH", cell_bold_style)
            ])

    # Autres règlements non rattachés directement
    other_payments = p_qs.filter(invoice__group__isnull=True)
    other_amt = other_payments.aggregate(t=Sum('amount'))['t'] or Decimal('0.00')
    if other_amt > 0:
        pct = round(float((other_amt / total_rev_check) * 100), 1)
        rev_rows.append([
            Paragraph("• Autres cotisations / Droits", cell_style),
            Paragraph(str(other_payments.count()), cell_style),
            Paragraph(f"{pct}%", cell_style),
            Paragraph(f"{other_amt:,.2f} DH", cell_bold_style)
        ])

    # Total Recettes Ligne
    rev_rows.append([
        Paragraph("<b>TOTAL GÉNÉRAL DES RECETTES</b>", cell_bold_style),
        Paragraph(f"<b>{p_qs.count()}</b>", cell_bold_style),
        Paragraph("<b>100%</b>", cell_bold_style),
        Paragraph(f"<b>{closing.total_collected:,.2f} DH</b>", cell_bold_style)
    ])

    rev_table = Table(rev_rows, colWidths=[82*mm, 35*mm, 25*mm, 40*mm])
    rev_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), NAVY),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('GRID', (0,0), (-1,-1), 0.5, BORDER_COLOR),
        ('ROWBACKGROUNDS', (0,1), (-1,-2), [colors.white, GRAY_BG]),
        ('BACKGROUND', (0,-1), (-1,-1), LIGHT_GREEN),
        ('ALIGN', (1,0), (-1,-1), 'RIGHT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 3.5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3.5),
    ]))
    for r_idx in range(len(rev_rows)):
        rev_table.setStyle(TableStyle([('TEXTCOLOR', (0,0), (-1,0), colors.white)]))
    elements.append(rev_table)
    elements.append(Spacer(1, 10))

    # 4. Section Détail des Dépenses par Catégorie
    sec3_title = "3. VENTILATION DES DÉPENSES & CHARGES D'EXPLOITATION / تفصيل المصاريف" if lang != "ar" else prepare_arabic_text_for_pdf("3. تفصيل المصاريف والتكاليف")
    elements.append(Paragraph(f"<b>{sec3_title}</b>", h2_style))

    e_qs = Expense.objects.all()
    if closing.period_type == 'year':
        e_qs = e_qs.filter(expense_date__year=closing.year)
    else:
        e_qs = e_qs.filter(expense_date__year=closing.year, expense_date__month=closing.month)

    categories = ExpenseCategory.objects.all()
    exp_rows = [
        [
            Paragraph("<b>Poste de Dépense / Catégorie</b>", cell_bold_style),
            Paragraph("<b>Nombre d'Actes</b>", cell_bold_style),
            Paragraph("<b>Part (%)</b>", cell_bold_style),
            Paragraph("<b>Montant Payé (DH)</b>", cell_bold_style)
        ]
    ]

    total_exp_check = closing.total_expense if closing.total_expense > 0 else Decimal('1.00')

    for cat in categories:
        cat_expenses = e_qs.filter(category=cat)
        cat_amt = cat_expenses.aggregate(t=Sum('amount'))['t'] or Decimal('0.00')
        cat_cnt = cat_expenses.count()
        if cat_amt > 0 or cat_cnt > 0:
            pct = round(float((cat_amt / total_exp_check) * 100), 1)
            cat_name = cat.get_name(lang)
            exp_rows.append([
                Paragraph(f"• {cat.icon} {cat_name}", cell_style),
                Paragraph(str(cat_cnt), cell_style),
                Paragraph(f"{pct}%", cell_style),
                Paragraph(f"{cat_amt:,.2f} DH", cell_bold_style)
            ])

    exp_rows.append([
        Paragraph("<b>TOTAL GÉNÉRAL DES CHARGES</b>", cell_bold_style),
        Paragraph(f"<b>{e_qs.count()}</b>", cell_bold_style),
        Paragraph("<b>100%</b>", cell_bold_style),
        Paragraph(f"<b>{closing.total_expense:,.2f} DH</b>", cell_bold_style)
    ])

    exp_table = Table(exp_rows, colWidths=[82*mm, 35*mm, 25*mm, 40*mm])
    exp_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), NAVY),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('GRID', (0,0), (-1,-1), 0.5, BORDER_COLOR),
        ('ROWBACKGROUNDS', (0,1), (-1,-2), [colors.white, GRAY_BG]),
        ('BACKGROUND', (0,-1), (-1,-1), LIGHT_RED),
        ('ALIGN', (1,0), (-1,-1), 'RIGHT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 3.5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3.5),
    ]))
    elements.append(exp_table)
    elements.append(Spacer(1, 10))

    # 5. Section Rapprochement de Trésorerie (Caisse & Banque)
    sec4_title = "4. RAPPROCHEMENT DE TRÉSORERIE ET DISPONIBILITÉS LIQUIDES / وضعية الخزينة" if lang != "ar" else prepare_arabic_text_for_pdf("4. وضعية الخزينة والسيولة المالية")
    elements.append(Paragraph(f"<b>{sec4_title}</b>", h2_style))

    phys_cash_str = f"{closing.physical_cash_counted:,.2f} DH" if closing.physical_cash_counted is not None else "Non renseigné"
    bank_stmt_str = f"{closing.bank_statement_balance:,.2f} DH" if closing.bank_statement_balance is not None else "Non renseigné"
    total_liquidity = (closing.physical_cash_counted or closing.theoretical_cash) + (closing.bank_statement_balance or closing.theoretical_bank)

    tres_data = [
        [
            Paragraph("<b>Compte / Caisse</b>", cell_bold_style),
            Paragraph("<b>Solde Initial</b>", cell_bold_style),
            Paragraph("<b>Encaissements (+)</b>", cell_bold_style),
            Paragraph("<b>Décaissements (-)</b>", cell_bold_style),
            Paragraph("<b>Solde Théorique</b>", cell_bold_style),
            Paragraph("<b>Solde Réel Constaté</b>", cell_bold_style)
        ],
        [
            Paragraph("<b>Caisse Espèces (Coffre)</b>", cell_style),
            Paragraph(f"{closing.initial_cash_balance:,.2f} DH", cell_style),
            Paragraph(f"+{closing.total_collected_cash:,.2f} DH", cell_style),
            Paragraph(f"-{closing.total_expense_cash:,.2f} DH", cell_style),
            Paragraph(f"<b>{closing.theoretical_cash:,.2f} DH</b>", cell_style),
            Paragraph(f"<b>{phys_cash_str}</b>", cell_bold_style)
        ],
        [
            Paragraph("<b>Compte Bancaire</b>", cell_style),
            Paragraph(f"{closing.initial_bank_balance:,.2f} DH", cell_style),
            Paragraph(f"+{closing.total_collected_bank:,.2f} DH", cell_style),
            Paragraph(f"-{closing.total_expense_bank:,.2f} DH", cell_style),
            Paragraph(f"<b>{closing.theoretical_bank:,.2f} DH</b>", cell_style),
            Paragraph(f"<b>{bank_stmt_str}</b>", cell_bold_style)
        ],
        [
            Paragraph("<b>TOTAL DISPONIBILITÉS</b>", cell_bold_style),
            Paragraph(f"<b>{(closing.initial_cash_balance + closing.initial_bank_balance):,.2f} DH</b>", cell_bold_style),
            Paragraph(f"<b>+{closing.total_collected:,.2f} DH</b>", cell_bold_style),
            Paragraph(f"<b>-{closing.total_expense:,.2f} DH</b>", cell_bold_style),
            Paragraph(f"<b>{(closing.theoretical_cash + closing.theoretical_bank):,.2f} DH</b>", cell_bold_style),
            Paragraph(f"<font color='#047857'><b>{total_liquidity:,.2f} DH</b></font>", cell_bold_style)
        ]
    ]

    tres_table = Table(tres_data, colWidths=[42*mm, 28*mm, 28*mm, 28*mm, 28*mm, 28*mm])
    tres_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), GRAY_BG),
        ('GRID', (0,0), (-1,-1), 0.5, BORDER_COLOR),
        ('BACKGROUND', (0,-1), (-1,-1), LIGHT_BLUE),
        ('ALIGN', (1,0), (-1,-1), 'RIGHT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 3.5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3.5),
    ]))
    elements.append(tres_table)
    elements.append(Spacer(1, 12))

    # 6. Emplacement officiel Signatures & Cachet (Le Trésorier & Le Président)
    sig_data = [
        [
            Paragraph("<b>LE TRÉSORIER GÉNÉRAL</b><br/><font size=7 color='#64748B'>أمين المال العام للجمعية</font>", cell_style),
            Paragraph("<b>LE PRÉSIDENT DE L'ASSOCIATION</b><br/><font size=7 color='#64748B'>رئيس الجمعية</font>", cell_style)
        ],
        [
            Paragraph("<br/><br/><br/><i>Date et Signature :</i><br/>___________________________", cell_style),
            Paragraph("<br/><br/><br/><i>Date, Signature et Cachet :</i><br/>___________________________", cell_style)
        ]
    ]
    sig_table = Table(sig_data, colWidths=[91*mm, 91*mm])
    sig_table.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 1, BORDER_COLOR),
        ('INNERGRID', (0,0), (-1,-1), 0.5, BORDER_COLOR),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 10),
    ]))
    elements.append(KeepTogether([sig_table]))

    doc.build(elements)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes
