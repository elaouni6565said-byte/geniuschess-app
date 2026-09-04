import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gca_config.settings')
django.setup()

from finance.models import Payment
from finance.receipt_pdf import generate_receipt_pdf
from portal.excel_export import export_students_to_excel
from academy.models import Student

os.makedirs('exports_samples', exist_ok=True)

payment = Payment.objects.first()

# 1. French PDF Receipt
pdf_fr = generate_receipt_pdf(payment, lang='fr')
with open('exports_samples/Recu_Paiement_FR.pdf', 'wb') as f:
    f.write(pdf_fr)

# 2. Arabic PDF Receipt (RTL)
pdf_ar = generate_receipt_pdf(payment, lang='ar')
with open('exports_samples/Recu_Paiement_AR_RTL.pdf', 'wb') as f:
    f.write(pdf_ar)

# 3. Bilingual PDF Receipt
pdf_bi = generate_receipt_pdf(payment, lang='bilingual')
with open('exports_samples/Recu_Paiement_Bilingue.pdf', 'wb') as f:
    f.write(pdf_bi)

# 4. Bilingual Excel Export
students = Student.objects.all()
excel_bytes = export_students_to_excel(students, lang='ar')
with open('exports_samples/Liste_Eleves_GCA_Arabe_RTL.xlsx', 'wb') as f:
    f.write(excel_bytes)

excel_bi_bytes = export_students_to_excel(students, lang='bilingual')
with open('exports_samples/Liste_Eleves_GCA_Bilingue.xlsx', 'wb') as f:
    f.write(excel_bi_bytes)

print("Generated all sample PDF receipts and Excel files in exports_samples/")
