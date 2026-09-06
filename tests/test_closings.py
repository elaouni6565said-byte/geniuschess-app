import pytest
from decimal import Decimal
from datetime import date
from django.test import Client
from academy.models import User, Student, Parent, Subject, Group
from finance.models import FinancialClosing, Payment, Expense, ExpenseCategory, Invoice
from finance.annual_report_pdf import generate_annual_report_pdf
from portal.excel_export import export_annual_financial_report_to_excel
import openpyxl
import io


@pytest.fixture
def admin_client():
    admin = User.objects.create_superuser(
        username="admin_closing",
        password="adminpassword123",
        role="admin"
    )
    client = Client()
    client.force_login(admin)
    return client, admin


@pytest.mark.django_db
def test_financial_closing_model_and_calculations(admin_client):
    _, admin_user = admin_client
    sub = Subject.objects.create(name_fr="Échecs", name_ar="الشطرنج")
    grp = Group.objects.create(name_fr="Groupe A", subject=sub)
    parent = Parent.objects.create(full_name_fr="Parent Clot", phone="+212600000000")
    st = Student.objects.create(registration_number="GCA-CLOT-01", first_name_fr="Ali", last_name_fr="Fassi", parent=parent, active=True)
    st.groups.add(grp)

    # Nettoyer d'éventuelles données de démo existantes pour garantir l'isolation du test
    Payment.objects.all().delete()
    Expense.objects.all().delete()

    # 1. Créer paiements en 2026
    Payment.objects.create(
        receipt_number="REC-CLOT-01",
        student=st,
        amount=Decimal("1000.00"),
        payment_date=date(2026, 5, 10),
        payment_method="cash"
    )
    Payment.objects.create(
        receipt_number="REC-CLOT-02",
        student=st,
        amount=Decimal("1500.00"),
        payment_date=date(2026, 6, 15),
        payment_method="transfer"
    )

    # 2. Créer dépenses en 2026
    cat = ExpenseCategory.objects.create(name_fr="Loyers", name_ar="كراء", icon="🏢")
    Expense.objects.create(
        title="Loyer Juin 2026",
        category=cat,
        amount=Decimal("1200.00"),
        expense_date=date(2026, 6, 2),
        payment_method="check"
    )
    Expense.objects.create(
        title="Fournitures",
        category=cat,
        amount=Decimal("300.00"),
        expense_date=date(2026, 6, 5),
        payment_method="cash"
    )

    # 3. Créer clôture annuelle 2026
    closing = FinancialClosing.objects.create(
        period_type="year",
        year=2026,
        closing_date=date(2026, 12, 31),
        initial_cash_balance=Decimal("500.00"),
        initial_bank_balance=Decimal("2000.00"),
        physical_cash_counted=Decimal("1200.00"), # Théorique = 500 + 1000 - 300 = 1200 -> écart 0
        bank_statement_balance=Decimal("2300.00"), # Théorique = 2000 + 1500 - 1200 = 2300 -> écart 0
        closed_by=admin_user
    )

    closing.compute_and_update_totals()
    closing.save()

    assert closing.total_collected_cash == Decimal("1000.00")
    assert closing.total_collected_bank == Decimal("1500.00")
    assert closing.total_collected == Decimal("2500.00")

    assert closing.total_expense_cash == Decimal("300.00")
    assert closing.total_expense_bank == Decimal("1200.00")
    assert closing.total_expense == Decimal("1500.00")

    assert closing.net_result == Decimal("1000.00")
    assert closing.theoretical_cash == Decimal("1200.00")
    assert closing.theoretical_bank == Decimal("2300.00")
    assert closing.cash_discrepancy == Decimal("0.00")
    assert closing.bank_discrepancy == Decimal("0.00")
    assert "Exercice 2026" in closing.get_period_label("fr")


