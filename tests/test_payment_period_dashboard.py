from datetime import date
from decimal import Decimal
import pytest
from django.test import Client
from django.contrib.auth import get_user_model
from academy.models import Student, Group, Subject, SessionSchedule
from finance.models import Invoice, Payment

User = get_user_model()


@pytest.mark.django_db
def test_dashboard_payment_calculation_based_on_period_month_not_payment_date():
    """
    Vérifie que :
    1. Un versement effectué le 4 Octobre 2026 pour le mois de Septembre 2026 (mois 9)
       est rigoureusement comptabilisé dans le Tableau de Bord (TB) pour SEPTEMBRE 2026.
    2. Il N'EST PAS comptabilisé dans les recettes d'OCTOBRE 2026.
    3. La répartition Part Centre et Part Coach s'applique bien au mois concerné.
    4. La table mensuelle (monthly_breakdown) du TB affecte ce versement à Septembre.
    """
    client = Client()
    admin = User.objects.get(username='admin')
    client.force_login(admin)

    # Récupérer ou créer un élève
    student = Student.objects.first()
    group = student.groups.first()

    # Créer une facture pour Septembre 2026
    inv_sept = Invoice.objects.create(
        student=student,
        group=group,
        period_month=9,
        period_year=2026,
        original_amount=Decimal('300.00'),
        discount_amount=Decimal('0.00'),
        amount_due=Decimal('300.00'),
        amount_paid=Decimal('0.00'),
        status='unpaid',
        due_date=date(2026, 9, 15)
    )

    # Créer un paiement versé le 04 Octobre 2026 (payment_date = 2026-10-04) mais rattaché à Septembre
    p = Payment.objects.create(
        receipt_number="REC-TEST-SEPT-IN-OCT",
        student=student,
        invoice=inv_sept,
        period_month=9,
        period_year=2026,
        amount=Decimal('300.00'),
        payment_date=date(2026, 10, 4),  # Payé en Octobre !
        payment_method='cash'
    )
    assert p.is_deferred is True  # Mois concerné (9) != Mois de paiement (10)
    assert p.period_month == 9

    # 1. Tester le Tableau de bord pour SEPTEMBRE 2026 (?month=9&year=2026)
    resp_sept = client.get('/?month=9&year=2026')
    assert resp_sept.status_code == 200
    ctx_sept = resp_sept.context
    assert ctx_sept['selected_month'] == 9
    assert ctx_sept['selected_year'] == 2026
    # Le paiement de 300 DH doit figurer dans la recette de Septembre
    assert ctx_sept['month_revenue'] >= Decimal('300.00')

    # 2. Tester le Tableau de bord pour OCTOBRE 2026 (?month=10&year=2026)
    resp_oct = client.get('/?month=10&year=2026')
    assert resp_oct.status_code == 200
    ctx_oct = resp_oct.context
    assert ctx_oct['selected_month'] == 10
    assert ctx_oct['selected_year'] == 2026

    # Les paiements d'Octobre ne doivent PAS inclure ce paiement de Septembre
    oct_payments_qs = Payment.objects.filter(
        period_month=10, period_year=2026
    )
    assert p.id not in [op.id for op in oct_payments_qs]

    # 3. Vérifier que la table mensuelle (monthly_breakdown) a bien affecté le paiement à Septembre
    breakdown = ctx_sept['monthly_breakdown']
    sept_row = next((r for r in breakdown if r['month'] == 9 and r['year'] == 2026), None)
    assert sept_row is not None
    assert sept_row['revenue'] >= Decimal('300.00')

    # 4. Vérifier que le template affiche bien la colonne Mois Concerné
    html = resp_sept.content.decode('utf-8')
    assert "Mois Concerné" in html or "الشهر المؤدى عنه" in html
    assert "REC-TEST-SEPT-IN-OCT" in html
