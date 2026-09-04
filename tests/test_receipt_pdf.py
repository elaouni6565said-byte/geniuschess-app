import pytest
from datetime import date
from decimal import Decimal
from finance.models import Payment
from finance.receipt_pdf import generate_receipt_pdf
from academy.models import Student, User

def test_generate_receipt_pdf_all_variants():
    payment = Payment.objects.first()
    if not payment:
        student = Student.objects.first()
        admin = User.objects.filter(is_superuser=True).first()
        payment = Payment.objects.create(
            receipt_number="REC-2026-9999",
            student=student,
            payment_date=date.today(),
            amount=Decimal("300.00"),
            payment_method="cash",
            created_by=admin
        )
    assert payment is not None

    pdf_fr = generate_receipt_pdf(payment, lang='fr')
    assert pdf_fr.startswith(b'%PDF-')
    assert len(pdf_fr) > 1000

    pdf_ar = generate_receipt_pdf(payment, lang='ar')
    assert pdf_ar.startswith(b'%PDF-')
    assert len(pdf_ar) > 1000

    pdf_bi = generate_receipt_pdf(payment, lang='bilingual')
    assert pdf_bi.startswith(b'%PDF-')
    assert len(pdf_bi) > 1000
