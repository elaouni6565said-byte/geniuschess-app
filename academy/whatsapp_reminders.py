import re
import urllib.parse
from datetime import date, datetime
from django.conf import settings
from academy.models import SessionSchedule, Student, Parent, Notification, SessionCancellation
from core.i18n import FRENCH_DAYS, ARABIC_DAYS


def format_phone_for_whatsapp(phone):
    """
    Normalizes a Moroccan phone number to international WhatsApp format.
    E.g.: '0661234567' -> '212661234567'
          '+212 661-234567' -> '212661234567'
          '00212661234567' -> '212661234567'
    """
    if not phone:
        return ""
    clean = re.sub(r'[^\d]', '', str(phone).strip())
    if clean.startswith('00212'):
        clean = clean[2:]
    elif clean.startswith('2120') and len(clean) >= 12:
        clean = '212' + clean[4:]
    elif clean.startswith('0'):
        clean = '212' + clean[1:]
    elif not clean.startswith('212') and len(clean) == 9:
        clean = '212' + clean
    return clean


def build_whatsapp_reminder_text(schedule, student, lang="fr"):
    """
    Builds the personalized WhatsApp reminder message for a parent.
    Respects the parent's chosen language (FR or AR).
    """
    parent = student.parent
    p_name_fr = parent.full_name_fr if parent else "Parent"
    p_name_ar = parent.full_name_ar if parent else "ولي الأمر"
    st_name_fr = student.get_full_name("fr")
    st_name_ar = student.get_full_name("ar")

    grp_fr = schedule.group.name_fr
    grp_ar = schedule.group.name_ar
    subj_fr = schedule.group.subject.name_fr
    subj_ar = schedule.group.subject.name_ar

    time_str = f"{schedule.start_time.strftime('%H:%M')} - {schedule.end_time.strftime('%H:%M')}"
    room_fr = schedule.room.name_fr if schedule.room else "Salle principale"
    room_ar = schedule.room.name_ar if schedule.room else "القاعة الرئيسية"
    coach_fr = schedule.trainer_name_fr or "L'entraîneur de l'Académie"
    coach_ar = schedule.trainer_name_ar or "مدرب الأكاديمية"

    if lang == "ar":
        message = (
            f"السلام عليكم ورحمة الله السيد(ة) {p_name_ar}،\n\n"
            f"♟️ تذكير بحصة اليوم في *أكاديمية جينيوس للشطرنج* :\n"
            f"👤 التلميذ(ة) : *{st_name_ar}*\n"
            f"📚 النشاط : *{subj_ar}* ({grp_ar})\n"
            f"🕒 التوقيت اليوم : *{time_str}*\n"
            f"🏛️ القاعة : {room_ar}\n"
            f"👨‍🏫 المؤطر(ة) : {coach_ar}\n\n"
            f"يرجى الحرص على الحضور 5 دقائق قبل الموعد. نتمنى لأبنائنا حصة ممتعة ومفيدة ! 🌟\n"
            f"📍 سيدي قاسم / الرباط • الموقع: https://geniuschess.ma"
        )
    else:
        message = (
            f"Bonjour M./Mme {p_name_fr},\n\n"
            f"♟️ *Rappel de Séance — Genius Chess Academy* :\n"
            f"👤 Élève : *{st_name_fr}*\n"
            f"📚 Activité : *{subj_fr}* ({grp_fr})\n"
            f"🕒 Horaire aujourd'hui : *{time_str}*\n"
            f"🏛️ Salle : {room_fr}\n"
            f"👨‍🏫 Formateur : {coach_fr}\n\n"
            f"Merci de veiller à la ponctualité de votre enfant (5 min avant le cours). Excellente séance ! 🌟\n"
            f"📍 Sidi Kacem / Rabat • Site Web: https://geniuschess.ma"
        )
    return message


def is_day_cancelled(target_date):
    if target_date is None:
        target_date = date.today()
    return SessionCancellation.objects.filter(date=target_date, cancel_all_day=True).exists()


def is_schedule_cancelled(schedule, target_date):
    if target_date is None:
        target_date = date.today()
    if is_day_cancelled(target_date):
        return True
    return SessionCancellation.objects.filter(schedule=schedule, date=target_date).exists()


def cancel_day(target_date, reason=""):
    if target_date is None:
        target_date = date.today()
    obj, _ = SessionCancellation.objects.get_or_create(
        date=target_date,
        cancel_all_day=True,
        defaults={'reason': reason}
    )
    return obj


def restore_day(target_date):
    if target_date is None:
        target_date = date.today()
    SessionCancellation.objects.filter(date=target_date, cancel_all_day=True).delete()


def cancel_schedule(schedule, target_date, reason=""):
    if target_date is None:
        target_date = date.today()
    obj, _ = SessionCancellation.objects.get_or_create(
        schedule=schedule,
        date=target_date,
        cancel_all_day=False,
        defaults={'reason': reason}
    )
    return obj


