import io
import os
import qrcode
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from core.i18n import prepare_arabic_text_for_pdf

CARD_WIDTH = 85.6 * mm
CARD_HEIGHT = 54.0 * mm

NAVY = colors.HexColor("#0A192F")
NAVY_LIGHT = colors.HexColor("#1E293B")
GOLD = colors.HexColor("#D97706")
GOLD_LIGHT = colors.HexColor("#FDE68A")
WHITE = colors.HexColor("#FFFFFF")
GRAY_LIGHT = colors.HexColor("#F8FAFC")
BORDER_GRAY = colors.HexColor("#CBD5E1")
TEXT_DARK = colors.HexColor("#0F172A")
TEXT_MUTED = colors.HexColor("#64748B")

_FONTS_INITIALIZED = False


def init_card_fonts():
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


def get_card_font(is_arabic=False):
    init_card_fonts()
    registered = pdfmetrics.getRegisteredFontNames()
    if is_arabic:
        if "Amiri" in registered:
            return "Amiri"
        if "Cairo" in registered:
            return "Cairo"
        if "SystemArial" in registered:
            return "SystemArial"
    return "Helvetica"


def get_card_font_bold(is_arabic=False):
    init_card_fonts()
    registered = pdfmetrics.getRegisteredFontNames()
    if is_arabic:
        if "Cairo" in registered:
            return "Cairo"
        if "Amiri" in registered:
            return "Amiri"
        if "SystemArial" in registered:
            return "SystemArial"
    return "Helvetica-Bold"


def make_student_qr_code_image(student):
    """
    Encodes student registration number into a crisp QR Code PNG image buffer.
    Format: GCA:STU:{registration_number}
    """
    payload = f"GCA:STU:{student.registration_number}"
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=1,
    )
    qr.add_data(payload)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#0A192F", back_color="#FFFFFF")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


def draw_single_card(c, x, y, student, lang="bilingual"):
    """
    Renders a single standard ID card (85.6mm x 54.0mm) at coordinate (x, y).
    """
    init_card_fonts()
    c.saveState()

    # 1. Background Card Shape & Shadow
    c.setFillColor(WHITE)
    c.setStrokeColor(BORDER_GRAY)
    c.setLineWidth(0.75)
    c.roundRect(x, y, CARD_WIDTH, CARD_HEIGHT, radius=3.5 * mm, stroke=1, fill=1)

    # 2. Header Banner (Navy)
    header_h = 13.0 * mm
    c.setFillColor(NAVY)
    c.setStrokeColor(NAVY)
    # Clip path for rounded top header
    p = c.beginPath()
    p.roundRect(x, y + CARD_HEIGHT - header_h, CARD_WIDTH, header_h, radius=3.5 * mm)
    c.drawPath(p, stroke=0, fill=1)
    # Cover bottom round corners of header
    c.rect(x, y + CARD_HEIGHT - header_h, CARD_WIDTH, 4.0 * mm, stroke=0, fill=1)

    # Gold Accent Line under header
    c.setFillColor(GOLD)
    c.rect(x, y + CARD_HEIGHT - header_h - 0.7 * mm, CARD_WIDTH, 0.7 * mm, stroke=0, fill=1)

    # Logo / Icon in header
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    logo_path = os.path.join(base_dir, "static", "img", "logo.png")
    if os.path.exists(logo_path):
        try:
            c.drawImage(
                ImageReader(logo_path),
                x + 2.5 * mm, y + CARD_HEIGHT - header_h + 1.2 * mm,
                width=10.5 * mm, height=10.5 * mm,
                mask='auto', preserveAspectRatio=True
            )
        except Exception:
            pass

    # Header Texts
    c.setFillColor(WHITE)
    c.setFont(get_card_font_bold(False), 8.5)
    c.drawString(x + 14.5 * mm, y + CARD_HEIGHT - 6.0 * mm, "GENIUS CHESS ACADEMY")

    c.setFillColor(GOLD_LIGHT)
    c.setFont(get_card_font(True), 7.5)
    ar_title = prepare_arabic_text_for_pdf("أكاديمية جينيوس للشطرنج")
    c.drawString(x + 14.5 * mm, y + CARD_HEIGHT - 10.5 * mm, ar_title)

    # 3. Footer Bar (Navy Thin)
    footer_h = 4.2 * mm
    c.setFillColor(NAVY)
    # Clip bottom corners
    p_foot = c.beginPath()
    p_foot.roundRect(x, y, CARD_WIDTH, footer_h, radius=3.5 * mm)
    c.drawPath(p_foot, stroke=0, fill=1)
    c.rect(x, y + 2.0 * mm, CARD_WIDTH, 2.2 * mm, stroke=0, fill=1)

    c.setFillColor(WHITE)
    c.setFont("Helvetica", 5.2)
    c.drawString(x + 3.5 * mm, y + 1.2 * mm, "CARTE DE MEMBRE OFFICIELLE")
    ar_foot = prepare_arabic_text_for_pdf("بطاقة العضوية الرسمية")
    c.setFont(get_card_font(True), 5.2)
    c.drawRightString(x + CARD_WIDTH - 3.5 * mm, y + 1.2 * mm, ar_foot)

    # 4. QR Code Box (Right side)
    qr_size = 23.5 * mm
    qr_x = x + CARD_WIDTH - qr_size - 3.5 * mm
    qr_y = y + footer_h + 3.0 * mm

    # Border frame around QR
    c.setFillColor(WHITE)
    c.setStrokeColor(colors.HexColor("#E2E8F0"))
    c.setLineWidth(0.6)
    c.roundRect(qr_x - 1.0 * mm, qr_y - 1.0 * mm, qr_size + 2.0 * mm, qr_size + 2.0 * mm, radius=2.0 * mm, fill=1, stroke=1)

    # Generate and draw QR Code
    qr_buf = make_student_qr_code_image(student)
    c.drawImage(ImageReader(qr_buf), qr_x, qr_y, width=qr_size, height=qr_size)

    # QR Subtitle
    c.setFillColor(TEXT_MUTED)
    c.setFont("Helvetica-Bold", 4.8)
    c.drawCentredString(qr_x + qr_size / 2.0, qr_y - 2.8 * mm, "SCAN PRÉSENCE • مسح الحضور")

    # 5. Student Info Block (Left side)
    left_x = x + 3.5 * mm
    info_w = qr_x - left_x - 2.5 * mm

    # Student Full Name (French)
    c.setFillColor(TEXT_DARK)
    c.setFont(get_card_font_bold(False), 9.0)
    full_name_fr = student.get_full_name('fr').upper()
    if len(full_name_fr) > 22:
        c.setFont(get_card_font_bold(False), 7.8)
    c.drawString(left_x, y + CARD_HEIGHT - header_h - 4.5 * mm, full_name_fr)

    # Student Full Name (Arabic)
    ar_full_name = prepare_arabic_text_for_pdf(student.get_full_name('ar'))
    if ar_full_name:
        c.setFillColor(NAVY)
        c.setFont(get_card_font_bold(True), 8.5)
        c.drawString(left_x, y + CARD_HEIGHT - header_h - 8.2 * mm, ar_full_name)

    # Matricule Badge
    mat_y = y + CARD_HEIGHT - header_h - 13.5 * mm
    c.setFillColor(colors.HexColor("#F1F5F9"))
    c.setStrokeColor(colors.HexColor("#CBD5E1"))
    c.setLineWidth(0.5)
    c.roundRect(left_x, mat_y, 35.0 * mm, 4.2 * mm, radius=1.5 * mm, fill=1, stroke=1)

    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 6.2)
    c.drawString(left_x + 2.0 * mm, mat_y + 1.2 * mm, f"ID: {student.registration_number}")

    # Group / Activity
    grp = student.groups.first()
    grp_name = grp.name_fr if grp else "Échecs & Stratégie"
    subj_name = grp.subject.name_fr if grp and grp.subject else "GCA Academy"

    c.setFillColor(TEXT_MUTED)
    c.setFont("Helvetica", 5.8)
    c.drawString(left_x, mat_y - 3.8 * mm, "Groupe:")

    c.setFillColor(TEXT_DARK)
    c.setFont("Helvetica-Bold", 6.2)
    if len(grp_name) > 24:
        grp_name = grp_name[:22] + "..."
    c.drawString(left_x + 11.0 * mm, mat_y - 3.8 * mm, grp_name)

    # Academic Year
    c.setFillColor(TEXT_MUTED)
    c.setFont("Helvetica", 5.5)
    c.drawString(left_x, mat_y - 7.5 * mm, "Saison: 2025 / 2026")

    c.restoreState()


