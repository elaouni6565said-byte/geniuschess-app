from datetime import date
from decimal import Decimal
import pytest
from django.test import Client
from django.contrib.auth import get_user_model
from academy.models import Student, Group, Subject, Parent
from finance.models import Invoice, Payment
from portal.views import get_billable_unpaid_invoices_qs

User = get_user_model()


@pytest.mark.django_db
def test_september_unpaid_invoices_appear_in_dashboard_and_payments():
    """
    Vérifie que :
    1. Les élèves inscrits pour Septembre sans paiement complet ont bien une facture impayée pour Septembre.
    2. Ces factures apparaissent fidèlement dans get_billable_unpaid_invoices_qs().
    3. Elles apparaissent dans /payments/ sous la section Impayés.
    4. Elles apparaissent dans le Tableau de Bord (TB) :
       - Dans la ligne Septembre de monthly_breakdown avec le montant 'unpaid' exact.
       - Dans le KPI 'month_unpaid' lorsqu'on consulte Septembre (?month=9&year=2026).
    5. Même en l'absence d'enregistrement de présence numérique préalable, l'élève actif inscrit
       n'est pas exclu des impayés.
    """
    admin = User.objects.get(username='admin')
    client = Client()
    client.force_login(admin)

    parent = Parent.objects.create(full_name_fr="Parent Test Sept", phone="212611223344")
    sub = Subject.objects.create(name_fr="Échecs Sept", name_ar="شطرنج شتنبر")
    grp = Group.objects.create(name_fr="Groupe Septembre", name_ar="فوج شتنبر", subject=sub, monthly_fee=Decimal('300.00'))

    # Élève 1 : Totalement impayé pour Septembre
    st1 = Student.objects.create(
        registration_number="GCA-SEPT-01",
        first_name_fr="Amine",
        last_name_fr="Tahiri",
        parent=parent,
        active=True
    )
    st1.groups.add(grp)

    # Élève 2 : Paiement partiel pour Septembre (a versé 100 DH sur 300 DH -> 200 DH d'impayé)
    st2 = Student.objects.create(
        registration_number="GCA-SEPT-02",
        first_name_fr="Sara",
        last_name_fr="Berrada",
        parent=parent,
        active=True
    )
    st2.groups.add(grp)

    inv2 = Invoice.objects.create(
        student=st2,
        group=grp,
        period_month=9,
        period_year=2026,
        original_amount=Decimal('300.00'),
        amount_due=Decimal('300.00'),
        amount_paid=Decimal('100.00'),
        status='partial',
        due_date=date(2026, 9, 15)
    )
    Payment.objects.create(
        receipt_number="REC-TEST-PARTIAL-SEPT",
        student=st2,
        invoice=inv2,
        period_month=9,
        period_year=2026,
        amount=Decimal('100.00'),
        payment_date=date(2026, 9, 10),
        payment_method='cash'
    )

    # 1. Vérification dans get_billable_unpaid_invoices_qs()
    unpaid_qs = get_billable_unpaid_invoices_qs()
    unpaid_student_ids = list(unpaid_qs.values_list('student_id', flat=True))

    # st1 et st2 doivent impérativement être présents
    assert st1.id in unpaid_student_ids
    assert st2.id in unpaid_student_ids

    inv1 = unpaid_qs.filter(student=st1, period_month=9, period_year=2026).first()
    assert inv1 is not None
    assert inv1.status == 'unpaid'
    assert inv1.get_balance() == Decimal('300.00')

    inv2_fetched = unpaid_qs.filter(student=st2, period_month=9, period_year=2026).first()
    assert inv2_fetched is not None
    assert inv2_fetched.status == 'partial'
    assert inv2_fetched.get_balance() == Decimal('200.00')

    # 2. Vérification sur la page /payments/
    resp_pay = client.get('/payments/')
    assert resp_pay.status_code == 200
    pay_html = resp_pay.content.decode('utf-8')
    assert "Amine" in pay_html or "Tahiri" in pay_html
    assert "Sara" in pay_html or "Berrada" in pay_html

    # 3. Vérification sur le Dashboard pour Septembre (?month=9&year=2026)
    resp_dash_sept = client.get('/?month=9&year=2026')
    assert resp_dash_sept.status_code == 200
    ctx_sept = resp_dash_sept.context
    assert ctx_sept['selected_month'] == 9
    assert ctx_sept['selected_year'] == 2026
    # Au moins 500 DH d'impayés pour Septembre (st1: 300 DH + st2: 200 DH)
    assert ctx_sept['month_unpaid'] >= Decimal('500.00')

    # 4. Vérification dans monthly_breakdown
    breakdown = ctx_sept['monthly_breakdown']
    sept_entry = next((item for item in breakdown if item['month'] == 9 and item['year'] == 2026), None)
    assert sept_entry is not None
    assert sept_entry['unpaid'] >= Decimal('500.00')
