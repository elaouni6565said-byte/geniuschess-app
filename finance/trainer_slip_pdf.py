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


def generate_trainer_slip_pdf(payout, lang="fr"):
    """
    Génère le Bulletin de Règlement d'Honoraires officiel d'un formateur au format PDF A4.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=14*mm,
        rightMargin=14*mm,
        topMargin=12*mm,
        bottomMargin=12*mm,
    )

    init_fonts()
    font_family = get_preferred_font(lang)
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName=font_family,
        fontSize=14,
        leading=18,
        textColor=NAVY,
        alignment=1, # Center
        spaceAfter=3
    )

    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName=font_family,
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor("#64748B"),
        alignment=1,
        spaceAfter=8
    )

    h2_style = ParagraphStyle(
        'H2Style',
        parent=styles['Normal'],
        fontName=font_family,
        fontSize=10.5,
        leading=14,
        textColor=NAVY,
        spaceBefore=6,
        spaceAfter=3
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

    # 1. En-Tête Officiel
    if lang == "ar":
        header_text = prepare_arabic_text_for_pdf("المملكة المغربية — جمعية الشطرنج القاسمي — أكاديمية الشطرنج")
        doc_title = prepare_arabic_text_for_pdf(f"بيان صرف المستحقات والتعويضات — {payout.get_period_label('ar')}")
        sub_text = prepare_arabic_text_for_pdf("سيدي قاسم • www.geniuschess.ma • هاتف: 06 060424142")
    elif lang == "bilingual":
        header_text = "ROYAUME DU MAROC — جمعية الشطرنج القاسمي — GENIUS CHESS ACADEMY"
        doc_title = f"BULLETIN DE RÈGLEMENT D'HONORAIRES — {payout.get_period_label('fr')} / بيان صرف المستحقات"
        sub_text = "Sidi Kacem • www.geniuschess.ma • Tél: 06 060424142"
    else: # fr
        header_text = "ROYAUME DU MAROC — جمعية الشطرنج القاسمي — GENIUS CHESS ACADEMY"
        doc_title = f"BULLETIN DE RÈGLEMENT D'HONORAIRES — {payout.get_period_label('fr').upper()}"
        sub_text = "Sidi Kacem • www.geniuschess.ma • Tél: 06 060424142"

    elements.append(Paragraph(f"<b>{header_text}</b>", title_style))
    elements.append(Paragraph(doc_title, ParagraphStyle('MainTitle', parent=title_style, fontSize=12.5, textColor=GOLD)))
    elements.append(Paragraph(sub_text, subtitle_style))
    elements.append(HRFlowable(width="100%", thickness=1.5, color=NAVY, spaceAfter=8))

    # 2. Cartouche Métadonnées & Identification Formateur
    pay_date_str = payout.payment_date.strftime("%d/%m/%Y") if payout.payment_date else "En attente / قيد المعالجة"
    status_label = payout.get_status_label(lang)
    trainer = payout.trainer

    cin_val = trainer.cin if trainer.cin else "Non renseigné"
    phone_val = trainer.phone if trainer.phone else "Non renseigné"
    rib_val = f"{trainer.bank_name} - {trainer.bank_rib}" if trainer.bank_rib else "Règlement en Espèces / نقدًا"

    info_data = [
        [
            Paragraph("<b>BÉNÉFICIAIRE / المستفيد :</b>", cell_bold_style),
            Paragraph(f"<b>{trainer.get_bilingual_full_name()}</b>", cell_style),
            Paragraph("<b>RÉFÉRENCE BULLETIN :</b>", cell_bold_style),
            Paragraph(f"<b>{payout.payout_number}</b>", cell_style),
        ],
        [
            Paragraph("<b>CIN (N° Carte) :</b>", cell_bold_style),
            Paragraph(cin_val, cell_style),
            Paragraph("<b>Période concernée :</b>", cell_bold_style),
            Paragraph(payout.get_period_label(lang), cell_style),
        ],
        [
            Paragraph("<b>Discipline / Spécialité :</b>", cell_bold_style),
            Paragraph(trainer.specialty or "Échecs", cell_style),
            Paragraph("<b>Statut du règlement :</b>", cell_bold_style),
            Paragraph(f"<b>{status_label}</b>", cell_style),
        ],
        [
            Paragraph("<b>Téléphone :</b>", cell_bold_style),
            Paragraph(phone_val, cell_style),
            Paragraph("<b>Date de versement :</b>", cell_bold_style),
            Paragraph(pay_date_str, cell_style),
        ],
        [
            Paragraph("<b>Coordonnées paiement :</b>", cell_bold_style),
            Paragraph(rib_val, cell_style),
            Paragraph("<b>Mode de règlement :</b>", cell_bold_style),
            Paragraph(payout.get_method_label(lang), cell_style),
        ],
    ]

    info_table = Table(info_data, colWidths=[42*mm, 52*mm, 42*mm, 46*mm])
    info_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), GRAY_BG),
        ('BOX', (0,0), (-1,-1), 0.5, BORDER_COLOR),
        ('INNERGRID', (0,0), (-1,-1), 0.5, BORDER_COLOR),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 3.5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3.5),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 10))

    # 3. Décompte des Prestations & Calcul des Honoraires
    section_title = "DÉCOMPTE DÉTAILLÉ DES PRESTATIONS / تفاصيل المستحقات" if lang != "ar" else prepare_arabic_text_for_pdf("تفاصيل المستحقات والتعويضات")
    elements.append(Paragraph(f"<b>{section_title}</b>", h2_style))

    # Déterminer le libellé de la base
    if payout.compensation_type == 'per_session':
        base_desc = f"Séances d'encadrement assurées ({payout.sessions_count} séances × {format_currency(payout.rate_applied)})"
        calc_unit = f"{payout.sessions_count} séances"
    elif payout.compensation_type == 'per_hour':
        base_desc = f"Volume horaire d'animation ({payout.sessions_count} h × {format_currency(payout.rate_applied)})"
        calc_unit = f"{payout.sessions_count} heures"
    else: # monthly_fixed
        base_desc = "Forfait mensuel conventionné d'encadrement technique"
        calc_unit = "1 mois"

    breakdown_rows = [
        [
            Paragraph("<b>Désignation de la prestation / البيان</b>", cell_bold_style),
            Paragraph("<b>Base / Unité</b>", cell_bold_style),
            Paragraph("<b>Taux unitaire</b>", cell_bold_style),
            Paragraph("<b>Montant (DH)</b>", cell_bold_style),
        ],
        [
            Paragraph(base_desc, cell_style),
            Paragraph(calc_unit, cell_style),
            Paragraph(format_currency(payout.rate_applied) if payout.compensation_type != 'monthly_fixed' else "---", cell_style),
            Paragraph(f"<b>{format_currency(payout.base_amount)}</b>", cell_style),
        ]
    ]

    # Primes si > 0
    if payout.bonus_amount > Decimal('0.00'):
        b_desc = f"Primes & Indemnités exceptionnelles ({payout.bonus_description or 'Arbitrage / Déplacement / Performance'})"
        breakdown_rows.append([
            Paragraph(b_desc, cell_style),
            Paragraph("Prime", cell_style),
            Paragraph("---", cell_style),
            Paragraph(f"<font color='#047857'><b>+{format_currency(payout.bonus_amount)}</b></font>", cell_style),
        ])

    # Retenues si > 0
    if payout.deduction_amount > Decimal('0.00'):
        d_desc = f"Retenues & Avances sur honoraires ({payout.deduction_description or 'Acompte versé / Absence injustifiée'})"
        breakdown_rows.append([
            Paragraph(d_desc, cell_style),
            Paragraph("Déduction", cell_style),
            Paragraph("---", cell_style),
            Paragraph(f"<font color='#B91C1C'><b>-{format_currency(payout.deduction_amount)}</b></font>", cell_style),
        ])

    # Ligne NET A PAYER
    net_label = "NET À VERSER AU FORMATEUR / الصافي للأداء" if lang != "ar" else prepare_arabic_text_for_pdf("الصافي للأداء للمدرب")
    breakdown_rows.append([
        Paragraph(f"<b>{net_label}</b>", ParagraphStyle('NetLbl', parent=cell_bold_style, fontSize=9.5, textColor=NAVY)),
        Paragraph("", cell_style),
        Paragraph("", cell_style),
        Paragraph(f"<b>{format_currency(payout.net_amount)}</b>", ParagraphStyle('NetVal', parent=cell_bold_style, fontSize=10.5, textColor=GOLD)),
    ])

    breakdown_table = Table(breakdown_rows, colWidths=[92*mm, 30*mm, 30*mm, 30*mm])
    breakdown_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), LIGHT_BLUE),
        ('BOX', (0,0), (-1,-1), 0.5, BORDER_COLOR),
        ('INNERGRID', (0,0), (-1,-1), 0.5, BORDER_COLOR),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('SPAN', (0, -1), (2, -1)), # Fusionne pour le total net
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor("#FEF3C7")), # Gold light background
    ]))
    elements.append(breakdown_table)
    elements.append(Spacer(1, 8))

    # Notes et observations éventuelles
    if payout.notes:
        elements.append(Paragraph(f"<b>Observations :</b> {payout.notes}", cell_style))
        elements.append(Spacer(1, 6))

    # 4. Mention Légale d'Acquit & Décharge
    elements.append(Spacer(1, 6))
    if lang == "ar":
        decharge_text = prepare_arabic_text_for_pdf(
            "يشهد الموقع أسفله أنه توصل من جمعية الشطرنج القاسمي بالمبلغ الصافي المذكور أعلاه كأداء كامل لمستحقات التأطير عن الفترة المشار إليها، وذلك إبراءً للذمة."
        )
    else:
        decharge_text = (
            "<i>« Le bénéficiaire soussigné atteste avoir reçu de l'association جمعية الشطرنج القاسمي la somme nette susmentionnée "
            "en règlement intégral de ses honoraires et indemnités d'encadrement pour la période indiquée ci-dessus, valant reçu pour solde de tout compte. »</i>"
        )
    decharge_p = Paragraph(decharge_text, ParagraphStyle('Decharge', parent=cell_style, fontSize=7.5, leading=10, textColor=colors.HexColor("#475569")))
    decharge_table = Table([[decharge_p]], colWidths=[182*mm])
    decharge_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), GRAY_BG),
        ('BOX', (0,0), (-1,-1), 0.5, BORDER_COLOR),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
    ]))
    elements.append(decharge_table)
    elements.append(Spacer(1, 14))

    # 5. Cadres de Signature Officiels (3 colonnes)
    if lang == "ar":
        sig_trainer = prepare_arabic_text_for_pdf("توقيع وإشهاد المدرب - (قرئ وصودق عليه)")
        sig_treasurer = prepare_arabic_text_for_pdf("تأشيرة أمين المال العام (الجمعية)")
        sig_president = prepare_arabic_text_for_pdf("توقيع وخاتم رئيس الجمعية")
    else:
        sig_trainer = "<b>Le Formateur Bénéficiaire</b><br/><font size=7 color='#64748B'>(Signature précédée de la mention manuscrite<br/>« Lu et approuvé, bon pour reçu »)</font>"
        sig_treasurer = "<b>Le Trésorier Général</b><br/><font size=7 color='#64748B'>(Visa & Contrôle financier<br/>جمعية الشطرنج القاسمي)</font>"
        sig_president = "<b>Le Président de l'Association</b><br/><font size=7 color='#64748B'>(Cachet officiel & Signature<br/>GENIUS CHESS ACADEMY)</font>"

    sig_data = [
        [
            Paragraph(sig_trainer, cell_style),
            Paragraph(sig_treasurer, cell_style),
            Paragraph(sig_president, cell_style),
        ],
        [
            Paragraph("<br/><br/><br/><br/>", cell_style),
            Paragraph("<br/><br/><br/><br/>", cell_style),
            Paragraph("<br/><br/><br/><br/>", cell_style),
        ]
    ]

    sig_table = Table(sig_data, colWidths=[60*mm, 60*mm, 62*mm])
    sig_table.setStyle(TableStyle([
        ('BOX', (0,0), (0,1), 0.5, BORDER_COLOR),
        ('BOX', (1,0), (1,1), 0.5, BORDER_COLOR),
        ('BOX', (2,0), (2,1), 0.5, BORDER_COLOR),
        ('BACKGROUND', (0,0), (0,0), GRAY_BG),
        ('BACKGROUND', (1,0), (1,0), GRAY_BG),
        ('BACKGROUND', (2,0), (2,0), GRAY_BG),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))

    elements.append(KeepTogether([sig_table]))

    def add_footer(canvas, doc_obj):
        canvas.saveState()
        canvas.setFont(font_family if font_family != 'Amiri-Bold' else 'Amiri', 7.5)
        canvas.setFillColor(colors.HexColor("#94A3B8"))
        ft_text = "Genius Chess Academy • جمعية الشطرنج القاسمي • Sidi Kacem • Document comptable officiel"
        canvas.drawCentredString(A4[0] / 2.0, 7*mm, ft_text)
        canvas.restoreState()

    doc.build(elements, onFirstPage=add_footer, onLaterPages=add_footer)
    return buffer.getvalue()
