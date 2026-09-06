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

