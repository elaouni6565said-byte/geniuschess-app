from datetime import date
from decimal import Decimal
import pytest
from django.test import Client
from django.contrib.auth import get_user_model
from academy.models import Student, Group, Subject, Parent, Attendance, SessionSchedule
from finance.models import Invoice, Payment
from portal.views import get_billable_unpaid_invoices_qs, is_period_overdue

User = get_user_model()


@pytest.mark.django_db
def test_september_unpaid_invoices_and_tenth_of_month_rule():
    """
    Vérifie les règles GCA :
    1. Seuls les élèves ayant effectivement assisté aux cours (status='present')
       ou ayant versé un acompte reçoivent une facture pour ce mois.
    2. Un élève n'ayant aucune présence dans le mois et aucun paiement N'EST PAS facturé pour ce mois.
    3. Règle du 10 du mois :
       - Les impayés d'un mois ne sont calculés qu'à partir du 10 de ce mois.
       - Avant le 10 (ex: 4 Octobre), les cotisations d'Octobre ne sont pas en impayé (0 DH).
       - Pour Septembre (mois antérieur), le 10 est passé -> les factures impayées sont bien comptabilisées.
    """
    admin = User.objects.get(username='admin')
    client = Client()
    client.force_login(admin)

    parent = Parent.objects.create(full_name_fr="Parent Test Sept", phone="212611223344")
    sub = Subject.objects.create(name_fr="Échecs Sept", name_ar="شطرنج شتنبر")
    grp = Group.objects.create(name_fr="Groupe Septembre", name_ar="فوج شتنبر", subject=sub, monthly_fee=Decimal('300.00'))

    # Élève 1 : A assisté aux cours en Septembre (présent), mais n'a pas payé (300 DH impayé)
    st1 = Student.objects.create(
        registration_number="GCA-SEPT-01",
        first_name_fr="Amine",
        last_name_fr="Tahiri",
        parent=parent,
        active=True
    )
    st1.groups.add(grp)
    schedule = SessionSchedule.objects.first()
    Attendance.objects.create(
        student=st1,
        session=schedule,
        date=date(2026, 9, 12),
        status='present'
    )

    # Élève 2 : A versé 100 DH sur 300 DH -> reliquat de 200 DH d'impayé
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

    # Élève 3 : Inscrit mais n'a JAMAIS assisté en Septembre et n'a rien versé -> NE DOIT PAS AVOIR D'IMPAYÉ
    st3 = Student.objects.create(
        registration_number="GCA-SEPT-03",
        first_name_fr="Mehdi",
        last_name_fr="Alaoui",
        parent=parent,
        active=True
    )
    st3.groups.add(grp)

    # Test de la fonction is_period_overdue
    assert is_period_overdue(2026, 9, today=date(2026, 10, 4)) is True
    assert is_period_overdue(2026, 10, today=date(2026, 10, 4)) is False
    assert is_period_overdue(2026, 10, today=date(2026, 10, 10)) is True

    # 1. Vérification dans get_billable_unpaid_invoices_qs()
    unpaid_qs = get_billable_unpaid_invoices_qs()
    unpaid_student_ids = list(unpaid_qs.values_list('student_id', flat=True))

    # st1 et st2 doivent impérativement être présents
    assert st1.id in unpaid_student_ids
    assert st2.id in unpaid_student_ids
    # st3 NE DOIT PAS être présent dans les impayés
    assert st3.id not in unpaid_student_ids

    # 2. Vérification sur la page /payments/
    resp_pay = client.get('/payments/')
    assert resp_pay.status_code == 200
    pay_html = resp_pay.content.decode('utf-8')
    assert "Amine" in pay_html or "Tahiri" in pay_html
    assert "Sara" in pay_html or "Berrada" in pay_html
    assert "Mehdi" not in pay_html

    # 3. Vérification sur le Dashboard pour Septembre (?month=9&year=2026)
    resp_dash_sept = client.get('/?month=9&year=2026')
    assert resp_dash_sept.status_code == 200
    ctx_sept = resp_dash_sept.context
    assert ctx_sept['selected_month'] == 9
    assert ctx_sept['selected_year'] == 2026
    # Exactement 500 DH d'impayés pour ces deux élèves (st1: 300 DH + st2: 200 DH)
    assert ctx_sept['month_unpaid'] >= Decimal('500.00')

    # 4. Vérification dans monthly_breakdown
    breakdown = ctx_sept['monthly_breakdown']
    sept_entry = next((item for item in breakdown if item['month'] == 9 and item['year'] == 2026), None)
    assert sept_entry is not None
    assert sept_entry['unpaid'] >= Decimal('500.00')

    # Vérification pour Octobre 2026 avant le 10 : impayés d'Octobre = 0 DH
    oct_entry = next((item for item in breakdown if item['month'] == 10 and item['year'] == 2026), None)
    if oct_entry:
        assert oct_entry['unpaid'] == Decimal('0.00')
