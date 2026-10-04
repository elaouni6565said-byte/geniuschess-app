import pytest
from decimal import Decimal
from datetime import date
from academy.models import Student, Parent, User, Group, Notification
from finance.models import Invoice
from finance.reminders import generate_monthly_reminders

@pytest.mark.django_db
def test_reminders_respect_parent_language():
    """Verifies 10th-of-the-month reminders respect parent's chosen language (47.10 & 47.11)."""
    Notification.objects.all().delete()
    
    # Ensure parents with AR and FR preferences have pending invoices
    st_ar = Student.objects.first()
    p_ar = st_ar.parent
    p_ar.preferred_language = 'ar'
    p_ar.save()

    st_fr = Student.objects.exclude(parent=p_ar).first() or st_ar
    p_fr = st_fr.parent
    p_fr.preferred_language = 'fr'
    p_fr.save()

    grp = Group.objects.first()
    Invoice.objects.get_or_create(
        student=st_ar,
        group=grp,
        period_month=9,
        period_year=2026,
        defaults={
            'amount_due': Decimal('300.00'),
            'amount_paid': Decimal('0.00'),
            'status': 'unpaid',
            'due_date': date(2026, 9, 10),
        }
    )
    Invoice.objects.get_or_create(
        student=st_fr,
        group=grp,
        period_month=9,
        period_year=2026,
        defaults={
            'amount_due': Decimal('350.00'),
            'amount_paid': Decimal('100.00'),
            'status': 'partial',
            'due_date': date(2026, 9, 10),
        }
    )

    # Run reminders
    records = generate_monthly_reminders()
    assert len(records) > 0

    # Check notification for Arabic parent
    ar_record = next((r for r in records if r['language'] == 'ar'), None)
    if ar_record:
        assert "درهم" in ar_record['message']
        assert "تذكير" in ar_record['message'] or "تتوفر" in ar_record['message']
        assert "DH" not in ar_record['message']

    # Check notification for French parent
    fr_record = next((r for r in records if r['language'] == 'fr'), None)
    if fr_record:
        assert "DH" in fr_record['message']
        assert "reliquat" in fr_record['message'] or "rappel" in fr_record['message'].lower()


@pytest.mark.django_db
def test_whatsapp_unpaid_reminders_authorization_and_15th_rule():
    """
    Validates:
    1. build_unpaid_reminder_message contains 15th-of-the-month deadline in FR and AR.
    2. send_single_unpaid_whatsapp_reminder and send_bulk_authorized_reminders functions.
    3. Console endpoints: GET /payments/unpaid-reminders/, POST send-bulk, POST send single.
    """
    from django.test import Client
    from finance.whatsapp_payment_reminders import (
        build_unpaid_reminder_message,
        get_unpaid_reminder_chat_url,
        send_single_unpaid_whatsapp_reminder,
        send_bulk_authorized_reminders
    )

    client = Client()
    admin = User.objects.get(username='admin')
    client.force_login(admin)

    student = Student.objects.first()
    grp = Group.objects.first()
    assert student is not None and grp is not None

    inv, created = Invoice.objects.get_or_create(
        student=student,
        group=grp,
        period_month=9,
        period_year=2026,
        defaults={
            'amount_due': Decimal('400.00'),
            'amount_paid': Decimal('100.00'),
            'status': 'partial',
            'due_date': date(2026, 9, 15),
        }
    )
    inv.amount_due = Decimal('400.00')
    inv.amount_paid = Decimal('100.00')
    inv.status = 'partial'
    inv.save()

    # 1. Test message contents with explicit '15' rule
    msg_fr = build_unpaid_reminder_message(inv, lang='fr')
    assert "15" in msg_fr
    assert "Genius Chess Academy" in msg_fr
    assert "300" in msg_fr  # remaining balance 400 - 100

    msg_ar = build_unpaid_reminder_message(inv, lang='ar')
    assert "15" in msg_ar
    assert "جمعية الشطرنج القاسمي" in msg_ar
    assert "300" in msg_ar

    chat_url = get_unpaid_reminder_chat_url(inv, lang='fr')
    assert "wa.me" in chat_url

    # 2. Test send_single_unpaid_whatsapp_reminder
    res_single = send_single_unpaid_whatsapp_reminder(inv, force=True)
    assert res_single['success'] is True
    assert Notification.objects.filter(recipient=student.parent.user, notification_type='unpaid_whatsapp_reminder').exists()

    # 3. Test bulk authorized reminders
    res_bulk = send_bulk_authorized_reminders([inv.id])
    assert res_bulk['sent_count'] == 1

    # 4. HTTP GET console view
    resp_console = client.get('/payments/unpaid-reminders/?month=9&year=2026')
    assert resp_console.status_code == 200
    assert resp_console.context['total_count'] >= 1
    assert resp_console.context['period_15_status'] in ['normal', 'due_soon', 'overdue']

    # 5. HTTP POST bulk send
    resp_post_bulk = client.post(
        '/payments/unpaid-reminders/send-bulk/',
        data={'selected_invoices': [inv.id]}
    )
    assert resp_post_bulk.status_code == 302

    # 6. HTTP POST single send
    resp_post_single = client.post(
        f'/payments/unpaid-reminders/send/{inv.id}/'
    )
    assert resp_post_single.status_code == 302