@pytest.mark.django_db
def test_annual_report_pdf_generation(admin_client):
    _, admin_user = admin_client
    closing = FinancialClosing.objects.create(
        period_type="year",
        year=2026,
        closing_date=date(2026, 12, 31),
        initial_cash_balance=Decimal("100.00"),
        initial_bank_balance=Decimal("1000.00"),
        total_collected=Decimal("5000.00"),
        total_expense=Decimal("3000.00"),
        net_result=Decimal("2000.00"),
        theoretical_cash=Decimal("1500.00"),
        theoretical_bank=Decimal("2500.00"),
        physical_cash_counted=Decimal("1500.00"),
        bank_statement_balance=Decimal("2500.00"),
        closed_by=admin_user
    )

    # Test PDF French
    pdf_fr = generate_annual_report_pdf(closing, lang="fr")
    assert pdf_fr.startswith(b"%PDF-")
    assert len(pdf_fr) > 1000

    # Test PDF Arabic
    pdf_ar = generate_annual_report_pdf(closing, lang="ar")
    assert pdf_ar.startswith(b"%PDF-")
    assert len(pdf_ar) > 1000


@pytest.mark.django_db
def test_multi_sheet_excel_export():
    cat = ExpenseCategory.objects.create(name_fr="Matériel", name_ar="عتاد", icon="♟️")
    Expense.objects.create(
        title="Échiquiers",
        category=cat,
        amount=Decimal("800.00"),
        expense_date=date(2026, 3, 15),
        payment_method="cash"
    )

    excel_bytes = export_annual_financial_report_to_excel(2026, lang="fr")
    wb = openpyxl.load_workbook(io.BytesIO(excel_bytes))

    sheet_names = wb.sheetnames
    assert "Bilan Financier AG" in sheet_names
    assert "Recettes Encaissées" in sheet_names
    assert "Dépenses Acquittées" in sheet_names
    assert "Journal Trésorerie" in sheet_names

    ws1 = wb["Bilan Financier AG"]
    assert "RAPPORT FINANCIER EXERCICE 2026" in ws1["A1"].value
    assert "Sidi Kacem" in ws1["A2"].value


@pytest.mark.django_db
def test_closing_views_and_locking(admin_client):
    client, admin_user = admin_client

    # 1. Create via view
    post_data = {
        "period_type": "year",
        "year": "2026",
        "month": "",
        "title": "Clôture Test 2026",
        "closing_date": "2026-12-31",
        "status": "closed",
        "initial_cash_balance": "200.00",
        "initial_bank_balance": "500.00",
        "physical_cash_counted": "200.00",
        "bank_statement_balance": "500.00",
    }
    resp = client.post("/closings/add/", post_data)
    assert resp.status_code == 302
    closing = FinancialClosing.objects.get(title="Clôture Test 2026")
    assert closing.year == 2026
    assert not closing.is_locked

    # 2. Detail view
    resp_detail = client.get(f"/closings/{closing.id}/")
    assert resp_detail.status_code == 200
    assert "Clôture Test 2026" in resp_detail.content.decode("utf-8")

    # 3. Toggle lock
    resp_lock = client.post(f"/closings/{closing.id}/toggle-lock/")
    assert resp_lock.status_code == 302
    closing.refresh_from_db()
    assert closing.is_locked is True

    # 4. Try delete locked closing (should be refused)
    resp_del_locked = client.post(f"/closings/{closing.id}/delete/")
    assert resp_del_locked.status_code == 302
    assert FinancialClosing.objects.filter(id=closing.id).exists()

    # 5. Unlock and delete
    client.post(f"/closings/{closing.id}/toggle-lock/")
    closing.refresh_from_db()
    assert closing.is_locked is False
    resp_del = client.post(f"/closings/{closing.id}/delete/")
    assert resp_del.status_code == 302
    assert not FinancialClosing.objects.filter(id=closing.id).exists()


@pytest.mark.django_db
def test_closing_downloads(admin_client):
    client, admin_user = admin_client
    closing = FinancialClosing.objects.create(
        period_type="year",
        year=2026,
        closing_date=date(2026, 12, 31),
        title="Clôture Téléchargement",
        closed_by=admin_user
    )

    # PDF AG
    resp_pdf = client.get(f"/closings/{closing.id}/pdf/?lang=fr")
    assert resp_pdf.status_code == 200
    assert resp_pdf["Content-Type"] == "application/pdf"
    assert "Rapport_Financier_AG" in resp_pdf["Content-Disposition"]

    # Excel AG
    resp_excel = client.get(f"/closings/{closing.id}/excel/?lang=fr")
    assert resp_excel.status_code == 200
    assert resp_excel["Content-Type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert "Bilan_Financier_AG" in resp_excel["Content-Disposition"]
