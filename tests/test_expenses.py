import pytest
from decimal import Decimal
from datetime import date
from django.test import Client
from academy.models import User
from finance.models import ExpenseCategory, Expense, Payment, Invoice
from finance.forecast import get_monthly_financial_forecast
from portal.excel_export import export_expenses_to_excel
import openpyxl
import io


@pytest.fixture
def admin_client():
    admin = User.objects.create_superuser(
        username="admin_exp",
        password="adminpassword123",
        role="admin"
    )
    client = Client()
    client.force_login(admin)
    return client, admin


@pytest.mark.django_db
def test_expense_category_and_expense_creation():
    cat = ExpenseCategory.objects.create(
        name_fr="Locaux & Loyers",
        name_ar="المقرات والكراء",
        icon="🏢",
        color="#0284C7"
    )
    assert cat.get_name("fr") == "Locaux & Loyers"
    assert cat.get_name("ar") == "المقرات والكراء"
    assert "Locaux & Loyers" in str(cat)

    exp = Expense.objects.create(
        title="Loyer Salle Sidi Kacem",
        category=cat,
        amount=Decimal("2500.00"),
        expense_date=date(2026, 10, 5),
        payment_method="check",
        beneficiary="Propriétaire Local",
        invoice_number="QUITT-10-2026"
    )
    assert exp.amount == Decimal("2500.00")
    assert exp.method_label_fr == "Chèque"
    assert exp.method_label_ar == "شيك"
    assert "Loyer Salle" in str(exp)


@pytest.mark.django_db
def test_financial_forecast_with_expenses():
    cat1 = ExpenseCategory.objects.create(name_fr="Loyers", name_ar="كراء", icon="🏢", color="#0284C7")
    cat2 = ExpenseCategory.objects.create(name_fr="Matériel", name_ar="عتاد", icon="♟️", color="#D97706")

    # Dépenses d'octobre 2026
    Expense.objects.create(title="Loyer", category=cat1, amount=Decimal("1500.00"), expense_date=date(2026, 10, 2))
    Expense.objects.create(title="Pendules d'échecs", category=cat2, amount=Decimal("500.00"), expense_date=date(2026, 10, 12))

    data = get_monthly_financial_forecast(month=10, year=2026, lang="fr")

    assert data["total_expenses"] == Decimal("2000.00")
    assert data["expenses_count"] == 2
    # Recettes = 0 donc net_result = 0 - 2000 = -2000
    assert data["net_result"] == Decimal("-2000.00")
    assert len(data["categories_breakdown"]) == 2
    assert data["categories_breakdown"][0]["category"] == cat1
    assert data["categories_breakdown"][0]["amount"] == Decimal("1500.00")


@pytest.mark.django_db
def test_expenses_list_view_and_filtering(admin_client):
    client, _ = admin_client
    cat = ExpenseCategory.objects.create(name_fr="Fournitures", name_ar="لوازم", icon="📑")
    Expense.objects.create(title="Papier A4", category=cat, amount=Decimal("150.00"), expense_date=date(2026, 9, 10))
    Expense.objects.create(title="Stylos", category=cat, amount=Decimal("50.00"), expense_date=date(2026, 10, 5))

    # Vue sans filtre (mois en cours par défaut)
    resp = client.get("/expenses/")
    assert resp.status_code == 200
    assert "Registre des Dépenses" in resp.content.decode("utf-8")

    # Filtre tous les mois
    resp_all = client.get("/expenses/?month=all&year=2026")
    assert resp_all.status_code == 200
    content = resp_all.content.decode("utf-8")
    assert "Papier A4" in content
    assert "Stylos" in content


