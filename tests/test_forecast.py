import pytest
from decimal import Decimal
from datetime import date
from django.test import Client
from academy.models import Student, Parent, Group, Subject, User
from finance.models import Invoice, Payment
from finance.forecast import get_monthly_financial_forecast


@pytest.mark.django_db
def test_get_monthly_financial_forecast_calculation():
    """
    Verifie les calculs previsionnels et la partition des encaissements au 15 du mois.
    """
    sub, _ = Subject.objects.get_or_create(name_fr="Échecs", defaults={"name_ar": "الشطرنج", "color": "#0A192F"})
    grp, _ = Group.objects.get_or_create(name_fr="Groupe Test", defaults={"subject": sub, "name_ar": "مجموعة تجريبية"})
    
    parent_user = User.objects.create_user(username="parent_fc", password="pwd", role="parent")
    parent = Parent.objects.create(user=parent_user, full_name_fr="Parent Test", phone="+212600000000")
    
    st1 = Student.objects.create(
        registration_number="GCA-FC-01",
        first_name_fr="Adil",
        last_name_fr="Alami",
        parent=parent,
        active=True
    )
    st1.groups.add(grp)

    st2 = Student.objects.create(
        registration_number="GCA-FC-02",
        first_name_fr="Sami",
        last_name_fr="Bennani",
        parent=parent,
        active=True
    )
    st2.groups.add(grp)

    # Facture 1 : 500 DH - payee le 10 du mois (avant le 15)
    inv1 = Invoice.objects.create(
        student=st1,
        group=grp,
        period_month=10,
        period_year=2026,
        amount_due=Decimal("500.00"),
        amount_paid=Decimal("500.00"),
        status="paid",
        due_date=date(2026, 10, 15)
    )
    Payment.objects.create(
        receipt_number="REC-FC-01",
        student=st1,
        invoice=inv1,
        amount=Decimal("500.00"),
        payment_date=date(2026, 10, 10),
        payment_method="cash"
    )

    # Facture 2 : 500 DH - partiellement payee 200 DH le 20 du mois (apres le 15)
    inv2 = Invoice.objects.create(
        student=st2,
        group=grp,
        period_month=10,
        period_year=2026,
        amount_due=Decimal("500.00"),
        amount_paid=Decimal("200.00"),
        status="partial",
        due_date=date(2026, 10, 15)
    )
    Payment.objects.create(
        receipt_number="REC-FC-02",
        student=st2,
        invoice=inv2,
        amount=Decimal("200.00"),
        payment_date=date(2026, 10, 20),
        payment_method="cash"
    )

    data = get_monthly_financial_forecast(month=10, year=2026, lang="fr")

    # Assertions
    assert data["total_expected"] == Decimal("1000.00")
    assert data["total_collected"] == Decimal("700.00")
    assert data["total_remaining"] == Decimal("300.00")
    assert data["recovery_rate"] == 70.0

    # Verification speciale de la regle du 15
    assert data["collected_before_15"] == Decimal("500.00")
    assert data["collected_after_15"] == Decimal("200.00")
    assert data["rate_at_15"] == 50.0  # 500 / 1000 * 100

    assert data["paid_invoices_count"] == 1
    assert data["partial_invoices_count"] == 1
    assert len(data["history"]) == 6
    assert len(data["activities_data"]) >= 1


@pytest.mark.django_db
def test_financial_forecast_view_permissions_and_render():
    """
    Verifie l'acces admin et le rendu du template HTML.
    """
    client = Client()
    admin = User.objects.get(username="admin")
    client.force_login(admin)

    resp = client.get("/payments/forecast/?month=10&year=2026")
    assert resp.status_code == 200
    assert "total_expected" in resp.context
    assert "rate_at_15" in resp.context
    assert "deadline_badge" in resp.context

    html = resp.content.decode("utf-8")
    assert "Recouvrement" in html or "الاستخلاص" in html
    assert "15" in html
