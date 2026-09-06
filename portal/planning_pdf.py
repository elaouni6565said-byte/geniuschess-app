import io
import os
from datetime import datetime
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from core.i18n import prepare_arabic_text_for_pdf, FRENCH_DAYS, ARABIC_DAYS

# Official GCA Palette
NAVY = colors.HexColor("#001B57")
BLUE = colors.HexColor("#0077CE")
ORANGE = colors.HexColor("#FF6E00")
LIGHT_BG = colors.HexColor("#F8FAFC")
DARK_GRAY = colors.HexColor("#1E293B")
BORDER_COLOR = colors.HexColor("#CBD5E1")
HEADER_BG = colors.HexColor("#001B57")
ALT_ROW_BG = colors.HexColor("#F1F5F9")

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


def get_preferred_font(lang="bilingual"):
    init_fonts()
    registered = pdfmetrics.getRegisteredFontNames()
    for fname in ["Amiri", "Amiri-Regular", "Amiri-Regular-Static", "Amiri-Bold", "Amiri-Bold-Static"]:
        if fname in registered:
            return fname
    return "Helvetica"


class NumberedCanvas(object):
    """Adds page numbers and footer rule to each page in landscape A4."""
    def __init__(self, *args, **kwargs):
        pass


def generate_master_planning_pdf(schedules, lang="fr", room=None):
    """
    Generates an official Master Timetable PDF for Genius Chess Academy in Landscape A4.
    Supports 'fr', 'ar', and 'bilingual' languages.
    """
    init_fonts()
    buffer = io.BytesIO()

    # Landscape A4: 297mm x 210mm
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=12 * mm,
        leftMargin=12 * mm,
        topMargin=10 * mm,
        bottomMargin=10 * mm,
    )

    story = []
    font_name = get_preferred_font(lang)
    styles = getSampleStyleSheet()

    # Header Titles - Organization & Academy
    academy_name = "GENIUS CHESS ACADEMY"
    org_subtitle = prepare_arabic_text_for_pdf("جمعية الشطرنج القاسمي")

    if lang == "ar":
        academy_sub = prepare_arabic_text_for_pdf("البرنامج العام الأسبوعي للحصص والتداريب • الموسم 2026")
        contact_text = prepare_arabic_text_for_pdf("سيدي قاسم • الموقع: geniuschess.ma • هاتف: 06 060424142")
        doc_title = prepare_arabic_text_for_pdf("البرنامج الأسبوعي العام")
    elif lang == "bilingual":
        academy_sub = f"PLANNING OFFICIEL HEBDOMADAIRE / {prepare_arabic_text_for_pdf('البرنامج الأسبوعي العام')} • 2026"
        contact_text = "Sidi Kacem • www.geniuschess.ma • Tél: 06 060424142"
        doc_title = f"PLANNING OFFICIEL / {prepare_arabic_text_for_pdf('برنامج الحصص')}"
    else:
        academy_sub = "PLANNING OFFICIEL HEBDOMADAIRE DES COURS • SAISON 2026"
        contact_text = "Sidi Kacem • www.geniuschess.ma • Tél: 06 060424142"
        doc_title = "PLANNING GÉNÉRAL DES COURS"

    # Logo & Header Banner
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    logo_path = os.path.join(base_dir, "static", "img", "logo.png")

    now_str = datetime.now().strftime("%d/%m/%Y à %H:%M")
    if room:
        if lang == "ar":
            r_name = room.name_ar or room.name_fr
            filter_info = prepare_arabic_text_for_pdf(f"القاعة: {r_name}")
        elif lang == "bilingual":
            filter_info = f"Salle : {room.name_fr} ({room.name_ar})"
        else:
            filter_info = f"Salle : {room.name_fr}"
    else:
        if lang == "ar":
            filter_info = prepare_arabic_text_for_pdf("جميع القاعات")
        elif lang == "bilingual":
            filter_info = "Toutes les salles / جميع القاعات"
        else:
            filter_info = "Toutes les salles"

    if os.path.exists(logo_path):
        logo_img = RLImage(logo_path, width=22 * mm, height=22 * mm)
        hdr_table_data = [
            [
                logo_img,
                Paragraph(f"<b><font size=13 color='{NAVY.hexval()}'>{academy_name}</font></b><br/>"
                          f"<b><font size=9.5 color='{BLUE.hexval()}'>{org_subtitle}</font></b><br/>"
                          f"<font size=8 color='#475569'>{academy_sub}</font><br/>"
                          f"<font size=7 color='#64748B'>{contact_text}</font>",
                          ParagraphStyle('HdrLeft', fontName=font_name, leading=11.5)),
                Paragraph(f"<b><font size=12 color='{ORANGE.hexval()}'>{doc_title}</font></b><br/>"
                          f"<font size=8 color='#334155'><b>{filter_info}</b></font><br/>"
                          f"<font size=7 color='#64748B'>Édité le {now_str}</font>",
                          ParagraphStyle('HdrRight', fontName=font_name, alignment=2, leading=12)),
            ]
        ]
        hdr_table = Table(hdr_table_data, colWidths=[26 * mm, 160 * mm, 87 * mm])
        hdr_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
        ]))
        story.append(hdr_table)
    else:
        story.append(Paragraph(f"<b><font size=15 color='{NAVY.hexval()}'>{academy_name}</font></b><br/><b><font size=10 color='{BLUE.hexval()}'>{org_subtitle}</font></b>", styles['Title']))

    story.append(Spacer(1, 4 * mm))

    # Horizontal Divider
    divider = Table([['']], colWidths=[273 * mm], rowHeights=[2])
    divider.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), ORANGE),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(divider)
    story.append(Spacer(1, 4 * mm))

    # Table Headers
    if lang == "ar":
        headers = [
            prepare_arabic_text_for_pdf("اليوم"),
            prepare_arabic_text_for_pdf("التوقيت"),
            prepare_arabic_text_for_pdf("المادة / النشاط"),
            prepare_arabic_text_for_pdf("المجموعة والمستوى"),
            prepare_arabic_text_for_pdf("القاعة"),
            prepare_arabic_text_for_pdf("المدرب / المؤطر"),
        ]
        align_content = 2 # Right
    elif lang == "bilingual":
        headers = [
            f"Jour / {prepare_arabic_text_for_pdf('اليوم')}",
            f"Horaire / {prepare_arabic_text_for_pdf('التوقيت')}",
            f"Activité / {prepare_arabic_text_for_pdf('النشاط')}",
            f"Groupe / {prepare_arabic_text_for_pdf('المجموعة')}",
            f"Salle / {prepare_arabic_text_for_pdf('القاعة')}",
            f"Formateur / {prepare_arabic_text_for_pdf('المدرب')}",
        ]
        align_content = 0 # Left
    else:
        headers = [
            "Jour",
            "Horaire",
            "Discipline / Activité",
            "Groupe & Niveau",
            "Salle de cours",
            "Formateur / Enseignant",
        ]
        align_content = 0

    header_style = ParagraphStyle(
        'ThStyle',
        fontName=font_name,
        fontSize=9,
        leading=11,
        textColor=colors.white,
        alignment=1, # Center
        fontStyle='bold',
    )

    cell_style = ParagraphStyle(
        'TdStyle',
        fontName=font_name,
        fontSize=8.5,
        leading=11,
        textColor=DARK_GRAY,
        alignment=align_content,
    )

    cell_style_center = ParagraphStyle(
        'TdStyleCenter',
        fontName=font_name,
        fontSize=8.5,
        leading=11,
        textColor=DARK_GRAY,
        alignment=1,
    )

    # Convert headers to Paragraphs
    table_data = [[Paragraph(f"<b>{h}</b>", header_style) for h in headers]]

    # Sort schedules by day_of_week and start_time
    sorted_schedules = sorted(schedules, key=lambda s: (s.day_of_week, s.start_time))

    # Day mapping
    days_dict = ARABIC_DAYS if lang == "ar" else FRENCH_DAYS

    for idx, sch in enumerate(sorted_schedules):
        # Day
        raw_day = days_dict.get(sch.day_of_week, f"Jour {sch.day_of_week}")
        if lang == "ar":
            day_str = prepare_arabic_text_for_pdf(raw_day)
        elif lang == "bilingual":
            fr_d = FRENCH_DAYS.get(sch.day_of_week, "")
            ar_d = prepare_arabic_text_for_pdf(ARABIC_DAYS.get(sch.day_of_week, ""))
            day_str = f"{fr_d} • {ar_d}"
        else:
            day_str = raw_day

        # Time
        time_str = f"{sch.start_time.strftime('%H:%M')} - {sch.end_time.strftime('%H:%M')}"

        # Subject / Activity
        subj = sch.group.subject
        if lang == "ar":
            subject_str = prepare_arabic_text_for_pdf(subj.name_ar) if subj and subj.name_ar else (subj.name_fr if subj else "-")
        elif lang == "bilingual":
            ar_name = prepare_arabic_text_for_pdf(subj.name_ar) if subj and subj.name_ar else ""
            subject_str = f"{subj.name_fr} / {ar_name}" if subj else "-"
        else:
            subject_str = subj.name_fr if subj else "-"

        # Group Name & Color indicator
        grp = sch.group
        grp_color = getattr(grp, 'color', '#0077CE') or '#0077CE'
        if lang == "ar":
            grp_name = prepare_arabic_text_for_pdf(grp.name_ar) if grp and grp.name_ar else (grp.name_fr if grp else "-")
        elif lang == "bilingual":
            ar_grp = prepare_arabic_text_for_pdf(grp.name_ar) if grp and grp.name_ar else ""
            grp_name = f"{grp.name_fr} ({ar_grp})" if grp else "-"
        else:
            grp_name = grp.name_fr if grp else "-"

        # Room
        rm = sch.room
        if rm:
            if lang == "ar":
                room_str = prepare_arabic_text_for_pdf(rm.name_ar or rm.name_fr)
            elif lang == "bilingual":
                ar_rm = prepare_arabic_text_for_pdf(rm.name_ar) if rm.name_ar else ""
                room_str = f"{rm.name_fr} ({ar_rm})" if ar_rm else rm.name_fr
            else:
                room_str = rm.name_fr
        else:
            if lang == "ar":
                room_str = prepare_arabic_text_for_pdf("القاعة الرئيسية")
            elif lang == "bilingual":
                room_str = f"Salle Principale ({prepare_arabic_text_for_pdf('القاعة الرئيسية')})"
            else:
                room_str = "Salle Principale"

        # Trainer
        tr_fr = sch.get_trainer_name('fr')
        tr_ar = sch.get_trainer_name('ar')
        if lang == "ar":
            trainer_str = prepare_arabic_text_for_pdf(tr_ar) if tr_ar else (tr_fr or "-")
        elif lang == "bilingual":
            ar_t = prepare_arabic_text_for_pdf(tr_ar) if tr_ar else ""
            trainer_str = f"{tr_fr} • {ar_t}" if tr_fr else (ar_t or "-")
        else:
            trainer_str = tr_fr or "-"

        row = [
            Paragraph(f"<b>{day_str}</b>", cell_style_center),
            Paragraph(f"<b>{time_str}</b>", cell_style_center),
            Paragraph(f"<font color='{grp_color}'><b>●</b></font> {subject_str}", cell_style),
            Paragraph(f"<b>{grp_name}</b>", cell_style),
            Paragraph(f"{room_str}", cell_style_center),
            Paragraph(f"{trainer_str}", cell_style),
        ]
        table_data.append(row)

    if len(table_data) == 1:
        # Empty state
        empty_msg = "Aucun créneau programmé dans le planning." if lang != "ar" else prepare_arabic_text_for_pdf("لا توجد حصص مسجلة في البرنامج.")
        table_data.append([
            Paragraph(empty_msg, cell_style_center),
            Paragraph("-", cell_style_center),
            Paragraph("-", cell_style_center),
            Paragraph("-", cell_style_center),
            Paragraph("-", cell_style_center),
            Paragraph("-", cell_style_center),
        ])

    # Col Widths for 273mm printable width
    # 273mm total: Day (38mm), Time (35mm), Subject (55mm), Group (60mm), Room (35mm), Trainer (50mm)
    col_widths = [38 * mm, 35 * mm, 55 * mm, 60 * mm, 35 * mm, 50 * mm]

    table = Table(table_data, colWidths=col_widths, repeatRows=1)
    t_style = [
        ('BACKGROUND', (0, 0), (-1, 0), HEADER_BG),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 4.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4.5),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('GRID', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
    ]

    # Zebra striping
    for r in range(1, len(table_data)):
        if r % 2 == 0:
            t_style.append(('BACKGROUND', (0, r), (-1, r), ALT_ROW_BG))

    table.setStyle(TableStyle(t_style))
    story.append(table)

    story.append(Spacer(1, 4 * mm))

    # Summary & Stamp Footer
    summary_text = f"Total des créneaux hebdomadaires : <b>{len(sorted_schedules)} séances</b> • GENIUS CHESS ACADEMY"
    if lang == "ar":
        summary_text = prepare_arabic_text_for_pdf(f"مجموع الحصص الأسبوعية: {len(sorted_schedules)} حصة • جمعية الشطرنج القاسمي")
    elif lang == "bilingual":
        summary_text = f"Total des créneaux : <b>{len(sorted_schedules)} séances</b> • {org_subtitle}"

    footer_table_data = [
        [
            Paragraph(summary_text, ParagraphStyle('Summary', fontName=font_name, fontSize=8, textColor=DARK_GRAY)),
            Paragraph(f"Cachet & Signature de la Direction<br/><br/><br/>",
                      ParagraphStyle('Stamp', fontName=font_name, fontSize=7.5, alignment=2, textColor=colors.HexColor('#64748B'))),
        ]
    ]
    footer_table = Table(footer_table_data, colWidths=[180 * mm, 93 * mm])
    footer_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(KeepTogether(footer_table))

    doc.build(story)
    pdf = buffer.getvalue()
    buffer.close()
    return pdf