@pytest.mark.django_db
def test_robotique_n3_schedule_and_sunday_0930_notification():
    """
    Vérifie la règle :
    - Séance Robotique N3 : Dimanche matin 10h30 à 12h00.
    - Heure de notification WhatsApp des parents : 09h30 chaque dimanche.
    """
    from datetime import time, date
    from django.core.management import call_command
    from academy.models import Group, SessionSchedule
    from academy.whatsapp_reminders import get_daily_sessions_reminders, dispatch_daily_whatsapp_reminders

    # Récupérer le groupe Robotique Dimanche N3
    grp = Group.objects.filter(name_fr__icontains='robot', schedules__day_of_week=6).first()
    assert grp is not None
    assert "N3" in grp.name_fr or "Robotique" in grp.name_fr

    # Récupérer la séance
    sched = SessionSchedule.objects.filter(group=grp, day_of_week=6).first()
    assert sched is not None
    assert sched.day_of_week == 6  # Dimanche
    assert sched.start_time == time(10, 30)
    assert sched.end_time == time(12, 0)
    assert sched.notification_time == time(9, 30)
    assert sched.get_notification_time() == time(9, 30)

    # Tester un dimanche donné (par exemple le 27 Septembre 2026, qui est un dimanche : weekday=6)
    sunday_date = date(2026, 9, 27)
    assert sunday_date.weekday() == 6

    reminders = get_daily_sessions_reminders(sunday_date)
    robotics_reminders = [r for r in reminders if r['schedule'].group == grp]
    if len(robotics_reminders) > 0:
        for rem in robotics_reminders:
            assert rem['time_str'] == "10:30 - 12:00"
            assert rem['notification_time'] == "09:30"
            assert "10:30" in rem['message_text']
            assert "12:00" in rem['message_text']

    # Tester le dispatch avec filtre horaire
    res_early = dispatch_daily_whatsapp_reminders(target_date=sunday_date, target_time="09:00")
    res_ontime = dispatch_daily_whatsapp_reminders(target_date=sunday_date, target_time="09:30")
    assert res_ontime['total_reminders'] >= len(robotics_reminders)

    # Tester la commande de management avec argument --time 09:30
    call_command('send_daily_session_reminders', date='2026-09-27', time='09:30')


@pytest.mark.django_db
def test_robotique_wednesday_and_sunday_schedules():
    """
    Vérifie qu'il y a bien :
    - Deux séances de Robotique le Mercredi (14h30-16h00 et 17h30-19h00).
    - Une séance de Robotique N3 le Dimanche (10h30-12h00, notif 09h30).
    """
    from datetime import time, date
    from academy.models import Group, SessionSchedule
    from academy.whatsapp_reminders import get_daily_sessions_reminders

    # Vérification séances Mercredi
    wed_schedules = SessionSchedule.objects.filter(
        group__subject__name_fr__icontains='robot',
        day_of_week=2
    ).order_by('start_time')
    assert wed_schedules.count() >= 2
    s1 = wed_schedules.filter(start_time=time(14, 30)).first()
    s2 = wed_schedules.filter(start_time=time(17, 30)).first()
    assert s1 is not None and s1.end_time == time(16, 0)
    assert s2 is not None and s2.end_time == time(19, 0)

    # Vérification séance Dimanche
    sun_schedules = SessionSchedule.objects.filter(
        group__subject__name_fr__icontains='robot',
        day_of_week=6
    )
    assert sun_schedules.count() >= 1
    sun = sun_schedules.filter(start_time=time(10, 30)).first()
    assert sun is not None and sun.end_time == time(12, 0)
    assert sun.notification_time == time(9, 30)