def restore_schedule(schedule, target_date):
    if target_date is None:
        target_date = date.today()
    SessionCancellation.objects.filter(schedule=schedule, date=target_date).delete()


def build_whatsapp_cancellation_text(schedule, student, lang="fr", reason=""):
    parent = student.parent
    p_name_fr = parent.full_name_fr if parent else "Parent"
    p_name_ar = parent.full_name_ar if parent else "ولي الأمر"
    st_name_fr = student.get_full_name("fr")
    st_name_ar = student.get_full_name("ar")

    grp_fr = schedule.group.name_fr
    grp_ar = schedule.group.name_ar
    subj_fr = schedule.group.subject.name_fr
    subj_ar = schedule.group.subject.name_ar
    time_str = f"{schedule.start_time.strftime('%H:%M')} - {schedule.end_time.strftime('%H:%M')}"

    reason_fr = f"\nMotif : {reason}" if reason else ""
    reason_ar = f"\nالسبب : {reason}" if reason else ""

    if lang == "ar":
        message = (
            f"السلام عليكم ورحمة الله السيد(ة) {p_name_ar}،\n\n"
            f"⚠️ *إشعار بإلغاء الحصة — أكاديمية جينيوس للشطرنج* :\n"
            f"👤 التلميذ(ة) : *{st_name_ar}*\n"
            f"📚 النشاط : *{subj_ar}* ({grp_ar})\n"
            f"🕒 التوقيت : *{time_str}*\n"
            f"{reason_ar}\n"
            f"نحيطكم علماً بأن هذه الحصة قد تم *إلغاؤها استثنائياً* اليوم. نعتذر عن هذا التغيير ونشكركم على حسن تفهمكم. 🙏\n"
            f"📍 سيدي قاسم / الرباط • الموقع: https://geniuschess.ma"
        )
    else:
        message = (
            f"Bonjour M./Mme {p_name_fr},\n\n"
            f"⚠️ *Avis d'Annulation de Séance — Genius Chess Academy* :\n"
            f"👤 Élève : *{st_name_fr}*\n"
            f"📚 Activité : *{subj_fr}* ({grp_fr})\n"
            f"🕒 Horaire initial : *{time_str}*\n"
            f"{reason_fr}\n"
            f"Nous vous informons que cette séance est *exceptionnellement annulée* aujourd'hui. Nous vous prions de nous excuser pour ce désagrément et vous remercions de votre compréhension. 🙏\n"
            f"📍 Sidi Kacem / Rabat • Site Web: https://geniuschess.ma"
        )
    return message


def get_daily_sessions_reminders(target_date=None):
    """
    Gathers all sessions scheduled for the given target date (defaults to today)
    and prepares reminder packages for each enrolled student and parent.
    Includes cancellation detection.
    """
    if target_date is None:
        target_date = date.today()

    day_of_week = target_date.weekday()
    schedules = SessionSchedule.objects.filter(day_of_week=day_of_week).select_related(
        'group', 'group__subject', 'room'
    ).order_by('start_time')

    day_cancelled = is_day_cancelled(target_date)
    reminders_data = []

    for sch in schedules:
        group = sch.group
        students = group.students.filter(active=True).select_related('parent', 'parent__user')
        sch_cancelled = day_cancelled or is_schedule_cancelled(sch, target_date)

        for st in students:
            parent = st.parent
            if not parent:
                continue

            lang = getattr(parent, 'preferred_language', 'fr') or 'fr'
            phone = parent.phone
            wa_phone = format_phone_for_whatsapp(phone)
            msg_text = build_whatsapp_reminder_text(sch, st, lang=lang)
            encoded_msg = urllib.parse.quote(msg_text)
            # WhatsApp Click to Chat URL (standard format wa.me, works seamlessly on Web and Mobile)
            wa_url = f"https://wa.me/{wa_phone}?text={encoded_msg}" if wa_phone else ""

            # Cancellation text & URL
            cancel_msg_text = build_whatsapp_cancellation_text(sch, st, lang=lang)
            encoded_cancel_msg = urllib.parse.quote(cancel_msg_text)
            cancellation_url = f"https://wa.me/{wa_phone}?text={encoded_cancel_msg}" if wa_phone else ""

            reminders_data.append({
                'id': f"{sch.id}_{st.id}",
                'schedule': sch,
                'student': st,
                'parent': parent,
                'target_date': target_date,
                'time_str': f"{sch.start_time.strftime('%H:%M')} - {sch.end_time.strftime('%H:%M')}",
                'language': lang,
                'phone_raw': phone,
                'whatsapp_phone': wa_phone,
                'message_text': msg_text,
                'whatsapp_url': wa_url,
                'cancellation_text': cancel_msg_text,
                'cancellation_url': cancellation_url,
                'is_cancelled': sch_cancelled,
                'group_color': group.get_color(),
            })

    return reminders_data


