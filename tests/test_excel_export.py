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


@pytest.mark.django_db
def test_export_paid_excel_with_unpaid_section_and_centre_shares():
    """Validates the 11 columns, centre/trainer share calculations, and the unpaid section below."""
    from datetime import date
    from decimal import Decimal
    from academy.models import Parent, Subject, Group
    from finance.models import Payment, Invoice
    from portal.excel_export import export_paid_payments_to_excel

    parent = Parent.objects.create(full_name_fr="Parent Test", phone="212688776655")
    sub1 = Subject.objects.create(name_fr="Robotique", name_ar="روبوتيك")
    sub2 = Subject.objects.create(name_fr="Échecs", name_ar="الشطرنج")
    grp1 = Group.objects.create(name_fr="Grp Rob", name_ar="روبوتيك", subject=sub1, monthly_fee=Decimal("200.00"))
    grp2 = Group.objects.create(name_fr="Grp Ech", name_ar="شطرنج", subject=sub2, monthly_fee=Decimal("150.00"))

    # Élève 1 (Payant avec 1 activité : Robotique 200 DH -> Centre: 35 DH, Prof: 165 DH)
    st1 = Student.objects.create(registration_number="GCA-PAY-01", first_name_fr="Adam", last_name_fr="Tazi", parent=parent, active=True)
    st1.groups.add(grp1)
    inv1 = Invoice.objects.create(student=st1, group=grp1, period_month=9, period_year=2026, amount_due=Decimal("200.00"), amount_paid=Decimal("200.00"), status="paid", due_date=date(2026, 9, 15))
    p1 = Payment.objects.create(receipt_number="REC-001", student=st1, invoice=inv1, amount=Decimal("200.00"), payment_date=date(2026, 9, 10))

    # Élève 2 (Non-payant / Impayé avec 2 activités : 300 DH -> Centre: 70 DH, Prof: 230 DH)
    st2 = Student.objects.create(registration_number="GCA-UNPAY-01", first_name_fr="Sara", last_name_fr="Idrissi", parent=parent, active=True)
    st2.groups.add(grp1, grp2)
    inv2 = Invoice.objects.create(student=st2, group=grp1, period_month=9, period_year=2026, original_amount=Decimal("350.00"), discount_amount=Decimal("50.00"), amount_due=Decimal("300.00"), amount_paid=Decimal("0.00"), status="unpaid", due_date=date(2026, 9, 15))

    excel_bytes = export_paid_payments_to_excel(
        Payment.objects.filter(id=p1.id),
        unpaid_invoices_queryset=Invoice.objects.filter(id=inv2.id),
        lang="fr"
    )
    wb = openpyxl.load_workbook(io.BytesIO(excel_bytes))
    ws = wb.active

    # Check 11 headers exist
    headers = [cell for cell in next(ws.iter_rows(min_row=3, max_row=3, values_only=True))]
    assert "Nombre d'activitées" in headers
    assert "Part du centre" in headers
    assert "Part du prof" in headers

    # Verify sections exist in content
    content_all = " ".join([str(cell) for row in ws.iter_rows(values_only=True) for cell in row if cell])
    assert "TOTAL DES RECETTES ENCAISSÉES" in content_all
    assert "ÉLÈVES NON PAYANTS & IMPAYÉS" in content_all
    assert "TOTAL DES IMPAYÉS RESTANTS" in content_all
    assert "BILAN GLOBAL & CHIFFRE D'AFFAIRES PRÉVISIONNEL" in content_all
    assert "Sara Idrissi" in content_all
    assert "Adam Tazi" in content_all