def generate_single_student_card_pdf(student, lang="bilingual"):
    """
    Returns bytes of a single ID card PDF in ISO ID-1 card dimensions (85.6mm x 54mm).
    """
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=(CARD_WIDTH, CARD_HEIGHT))
    c.setTitle(f"Carte_Membre_{student.registration_number}")
    draw_single_card(c, 0, 0, student, lang=lang)
    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer.getvalue()


def generate_student_cards_sheet_pdf(students, lang="bilingual"):
    """
    Renders up to 8 cards per A4 sheet (2 columns x 4 rows) with cutting guides.
    """
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    c.setTitle("Planche_Cartes_Membres_GCA")

    page_w, page_h = A4
    cols = 2
    rows = 4
    cards_per_page = cols * rows

    margin_x = (page_w - (cols * CARD_WIDTH)) / 3.0
    margin_y = (page_h - (rows * CARD_HEIGHT)) / 5.0
    spacing_x = margin_x
    spacing_y = margin_y

    for idx, student in enumerate(students):
        page_idx = idx % cards_per_page
        if idx > 0 and page_idx == 0:
            c.showPage()

        col = page_idx % cols
        row = page_idx // cols

        card_x = margin_x + col * (CARD_WIDTH + spacing_x)
        # Coordinates from bottom-left
        card_y = page_h - margin_y - (row + 1) * CARD_HEIGHT - row * spacing_y

        draw_single_card(c, card_x, card_y, student, lang=lang)

        # Light dashed cutting crop marks around the card
        c.saveState()
        c.setStrokeColor(colors.HexColor("#94A3B8"))
        c.setLineWidth(0.3)
        c.setDash(2, 2)
        c.rect(card_x - 0.5 * mm, card_y - 0.5 * mm, CARD_WIDTH + 1.0 * mm, CARD_HEIGHT + 1.0 * mm, stroke=1, fill=0)
        c.restoreState()

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer.getvalue()
