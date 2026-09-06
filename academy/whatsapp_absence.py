import re
import urllib.parse
from datetime import datetime, date
from django.conf import settings
from academy.models import Notification
from academy.whatsapp_reminders import format_phone_for_whatsapp, send_whatsapp_via_gateway


def build_whatsapp_absence_message(schedule, student, target_date=None, lang="fr"):
    """
    Construit le message d'alerte d'absence bienveillant et officiel pour le parent.
    Respecte la langue de préférence du parent (FR ou AR).
    """
    if target_date is None:
        target_date = date.today()

    parent = student.parent
    p_name_fr = parent.full_name_fr if parent else "Parent"
    p_name_ar = parent.full_name_ar if parent else "ولي الأمر"
    st_name_fr = student.get_full_name("fr")
    st_name_ar = student.get_full_name("ar")

    grp_fr = schedule.group.name_fr if schedule.group else "Groupe"
    grp_ar = schedule.group.name_ar if schedule.group else "الفوج"
    subj_fr = schedule.group.subject.name_fr if schedule.group and schedule.group.subject else "Échecs"
    subj_ar = schedule.group.subject.name_ar if schedule.group and schedule.group.subject else "الشطرنج"

    time_str = f"{schedule.start_time.strftime('%H:%M')} - {schedule.end_time.strftime('%H:%M')}"
    coach_fr = schedule.trainer_name_fr or "Le formateur"
    coach_ar = schedule.trainer_name_ar or "المؤطر"
    date_formatted = target_date.strftime("%d/%m/%Y")

    if lang == "ar":
        message = (
            f"السلام عليكم ورحمة الله السيد(ة) {p_name_ar}،\n\n"
            f"♟️ *إشعار بالغياب — جمعية الشطرنج القاسمي* :\n"
            f"نحيطكم علماً بأن التلميذ(ة) *{st_name_ar}* لم يسجل حضوره اليوم ({date_formatted}) في حصة *{subj_ar}* ({grp_ar}) المبرمجة على الساعة *{time_str}*.\n\n"
            f"نرجو أن يكون المانع خيراً. نرجو منكم التكرم بإشعارنا في حال وجود أي مانع أو عذر مسبق. نتمنى لأبنائنا السلامة والعافية دائماً ! 🌟\n\n"
            f"👨‍🏫 المؤطر : {coach_ar}\n"
            f"📍 أكاديمية جينيوس للشطرنج — سيدي قاسم / الرباط\n"
            f"🌐 الموقع : https://geniuschess.ma"
        )
    else:
        message = (
            f"Bonjour M./Mme {p_name_fr},\n\n"
            f"♟️ *Avis d'Absence — Genius Chess Academy* :\n"
            f"Nous vous informons que l'élève *{st_name_fr}* n'a pas été enregistré(e) présent(e) aujourd'hui ({date_formatted}) à sa séance de *{subj_fr}* ({grp_fr}) programmée de *{time_str}*.\n\n"
            f"Nous espérons que tout va bien. N'hésitez pas à nous informer en cas d'empêchement ou pour toute justification. Nous souhaitons le meilleur à nos élèves ! 🌟\n\n"
            f"👨‍🏫 Formateur : {coach_fr}\n"
            f"📍 Genius Chess Academy — جمعية الشطرنج القاسمي\n"
            f"🌐 Site Web : https://geniuschess.ma"
        )
    return message


def get_whatsapp_absence_chat_url(schedule, student, target_date=None, lang="fr"):
    """
    Génère le lien direct 'wa.me' pré-rempli pour ouvrir WhatsApp en 1 clic.
    """
    parent = student.parent
    if not parent or not parent.phone:
        return ""
    wa_phone = format_phone_for_whatsapp(parent.phone)
    if not wa_phone:
        return ""
    msg = build_whatsapp_absence_message(schedule, student, target_date=target_date, lang=lang)
    encoded = urllib.parse.quote(msg)
    return f"https://wa.me/{wa_phone}?text={encoded}"


def send_absence_alert_to_parent(attendance, force=False):
    """
    Envoie l'alerte d'absence par WhatsApp au parent via la passerelle serveur.
    Intègre une sécurité anti-doublon (ne renvoie pas si déjà envoyé, sauf si force=True).
    """
    if attendance.status != "absent":
        return {'success': False, 'error': "L'élève n'est pas marqué absent."}

    # Vérification anti-doublon dans les notes
    already_sent = "Alerte WhatsApp envoyée" in (attendance.notes or "")
    if already_sent and not force:
        return {'success': False, 'error': "Alerte déjà envoyée précédemment.", 'already_sent': True}

    student = attendance.student
    parent = student.parent
    if not parent or not parent.phone:
        return {'success': False, 'error': "Numéro de téléphone du parent manquant."}

    wa_phone = format_phone_for_whatsapp(parent.phone)
    if not wa_phone:
        return {'success': False, 'error': "Format du numéro de téléphone invalide."}

    lang = parent.preferred_language or "fr"
    message = build_whatsapp_absence_message(
        attendance.session,
        student,
        target_date=attendance.date,
        lang=lang
    )

    # 1. Envoi via passerelle WhatsApp si configurée
    gateway_res = send_whatsapp_via_gateway(wa_phone, message)

    # 2. Notification interne pour l'espace parent
    if parent.user:
        Notification.objects.create(
            recipient=parent.user,
            title_fr="Avis d'absence à la séance",
            title_ar="إشعار بالغياب عن الحصة",
            message_fr=f"Votre enfant {student.get_full_name('fr')} a été marqué(e) absent(e) à la séance du {attendance.date.strftime('%d/%m/%Y')}.",
            message_ar=f"تم تسجيل غياب التلميذ(ة) {student.get_full_name('ar')} عن حصة يوم {attendance.date.strftime('%d/%m/%Y')}.",
            notification_type="absence"
        )

    # 3. Marquer l'horodatage dans les notes
    now_str = datetime.now().strftime("%d/%m à %H:%M")
    tag = f"📲 Alerte WhatsApp envoyée ({now_str})"
    if attendance.notes:
        attendance.notes = f"{attendance.notes} | {tag}"
    else:
        attendance.notes = tag
    attendance.save(update_fields=['notes'])

    return {
        'success': True,
        'gateway_result': gateway_res,
        'sent_to': wa_phone,
        'tag': tag
    }


def send_bulk_absence_alerts_for_session(schedule, target_date=None):
    """
    Envoie l'alerte d'absence à tous les élèves absents de la séance qui ne l'ont pas encore reçue.
    """
    from academy.models import Attendance

    if target_date is None:
        target_date = date.today()

    absent_attendances = Attendance.objects.filter(
        session=schedule,
        date=target_date,
        status='absent'
    ).select_related('student', 'student__parent', 'session', 'session__group', 'session__group__subject')

    sent_count = 0
    skipped_count = 0
    errors = []

    for att in absent_attendances:
        if "Alerte WhatsApp envoyée" in (att.notes or ""):
            skipped_count += 1
            continue

        res = send_absence_alert_to_parent(att, force=False)
        if res.get('success'):
            sent_count += 1
        else:
            errors.append(f"{att.student.get_full_name('fr')}: {res.get('error')}")

    return {
        'total_absents': len(absent_attendances),
        'sent_count': sent_count,
        'skipped_count': skipped_count,
        'errors': errors
    }
