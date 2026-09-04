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
