import io
import os
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from core.i18n import (
    prepare_arabic_text_for_pdf, FRENCH_DAYS, ARABIC_DAYS
)

# Colors
NAVY = colors.HexColor("#001B57")
BLUE = colors.HexColor("#0077CE")
ORANGE = colors.HexColor("#FF6E00")
LIGHT_BG = colors.HexColor("#F8FAFC")
DARK_GRAY = colors.HexColor("#1E293B")
BORDER_COLOR = colors.HexColor("#CBD5E1")

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


def generate_timetable_pdf(student, lang="fr"):
    """
    Generates a printable PDF timetable for a student.
    Supports lang in ('fr', 'ar', 'bilingual').
    """
    init_fonts()
    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=14 * mm,
        leftMargin=14 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
    )

    story = []
    font_name = get_preferred_font(lang)
    styles = getSampleStyleSheet()

    # Pre-extract data
    parent = student.parent
    groups = student.groups.all().select_related('subject', 'level')
    
    # Gather all weekly sessions
    sessions_list = []
    for g in groups:
        for sch in g.schedules.all().select_related('room'):
            sessions_list.append({
                'day_of_week': sch.day_of_week,
                'start_time': sch.start_time,
                'end_time': sch.end_time,
                'group': g,
                'subject': g.subject,
                'room': sch.room or g.room,
                'trainer_fr': sch.get_trainer_name('fr'),
                'trainer_ar': sch.get_trainer_name('ar'),
            })
    sessions_list.sort(key=lambda x: (x['day_of_week'], x['start_time']))

    # Headers - Organization & Academy
    academy_name = "GENIUS CHESS ACADEMY"
    org_subtitle = prepare_arabic_text_for_pdf("جمعية الشطرنج القاسمي")

    if lang == "ar":
        title_text = prepare_arabic_text_for_pdf("جدول الحصص والتوقيت الأسبوعي")
        academy_sub = prepare_arabic_text_for_pdf("الموسم الدراسي 2026 • شطرنج • روبوتيك • حساب ذهني")
        contact_text = prepare_arabic_text_for_pdf("سيدي قاسم / الرباط • الموقع: geniuschess.ma • هاتف: 0661000000")
    elif lang == "bilingual":
        title_text = f"EMPLOI DU TEMPS / {prepare_arabic_text_for_pdf('جدول الحصص الأسبوعي')}"
        academy_sub = f"Saison 2026 • Échecs • Robotique • Calcul Mental"
        contact_text = "Sidi Kacem / Rabat • www.geniuschess.ma • Tél: 06 61 00 00 00"
    else:
        title_text = "EMPLOI DU TEMPS HEBDOMADAIRE"
        academy_sub = "Saison Académique 2026 • Échecs • Robotique • Calcul Mental"
        contact_text = "Sidi Kacem / Rabat • www.geniuschess.ma • Tél: 06 61 00 00 00"

    # Logo Header
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    logo_path = os.path.join(base_dir, "static", "img", "logo.png")

    if os.path.exists(logo_path):
        logo_img = RLImage(logo_path, width=24 * mm, height=24 * mm)
        hdr_data = [
            [
                logo_img,
                Paragraph(f"<b><font size=13 color='{NAVY.hexval()}'>{academy_name}</font></b><br/>"
                          f"<b><font size=9.5 color='{BLUE.hexval()}'>{org_subtitle}</font></b><br/>"
                          f"<font size=8 color='#555555'>{academy_sub}</font><br/>"
                          f"<font size=7 color='#666666'>{contact_text}</font>",
                          ParagraphStyle('H1', fontName=font_name, leading=12)),
                Paragraph(f"<b><font size=12 color='{ORANGE.hexval()}'>{title_text}</font></b><br/>"
                          f"<font size=8.5 color='#555555'>Année 2026 / 2027</font>",
                          ParagraphStyle('H2', fontName=font_name, alignment=2, leading=13)),
            ]
        ]
        hdr_table = Table(hdr_data, colWidths=[28 * mm, 95 * mm, 59 * mm])
    else:
        hdr_data = [
            [
                Paragraph(f"<b><font size=13 color='{NAVY.hexval()}'>{academy_name}</font></b><br/>"
                          f"<b><font size=9.5 color='{BLUE.hexval()}'>{org_subtitle}</font></b><br/>"
                          f"<font size=8 color='#555555'>{academy_sub}</font><br/>"
                          f"<font size=7 color='#666666'>{contact_text}</font>",
                          ParagraphStyle('H1', fontName=font_name, leading=12)),
                Paragraph(f"<b><font size=12 color='{ORANGE.hexval()}'>{title_text}</font></b><br/>"
                          f"<font size=8.5 color='#555555'>Année 2026 / 2027</font>",
                          ParagraphStyle('H2', fontName=font_name, alignment=2, leading=13)),
            ]
        ]
        hdr_table = Table(hdr_data, colWidths=[120 * mm, 62 * mm])

    hdr_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LINEBELOW', (0,0), (-1,-1), 1.5, NAVY),
    ]))
    story.append(hdr_table)
    story.append(Spacer(1, 5 * mm))

    # Student Card
    st_name_fr = f"{student.first_name_fr} {student.last_name_fr}".strip()
    st_name_ar = f"{student.first_name_ar} {student.last_name_ar}".strip()
    parent_name = parent.get_name('fr') if parent else "—"

    if lang == "ar":
        card_rows = [
            [
                Paragraph(f"<b>{prepare_arabic_text_for_pdf('التلميذ :')}</b> {prepare_arabic_text_for_pdf(st_name_ar or st_name_fr)}",
                          ParagraphStyle('C1', fontName=font_name, fontSize=9.5, alignment=2)),
                Paragraph(f"<b>{prepare_arabic_text_for_pdf('رقم التسجيل :')}</b> {student.registration_number}",
                          ParagraphStyle('C2', fontName=font_name, fontSize=9.5, alignment=2)),
            ],
            [
                Paragraph(f"<b>{prepare_arabic_text_for_pdf('ولي الأمر :')}</b> {prepare_arabic_text_for_pdf(parent.get_name('ar') if parent else '—')}",
                          ParagraphStyle('C3', fontName=font_name, fontSize=9, alignment=2)),
                Paragraph(f"<b>{prepare_arabic_text_for_pdf('الهاتف :')}</b> {parent.phone if parent else '—'}",
                          ParagraphStyle('C4', fontName=font_name, fontSize=9, alignment=2)),
            ]
        ]
    elif lang == "bilingual":
        card_rows = [
            [
                Paragraph(f"<b>Élève / {prepare_arabic_text_for_pdf('التلميذ')} :</b> {st_name_fr} ({prepare_arabic_text_for_pdf(st_name_ar)})",
                          ParagraphStyle('C1', fontName=font_name, fontSize=9.5)),
                Paragraph(f"<b>Matricule / {prepare_arabic_text_for_pdf('التسجيل')} :</b> {student.registration_number}",
                          ParagraphStyle('C2', fontName=font_name, fontSize=9.5, alignment=2)),
            ],
            [
                Paragraph(f"<b>Tuteur / {prepare_arabic_text_for_pdf('ولي الأمر')} :</b> {parent_name}",
                          ParagraphStyle('C3', fontName=font_name, fontSize=9)),
                Paragraph(f"<b>Tél :</b> {parent.phone if parent else '—'}",
                          ParagraphStyle('C4', fontName=font_name, fontSize=9, alignment=2)),
            ]
        ]
    else:
        card_rows = [
            [
                Paragraph(f"<b>Élève :</b> {st_name_fr}", ParagraphStyle('C1', fontName=font_name, fontSize=9.5)),
                Paragraph(f"<b>Matricule :</b> {student.registration_number}", ParagraphStyle('C2', fontName=font_name, fontSize=9.5, alignment=2)),
            ],
            [
                Paragraph(f"<b>Tuteur :</b> {parent_name}", ParagraphStyle('C3', fontName=font_name, fontSize=9)),
                Paragraph(f"<b>Tél :</b> {parent.phone if parent else '—'}", ParagraphStyle('C4', fontName=font_name, fontSize=9, alignment=2)),
            ]
        ]

    card_table = Table(card_rows, colWidths=[120 * mm, 62 * mm])
    card_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), LIGHT_BG),
        ('BOX', (0,0), (-1,-1), 1, BORDER_COLOR),
        ('PADDING', (0,0), (-1,-1), 6),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(card_table)
    story.append(Spacer(1, 6 * mm))

    # Timetable Table
    if lang == "ar":
        th_day = prepare_arabic_text_for_pdf("اليوم")
        th_time = prepare_arabic_text_for_pdf("التوقيت")
        th_group = prepare_arabic_text_for_pdf("المجموعة")
        th_subj = prepare_arabic_text_for_pdf("النشاط")
        th_room = prepare_arabic_text_for_pdf("القاعة")
        th_coach = prepare_arabic_text_for_pdf("المدرب(ة)")
    elif lang == "bilingual":
        th_day = f"Jour / {prepare_arabic_text_for_pdf('اليوم')}"
        th_time = f"Horaire / {prepare_arabic_text_for_pdf('التوقيت')}"
        th_group = f"Groupe / {prepare_arabic_text_for_pdf('المجموعة')}"
        th_subj = f"Activité / {prepare_arabic_text_for_pdf('النشاط')}"
        th_room = f"Salle / {prepare_arabic_text_for_pdf('القاعة')}"
        th_coach = f"Formateur / {prepare_arabic_text_for_pdf('المدرب')}"
    else:
        th_day = "Jour"
        th_time = "Horaire"
        th_group = "Groupe"
        th_subj = "Activité"
        th_room = "Salle"
        th_coach = "Entraîneur / Formateur"

    table_data = [
        [
            Paragraph(f"<b><font color='white'>{th_day}</font></b>", ParagraphStyle('TH', fontName=font_name, alignment=1, fontSize=9)),
            Paragraph(f"<b><font color='white'>{th_time}</font></b>", ParagraphStyle('TH', fontName=font_name, alignment=1, fontSize=9)),
            Paragraph(f"<b><font color='white'>{th_group}</font></b>", ParagraphStyle('TH', fontName=font_name, alignment=1, fontSize=9)),
            Paragraph(f"<b><font color='white'>{th_subj}</font></b>", ParagraphStyle('TH', fontName=font_name, alignment=1, fontSize=9)),
            Paragraph(f"<b><font color='white'>{th_room}</font></b>", ParagraphStyle('TH', fontName=font_name, alignment=1, fontSize=9)),
            Paragraph(f"<b><font color='white'>{th_coach}</font></b>", ParagraphStyle('TH', fontName=font_name, alignment=1, fontSize=9)),
        ]
    ]

    for s in sessions_list:
        dow = s['day_of_week']
        if lang == "ar":
            day_str = prepare_arabic_text_for_pdf(ARABIC_DAYS.get(dow, ''))
            time_str = f"{s['start_time'].strftime('%H:%M')} - {s['end_time'].strftime('%H:%M')}"
            grp_str = prepare_arabic_text_for_pdf(s['group'].name_ar or s['group'].name_fr)
            subj_str = prepare_arabic_text_for_pdf(s['subject'].name_ar or s['subject'].name_fr)
            room_str = prepare_arabic_text_for_pdf(s['room'].name_ar if s['room'] else '—')
            coach_str = prepare_arabic_text_for_pdf(s['trainer_ar'] or s['trainer_fr'] or '—')
        elif lang == "bilingual":
            day_str = f"{FRENCH_DAYS.get(dow, '')} / {prepare_arabic_text_for_pdf(ARABIC_DAYS.get(dow, ''))}"
            time_str = f"{s['start_time'].strftime('%H:%M')} - {s['end_time'].strftime('%H:%M')}"
            ar_g = prepare_arabic_text_for_pdf(s['group'].name_ar) if s['group'].name_ar else ""
            grp_str = f"{s['group'].name_fr} ({ar_g})" if ar_g else s['group'].name_fr
            ar_sub = prepare_arabic_text_for_pdf(s['subject'].name_ar) if s['subject'].name_ar else ""
            subj_str = f"{s['subject'].name_fr} / {ar_sub}" if ar_sub else s['subject'].name_fr
            ar_rm = prepare_arabic_text_for_pdf(s['room'].name_ar) if s['room'] and s['room'].name_ar else ""
            rm_fr = s['room'].name_fr if s['room'] else "Salle Principale"
            room_str = f"{rm_fr} ({ar_rm})" if ar_rm else rm_fr
            ar_coach = prepare_arabic_text_for_pdf(s['trainer_ar']) if s['trainer_ar'] else ""
            coach_str = f"{s['trainer_fr']} • {ar_coach}" if ar_coach and s['trainer_fr'] else (s['trainer_fr'] or ar_coach or "—")
        else:
            day_str = FRENCH_DAYS.get(dow, '')
            time_str = f"{s['start_time'].strftime('%H:%M')} - {s['end_time'].strftime('%H:%M')}"
            grp_str = s['group'].name_fr
            subj_str = s['subject'].name_fr
            room_str = s['room'].name_fr if s['room'] else "—"
            coach_str = s['trainer_fr'] or "—"

        grp_color = s['group'].get_color()
        grp_badge = f"<font color='{grp_color}'><b>● {grp_str}</b></font>"

        table_data.append([
            Paragraph(f"<b>{day_str}</b>", ParagraphStyle('TD', fontName=font_name, fontSize=8.5, alignment=1)),
            Paragraph(f"<font color='{BLUE.hexval()}'><b>{time_str}</b></font>", ParagraphStyle('TD', fontName=font_name, fontSize=8.5, alignment=1)),
            Paragraph(grp_badge, ParagraphStyle('TD', fontName=font_name, fontSize=8.5, alignment=1)),
            Paragraph(subj_str, ParagraphStyle('TD', fontName=font_name, fontSize=8.5, alignment=1)),
            Paragraph(room_str, ParagraphStyle('TD', fontName=font_name, fontSize=8.5, alignment=1)),
            Paragraph(coach_str, ParagraphStyle('TD', fontName=font_name, fontSize=8.5, alignment=1)),
        ])

    if len(sessions_list) == 0:
        empty_msg = (
            prepare_arabic_text_for_pdf("لا توجد حصص مبرمجة حالياً لهذا التلميذ.")
            if lang == 'ar' else
            "Aucune séance programmée actuellement pour cet élève."
        )
        table_data.append([
            Paragraph(f"<i>{empty_msg}</i>", ParagraphStyle('Empty', fontName=font_name, fontSize=8.5, alignment=1)),
            "", "", "", "", ""
        ])

    sched_table = Table(table_data, colWidths=[28 * mm, 30 * mm, 38 * mm, 32 * mm, 24 * mm, 30 * mm])
    t_style = [
        ('BACKGROUND', (0,0), (-1,0), NAVY),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('GRID', (0,0), (-1,-1), 0.5, BORDER_COLOR),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
    ]
    for i in range(1, len(table_data)):
        if i % 2 == 0:
            t_style.append(('BACKGROUND', (0, i), (-1, i), LIGHT_BG))
    if len(sessions_list) == 0:
        t_style.append(('SPAN', (0, 1), (-1, 1)))

    sched_table.setStyle(TableStyle(t_style))
    story.append(sched_table)
    story.append(Spacer(1, 8 * mm))

    # Policy / Notes
    if lang == "ar":
        policy_title = prepare_arabic_text_for_pdf("ملاحظات وتوجيهات تنظيمية للأكاديمية :")
        p1 = prepare_arabic_text_for_pdf("• الحضور قبل 5 دقائق من انطلاق الحصة والالتزام بالزي المناسب.")
        p2 = prepare_arabic_text_for_pdf("• في حالة الغياب، يرجى إشعار الإدارة عبر البوابة أو الهاتف لبرمجة حصة الاستدراك.")
        p3 = prepare_arabic_text_for_pdf("• الأنشطة مفتوحة للأولياء في الأسبوع الأخير من كل شهر لمواكبة تطور الأبناء.")
    elif lang == "bilingual":
        policy_title = f"Règlement Intérieur / {prepare_arabic_text_for_pdf('توجيهات تنظيمية')} :"
        p1 = f"• Merci d'arriver 5 minutes avant le début de la séance / {prepare_arabic_text_for_pdf('الحضور 5 دقائق قبل بدء الحصة')}."
        p2 = f"• En cas d'absence, veuillez prévenir l'administration / {prepare_arabic_text_for_pdf('إشعار الإدارة في حالة الغياب')}."
        p3 = f"• Suivi en direct disponible sur votre Espace Parent / {prepare_arabic_text_for_pdf('المتابعة عبر فضاء ولي الأمر')}."
    else:
        policy_title = "Consignes & Règlement Pédagogique :"
        p1 = "• Les élèves sont priés de se présenter 5 minutes avant le début de chaque séance."
        p2 = "• En cas d'empêchement, veuillez informer l'administration pour organiser un rattrapage."
        p3 = "• Le suivi des séances et l'assiduité sont consultables 24h/24 sur votre Espace Parent."

    notice_rows = [
        [
            Paragraph(f"<b><font color='{NAVY.hexval()}'>{policy_title}</font></b><br/>"
                      f"<font size=8 color='#475569'>{p1}<br/>{p2}<br/>{p3}</font>",
                      ParagraphStyle('Notes', fontName=font_name, leading=11)),
            Paragraph(f"<b>Cachet & Signature de l'Académie :</b><br/><br/><br/><br/>"
                      f"<font size=7 color='#94A3B8'>GENIUS CHESS ACADEMY — {org_subtitle}</font>",
                      ParagraphStyle('Stamp', fontName=font_name, alignment=1, leading=9)),
        ]
    ]
    notice_table = Table(notice_rows, colWidths=[125 * mm, 57 * mm])
    notice_table.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 1, BORDER_COLOR),
        ('BACKGROUND', (0,0), (0,0), LIGHT_BG),
        ('PADDING', (0,0), (-1,-1), 6),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    story.append(notice_table)

    doc.build(story)
    pdf_value = buffer.getvalue()
    buffer.close()
    return pdf_value