@pytest.mark.django_db
def test_expense_crud_views(admin_client):
    client, admin_user = admin_client
    cat = ExpenseCategory.objects.create(name_fr="Charges", name_ar="مصاريف", icon="⚡")

    # 1. CREATE
    post_data = {
        "title": "Facture Électricité",
        "category": cat.id,
        "amount": "320.00",
        "expense_date": "2026-09-06",
        "payment_method": "cash",
        "beneficiary": "ONEE Sidi Kacem",
        "invoice_number": "ELEC-2026-09",
        "notes": "Consommation climatisation",
    }
    resp = client.post("/expenses/add/", post_data)
    assert resp.status_code == 302
    exp = Expense.objects.get(title="Facture Électricité")
    assert exp.amount == Decimal("320.00")
    assert exp.created_by == admin_user

    # 2. EDIT
    edit_data = {
        "title": "Facture Électricité Corrigée",
        "category": cat.id,
        "amount": "350.00",
        "expense_date": "2026-09-06",
        "payment_method": "cash",
        "beneficiary": "ONEE Sidi Kacem",
        "invoice_number": "ELEC-2026-09",
        "notes": "Mise à jour",
    }
    resp_edit = client.post(f"/expenses/{exp.id}/edit/", edit_data)
    assert resp_edit.status_code == 302
    exp.refresh_from_db()
    assert exp.title == "Facture Électricité Corrigée"
    assert exp.amount == Decimal("350.00")

    # 3. DELETE
    resp_del = client.post(f"/expenses/{exp.id}/delete/")
    assert resp_del.status_code == 302
    assert not Expense.objects.filter(id=exp.id).exists()


@pytest.mark.django_db
def test_expense_categories_management(admin_client):
    client, _ = admin_client

    # Liste des catégories
    resp = client.get("/expenses/categories/")
    assert resp.status_code == 200

    # Création catégorie
    cat_data = {
        "name_fr": "Formations",
        "name_ar": "تكوينات",
        "icon": "🎓",
        "color": "#8B5CF6",
        "is_active": "on",
    }
    resp_create = client.post("/expenses/categories/", cat_data)
    assert resp_create.status_code == 302
    assert ExpenseCategory.objects.filter(name_fr="Formations").exists()


@pytest.mark.django_db
def test_export_expenses_excel():
    cat = ExpenseCategory.objects.create(name_fr="Matériel", name_ar="عتاد", icon="♟️")
    Expense.objects.create(
        title="10 Jeux d'échecs compétition",
        category=cat,
        amount=Decimal("1200.00"),
        expense_date=date(2026, 9, 1),
        payment_method="transfer",
        beneficiary="Fournisseur Échecs Maroc"
    )

    qs = Expense.objects.all()

    # 1. Export FR
    excel_fr = export_expenses_to_excel(qs, lang="fr", month=9, year=2026)
    wb_fr = openpyxl.load_workbook(io.BytesIO(excel_fr))
    ws_fr = wb_fr.active
    assert "Dépenses" in ws_fr.title
    assert "GENIUS CHESS ACADEMY" in ws_fr["A1"].value
    assert "Sidi Kacem" in ws_fr["A2"].value

    # 2. Export AR
    excel_ar = export_expenses_to_excel(qs, lang="ar", month=9, year=2026)
    wb_ar = openpyxl.load_workbook(io.BytesIO(excel_ar))
    ws_ar = wb_ar.active
    assert ws_ar.sheet_view.rightToLeft is True
    assert "سجل المصاريف" in ws_ar.title
    assert "جمعية الشطرنج القاسمي" in ws_ar["A1"].value


@pytest.mark.django_db
def test_export_expenses_view(admin_client):
    client, _ = admin_client
    cat = ExpenseCategory.objects.create(name_fr="Divers", name_ar="متفرقات", icon="📦")
    Expense.objects.create(
        title="Dépense Test View",
        category=cat,
        amount=Decimal("100.00"),
        expense_date=date(2026, 9, 2)
    )

    resp = client.get("/expenses/export-excel/?lang=fr&month=9&year=2026")
    assert resp.status_code == 200
    assert resp["Content-Type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert "Depenses_GCA" in resp["Content-Disposition"]
