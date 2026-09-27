import pytest
import io
import openpyxl
from academy.models import Student
from portal.excel_export import export_students_to_excel

@pytest.mark.django_db
def test_export_excel_bilingual_utf8():
    """Tests Excel export with mixed French and Arabic characters without corruption (47.14 & 47.15)."""
    students = Student.objects.all()
    excel_bytes = export_students_to_excel(students, lang='ar')

    wb = openpyxl.load_workbook(io.BytesIO(excel_bytes))
    ws = wb.active
    assert ws.title == "قائمة التلاميذ"
    assert ws.sheet_view.rightToLeft is True

    # Search for any student name in Arabic and French
    first_student = students.first()
    assert first_student is not None, "At least one student should exist"

    found_arabic = False
    found_french = False
    for row in ws.iter_rows(values_only=True):
        for cell in row:
            if cell and first_student.first_name_ar in str(cell):
                found_arabic = True
            if cell and first_student.first_name_fr in str(cell):
                found_french = True

    assert found_arabic, f"Arabic student name ({first_student.first_name_ar}) should be present in Excel"
    assert found_french, f"French student name ({first_student.first_name_fr}) should be present in Excel"


@pytest.mark.django_db
def test_export_paid_and_unpaid_excel():
    """Tests Excel export for paid payments and unpaid invoices with French and Arabic."""
    from finance.models import Payment, Invoice
    from portal.excel_export import export_paid_payments_to_excel, export_unpaid_invoices_to_excel

    # 1. Paid payments export
    payments = Payment.objects.all()
    excel_paid_bytes = export_paid_payments_to_excel(payments, lang='fr')
    wb_paid = openpyxl.load_workbook(io.BytesIO(excel_paid_bytes))
    ws_paid = wb_paid.active
    assert "Paiements" in ws_paid.title
    # Check header exists
    headers = [cell for cell in next(ws_paid.iter_rows(min_row=3, max_row=3, values_only=True))]
    assert any("Reçu" in str(h) for h in headers if h)
    assert any("Réduction" in str(h) or "Convention" in str(h) for h in headers if h)

    # 2. Unpaid invoices export in Arabic RTL
    invoices = Invoice.objects.filter(status__in=['unpaid', 'partial'])
    excel_unpaid_bytes = export_unpaid_invoices_to_excel(invoices, lang='ar')
    wb_unpaid = openpyxl.load_workbook(io.BytesIO(excel_unpaid_bytes))
    ws_unpaid = wb_unpaid.active
    assert ws_unpaid.sheet_view.rightToLeft is True
    assert "المستحقات" in ws_unpaid.title
    unpaid_headers = [cell for cell in next(ws_unpaid.iter_rows(min_row=3, max_row=3, values_only=True))]
    assert any("التخفيض" in str(h) or "الاتفاقية" in str(h) for h in unpaid_headers if h)


@pytest.mark.django_db
def test_export_excel_with_convention_reduction_reason():
    """Validates that a student with a convention displays the reduction motif and amount in Excel exports."""
    from datetime import date
    from decimal import Decimal
    from academy.models import Parent, Subject, Group
    from finance.models import Payment, Invoice
    from portal.excel_export import export_paid_payments_to_excel

    parent = Parent.objects.create(full_name_fr="Parent Conv", phone="212612345678")
    sub = Subject.objects.create(name_fr="Échecs", name_ar="الشطرنج")
    grp = Group.objects.create(name_fr="Groupe Pro", name_ar="المحترف", subject=sub, monthly_fee=Decimal("350.00"))
    st = Student.objects.create(
        registration_number="GCA-EXCEL-01",
        first_name_fr="Mehdi",
        last_name_fr="Alami",
        parent=parent,
        active=True,
        has_convention=True,
        convention_name="Convention Fondation OCP",
        discount_type="fixed_discount",
        discount_value=Decimal("50.00")
    )
    st.groups.add(grp)
    inv = Invoice.objects.create(
        student=st,
        group=grp,
        period_month=9,
        period_year=2026,
        original_amount=Decimal("350.00"),
        discount_amount=Decimal("50.00"),
        amount_due=Decimal("300.00"),
        amount_paid=Decimal("300.00"),
        status="paid",
        due_date=date(2026, 9, 15)
    )
    p = Payment.objects.create(
        receipt_number="REC-EXCEL-001",
        student=st,
        invoice=inv,
        amount=Decimal("300.00"),
        payment_date=date(2026, 9, 10),
        payment_method="cash"
    )

    excel_bytes = export_paid_payments_to_excel(Payment.objects.filter(id=p.id), lang="fr")
    wb = openpyxl.load_workbook(io.BytesIO(excel_bytes))
    ws = wb.active

    found_convention = False
    for row in ws.iter_rows(values_only=True):
        for cell in row:
            if cell and "Convention Fondation OCP" in str(cell) and "-50.00 DH" in str(cell):
                found_convention = True
                break

    assert found_convention, "The convention name and discount amount should be present in the payment Excel export"


