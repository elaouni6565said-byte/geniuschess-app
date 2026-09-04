content = """import io
import os
from decimal import Decimal
from reportlab.lib.pagesizes import A5, landscape
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from core.i18n import (
    prepare_arabic_text_for_pdf, format_date_localized,
    format_currency, get_translation
)

# Color Palette Genius Chess Academy
NAVY = colors.HexColor("#001B57")
BLUE = colors.HexColor("#0077CE")
ORANGE = colors.HexColor("#FF6E00")
LIGHT_BG = colors.HexColor("#F4F7FC")
DARK_GRAY = colors.HexColor("#2C3E50")
BORDER_COLOR = colors.HexColor("#CBD5E1")

# Font Registration
_FONTS_INITIALIZED = False

def init_fonts():
    global _FONTS_INITIALIZED
    if _FONTS_INITIALIZED:
        return
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    font_candidates = [
        ("Amiri", os.path.join(base_dir, "static", "fonts", "Amiri-Regular.ttf")),
        ("Cairo", os.path.join(base_dir, "static", "fonts", "Cairo-Variable.ttf")),
        ("SystemArial", "C:/Windows/Fonts/arial.ttf"),
    ]
    for font_name, font_path in font_candidates:
        if os.path.exists(font_path):
            try:
                pdfmetrics.registerFont(TTFont(font_name, font_path))
            except Exception:
                pass
    _FONTS_INITIALIZED = True


def get_preferred_font(lang):
    init_fonts()
    registered = pdfmetrics.getRegisteredFontNames()
    if lang in ("ar", "bilingual"):
        if "Amiri" in registered:
            return "Amiri"
        if "Cairo" in registered:
            return "Cairo"
        if "SystemArial" in registered:
            return "SystemArial"
    return "Helvetica"


def generate_receipt_pdf(payment, lang="fr"):
    \"\"\"
    Generates a high-quality PDF receipt.
    lang can be: 'fr', 'ar', or 'bilingual'
    \"\"\"
    init_fonts()
    buffer = io.BytesIO()

    # We use A5 in landscape orientation - standard for Moroccan school receipts
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A5),
        rightMargin=12 * mm,
        leftMargin=12 * mm,
        topMargin=10 * mm,
        bottomMargin=10 * mm,
    )

    story = []
    font_name = get_preferred_font(lang)
    styles = getSampleStyleSheet()

    # Pre-extract data
    student = payment.student
    invoice = payment.invoice
    group = invoice.group if invoice else (student.groups.first() if student.groups.exists() else None)
    subject = group.subject if group else None
    balance = invoice.get_balance() if invoice else Decimal("0.00")
    period_str = invoice.get_period_label(lang) if invoice else "Cotisation 2026"

    # Header texts
    if lang == "ar":
        title_text = prepare_arabic_text_for_pdf("وصل الأداء")
        academy_name = prepare_arabic_text_for_pdf("أكاديمية جينيوس للشطرنج")
        academy_sub = prepare_arabic_text_for_pdf("شطرنج • روبوتيك • حساب ذهني")
        contact_text = prepare_arabic_text_for_pdf("سيدي قاسم / الرباط - هاتف: 0661000000")
    elif lang == "bilingual":
        title_text = f"REÇU DE PAIEMENT / {prepare_arabic_text_for_pdf('وصل الأداء')}"
        academy_name = f"GENIUS CHESS ACADEMY / {prepare_arabic_text_for_pdf('أكاديمية جينيوس للشطرنج')}"
        academy_sub = f"Échecs • Robotique • Calcul Mental / {prepare_arabic_text_for_pdf('شطرنج • روبوتيك • حساب ذهني')}"
        contact_text = "Sidi Kacem / Rabat - Tél: 06 61 00 00 00"
    else: # fr
        title_text = "REÇU DE PAIEMENT"
        academy_name = "GENIUS CHESS ACADEMY"
        academy_sub = "Échecs • Robotique • Calcul Mental"
        contact_text = "Sidi Kacem / Rabat - Tél: 06 61 00 00 00"

    # Header banner Table
    header_data = [
        [
            Paragraph(f"<b><font size=14 color='{NAVY.hexval()}'>{academy_name}</font></b><br/>"
                      f"<font size=8 color='{BLUE.hexval()}'>{academy_sub}</font><br/>"
                      f"<font size=7 color='#666666'>{contact_text}</font>",
                      ParagraphStyle('H1', fontName=font_name, leading=12)),
            Paragraph(f"<b><font size=15 color='{ORANGE.hexval()}'>{title_text}</font></b><br/>"
                      f"<font size=9 color='{NAVY.hexval()}'>N°: <b>{payment.receipt_number}</b></font><br/>"
                      f"<font size=8 color='#555555'>{format_date_localized(payment.payment_date, lang=lang)}</font>",
                      ParagraphStyle('H2', fontName=font_name, alignment=2, leading=13)),
        ]
    ]
    header_table = Table(header_data, colWidths=[115 * mm, 75 * mm])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LINEBELOW', (0,0), (-1,-1), 1.5, NAVY),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 6 * mm))

    # Prepare labels and values
    student_disp = student.get_full_name(lang)
    if lang == "ar":
        student_disp = prepare_arabic_text_for_pdf(student_disp)
        activity_disp = prepare_arabic_text_for_pdf(subject.get_name("ar")) if subject else prepare_arabic_text_for_pdf("الشطرنج")
        group_disp = prepare_arabic_text_for_pdf(group.get_name("ar")) if group else prepare_arabic_text_for_pdf("المجموعة العامة")
        method_disp = prepare_arabic_text_for_pdf(payment.get_method_label("ar"))
        period_disp = prepare_arabic_text_for_pdf(period_str)
        lbl_student = prepare_arabic_text_for_pdf("اسم التلميذ :")
        lbl_mat = prepare_arabic_text_for_pdf("رقم التسجيل :")
        lbl_act = prepare_arabic_text_for_pdf("النشاط / المادة :")
        lbl_grp = prepare_arabic_text_for_pdf("المجموعة :")
        lbl_per = prepare_arabic_text_for_pdf("الشهر المؤدى :")
        lbl_mth = prepare_arabic_text_for_pdf("طريقة الأداء :")
        lbl_amt = prepare_arabic_text_for_pdf("المبلغ المؤدى :")
        lbl_bal = prepare_arabic_text_for_pdf("المبلغ المتبقي :")
    elif lang == "bilingual":
        student_disp = f"{student.first_name_fr} {student.last_name_fr} / {prepare_arabic_text_for_pdf(student.get_full_name('ar'))}"
        activity_disp = f"{subject.name_fr} / {prepare_arabic_text_for_pdf(subject.name_ar)}" if subject else "Échecs"
        group_disp = f"{group.name_fr} / {prepare_arabic_text_for_pdf(group.name_ar)}" if group else "GCA"
        method_disp = f"{payment.get_method_label('fr')} / {prepare_arabic_text_for_pdf(payment.get_method_label('ar'))}"
        period_disp = f"{invoice.get_period_label('fr') if invoice else '2026'}"
        lbl_student = f"Élève / {prepare_arabic_text_for_pdf('التلميذ')} :"
        lbl_mat = f"Matricule / {prepare_arabic_text_for_pdf('التسجيل')} :"
        lbl_act = f"Activité / {prepare_arabic_text_for_pdf('النشاط')} :"
        lbl_grp = f"Groupe / {prepare_arabic_text_for_pdf('المجموعة')} :"
        lbl_per = f"Période / {prepare_arabic_text_for_pdf('الفترة')} :"
        lbl_mth = f"Mode / {prepare_arabic_text_for_pdf('طريقة')} :"
        lbl_amt = f"Montant / {prepare_arabic_text_for_pdf('المبلغ')} :"
        lbl_bal = f"Reliquat / {prepare_arabic_text_for_pdf('المتبقي')} :"
    else: # fr
        activity_disp = subject.name_fr if subject else "Échecs"
        group_disp = group.name_fr if group else "Groupe Général"
        method_disp = payment.get_method_label("fr")
        period_disp = period_str
        lbl_student = "Nom de l'élève :"
        lbl_mat = "Matricule :"
        lbl_act = "Activité / Matière :"
        lbl_grp = "Groupe :"
        lbl_per = "Période concernée :"
        lbl_mth = "Mode de règlement :"
        lbl_amt = "Montant perçu :"
        lbl_bal = "Reste à payer :"

    amt_str = format_currency(payment.amount, lang=lang)
    bal_str = format_currency(balance, lang=lang)
    if lang == "ar":
        amt_str = prepare_arabic_text_for_pdf(amt_str)
        bal_str = prepare_arabic_text_for_pdf(bal_str)

    cell_style = ParagraphStyle('Cell', fontName=font_name, fontSize=9, leading=12)
    cell_bold = ParagraphStyle('CellB', fontName=font_name, fontSize=9, leading=12, textColor=NAVY)
    amt_style = ParagraphStyle('Amt', fontName=font_name, fontSize=11, leading=13, textColor=BLUE)

    if lang == "ar":
        # In RTL, values go first (right side) and labels follow or vice-versa
        details_data = [
            [Paragraph(f"<b>{student.registration_number}</b>", cell_bold), Paragraph(lbl_mat, cell_style),
             Paragraph(f"<b>{student_disp}</b>", cell_bold), Paragraph(lbl_student, cell_style)],
            [Paragraph(group_disp, cell_style), Paragraph(lbl_grp, cell_style),
             Paragraph(activity_disp, cell_style), Paragraph(lbl_act, cell_style)],
            [Paragraph(method_disp, cell_style), Paragraph(lbl_mth, cell_style),
             Paragraph(period_disp, cell_style), Paragraph(lbl_per, cell_style)],
            [Paragraph(f"<b>{bal_str}</b>", cell_bold), Paragraph(lbl_bal, cell_style),
             Paragraph(f"<b>{amt_str}</b>", amt_style), Paragraph(lbl_amt, cell_style)],
        ]
        col_w = [45 * mm, 30 * mm, 80 * mm, 35 * mm]
    else:
        details_data = [
            [Paragraph(lbl_student, cell_style), Paragraph(f"<b>{student_disp}</b>", cell_bold),
             Paragraph(lbl_mat, cell_style), Paragraph(f"<b>{student.registration_number}</b>", cell_bold)],
            [Paragraph(lbl_act, cell_style), Paragraph(activity_disp, cell_style),
             Paragraph(lbl_grp, cell_style), Paragraph(group_disp, cell_style)],
            [Paragraph(lbl_per, cell_style), Paragraph(period_disp, cell_style),
             Paragraph(lbl_mth, cell_style), Paragraph(method_disp, cell_style)],
            [Paragraph(lbl_amt, cell_style), Paragraph(f"<b>{amt_str}</b>", amt_style),
             Paragraph(lbl_bal, cell_style), Paragraph(f"<b>{bal_str}</b>", cell_bold)],
        ]
        col_w = [35 * mm, 80 * mm, 30 * mm, 45 * mm]

    details_table = Table(details_data, colWidths=col_w)
    details_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), LIGHT_BG),
        ('GRID', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(details_table)
    story.append(Spacer(1, 6 * mm))

    # Bottom Signatures & Stamp area
    if lang == "ar":
        footer_msg = prepare_arabic_text_for_pdf("وثيقة رسمية صادرة عن أكاديمية جينيوس للشطرنج. تعتبر إثباتاً قانونياً للأداء.")
        stamp_title = prepare_arabic_text_for_pdf("الخاتم والتوقيع المعتمد")
    elif lang == "bilingual":
        footer_msg = f"Document officiel GCA / {prepare_arabic_text_for_pdf('وثيقة رسمية صادرة عن الأكاديمية')}"
        stamp_title = f"Cachet & Signature / {prepare_arabic_text_for_pdf('الخاتم والتوقيع')}"
    else:
        footer_msg = "Document officiel délivré par Genius Chess Academy. Valable comme justificatif de paiement."
        stamp_title = "Cachet & Signature de l'Administration"

    sign_data = [
        [
            Paragraph(f"<font size=7 color='#666666'>{footer_msg}<br/>"
                      f"Réf système: GCA-SECURE-{payment.id:06d}</font>",
                      ParagraphStyle('F1', fontName=font_name, leading=10)),
            Paragraph(f"<b><font size=8 color='{NAVY.hexval()}'>{stamp_title}</font></b><br/><br/><br/>"
                      f"<font size=7 color='#999999'>[ GENIUS CHESS ACADEMY - VALIDÉ ]</font>",
                      ParagraphStyle('F2', fontName=font_name, alignment=1, leading=11)),
        ]
    ]
    sign_table = Table(sign_data, colWidths=[120 * mm, 70 * mm])
    sign_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('BOX', (1,0), (1,0), 0.8, BLUE),
        ('BACKGROUND', (1,0), (1,0), colors.white),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(sign_table)

    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes
"""

with open("finance/receipt_pdf.py", "w", encoding="utf-8") as f:
    f.write(content)

print("Created finance/receipt_pdf.py")