def send_whatsapp_via_gateway(phone, message):
    """
    Sends a WhatsApp message via an external API Gateway if configured in settings.
    Supports WAHA (local or remote), UltraMsg, Wasapi, Green API or generic Webhook.
    """
    import json
    import urllib.request
    import urllib.error

    gateway_url = getattr(settings, 'WHATSAPP_GATEWAY_URL', '').strip()
    token = getattr(settings, 'WHATSAPP_TOKEN', '').strip()
    instance_id = getattr(settings, 'WHATSAPP_INSTANCE_ID', '').strip()
    session_name = getattr(settings, 'WHATSAPP_SESSION_NAME', 'default').strip()

    if not (gateway_url or (token and instance_id)):
        return {'success': False, 'error': 'No WhatsApp Gateway configured.'}

    wa_phone = format_phone_for_whatsapp(phone)
    if not wa_phone:
        return {'success': False, 'error': 'Invalid phone number.'}

    try:
        # 1. WAHA (WhatsApp HTTP API - local or remote)
        if ':3000' in gateway_url or 'sendText' in gateway_url or 'waha' in gateway_url:
            url = gateway_url if gateway_url.endswith('/api/sendText') else f"{gateway_url.rstrip('/')}/api/sendText"
            payload = json.dumps({
                'session': session_name or 'default',
                'chatId': f"{wa_phone}@c.us",
                'text': message,
            }).encode('utf-8')
            headers = {
                'Content-Type': 'application/json',
            }
            if token:
                headers['X-Api-Key'] = token
            req = urllib.request.Request(url, data=payload, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as resp:
                res_data = json.loads(resp.read().decode('utf-8'))
                return {'success': True, 'response': res_data, 'sent_to': wa_phone}

        # 2. UltraMsg
        elif 'ultramsg.com' in gateway_url or instance_id:
            url = gateway_url if gateway_url else f"https://api.ultramsg.com/{instance_id}/messages/chat"
            payload = urllib.parse.urlencode({
                'token': token,
                'to': f"+{wa_phone}",
                'body': message,
            }).encode('utf-8')
            req = urllib.request.Request(url, data=payload, headers={'Content-Type': 'application/x-www-form-urlencoded'})
            with urllib.request.urlopen(req, timeout=10) as resp:
                res_data = json.loads(resp.read().decode('utf-8'))
                return {'success': True, 'response': res_data, 'sent_to': wa_phone}

        # 3. Generic JSON Webhook
        else:
            payload = json.dumps({'phone': wa_phone, 'message': message, 'token': token}).encode('utf-8')
            req = urllib.request.Request(gateway_url, data=payload, headers={'Content-Type': 'application/json'})
            with urllib.request.urlopen(req, timeout=10) as resp:
                return {'success': True, 'sent_to': wa_phone}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def dispatch_daily_whatsapp_reminders(target_date=None):
    """
    Automatic dispatcher executed at 13:00 daily (via cron or admin button).
    Dispatches in-app notifications to parents and sends WhatsApp messages if API gateway is configured.
    Skips any session or day marked as cancelled by admin.
    """
    if target_date is None:
        target_date = date.today()

    if is_day_cancelled(target_date):
        return {
            'total_reminders': 0,
            'notifications_created': 0,
            'whatsapp_sent_via_api': 0,
            'items': [],
            'date': target_date,
            'day_cancelled': True,
        }

    items = get_daily_sessions_reminders(target_date)
    created_notifs = 0
    wa_sent_via_api = 0

    for item in items:
        # Skip if session is cancelled
        if item.get('is_cancelled'):
            continue

        parent = item['parent']
        user = parent.user if parent else None
        if not user:
            continue

        sch = item['schedule']
        st = item['student']
        time_str = item['time_str']

        title_fr = f"🕒 Rappel Séance du Jour ({time_str})"
        title_ar = f"🕒 تذكير بحصة اليوم ({time_str})"
        
        # Check if notification already created today for this session
        existing = Notification.objects.filter(
            recipient=user,
            notification_type='session_reminder',
            created_at__date=target_date,
            message_fr__contains=st.get_full_name('fr')
        ).exists()

        if not existing:
            msg_fr = build_whatsapp_reminder_text(sch, st, lang='fr')
            msg_ar = build_whatsapp_reminder_text(sch, st, lang='ar')
            Notification.objects.create(
                recipient=user,
                title_fr=title_fr,
                title_ar=title_ar,
                message_fr=msg_fr,
                message_ar=msg_ar,
                notification_type='session_reminder'
            )
            created_notifs += 1

            # Dispatch via Gateway if configured
            res_gateway = send_whatsapp_via_gateway(item['whatsapp_phone'], item['message_text'])
            if res_gateway.get('success'):
                wa_sent_via_api += 1

    active_items = [i for i in items if not i.get('is_cancelled')]
    return {
        'total_reminders': len(active_items),
        'notifications_created': created_notifs,
        'whatsapp_sent_via_api': wa_sent_via_api,
        'items': items,
        'date': target_date,
        'day_cancelled': False,
    }
