content = """from django.db import models
from decimal import Decimal
from academy.models import Student, Group, User
from core.i18n import FRENCH_MONTHS, ARABIC_MONTHS

class Invoice(models.Model):
    STATUS_CHOICES = [
        ('paid', 'Réglé / مؤدى'),
        ('partial', 'Partiel / أداء جزئي'),
        ('unpaid', 'Non réglé / غير مؤدى'),
    ]
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='invoices')
    group = models.ForeignKey(Group, on_delete=models.CASCADE)
    period_month = models.PositiveIntegerField()
    period_year = models.PositiveIntegerField(default=2026)
    amount_due = models.DecimalField(max_digits=10, decimal_places=2)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='unpaid')
    due_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    def get_balance(self):
        return max(Decimal('0.00'), self.amount_due - self.amount_paid)

    def is_overdue(self):
        return self.get_balance() > Decimal('0.00')

    def get_period_label(self, lang='fr'):
        if lang == 'ar':
            month_name = ARABIC_MONTHS.get(self.period_month, str(self.period_month))
            return f"{month_name} {self.period_year}"
        month_name = FRENCH_MONTHS.get(self.period_month, str(self.period_month))
        return f"{month_name.capitalize()} {self.period_year}"

    def get_status_label(self, lang='fr'):
        labels = {
            'paid': {'fr': 'Réglé', 'ar': 'مؤدى بالكامل'},
            'partial': {'fr': 'Partiel', 'ar': 'أداء جزئي'},
            'unpaid': {'fr': 'Non réglé', 'ar': 'غير مؤدى'},
        }
        return labels.get(self.status, {}).get(lang, self.status)

    def __str__(self):
        return f"Facture {self.student.registration_number} - {self.get_period_label('fr')} ({self.status})"


class Payment(models.Model):
    METHOD_CHOICES = [
        ('cash', 'Espèces / نقداً'),
        ('transfer', 'Virement bancaire / تحويل بنكي'),
        ('check', 'Chèque / شيك'),
    ]
    receipt_number = models.CharField(max_length=50, unique=True)
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='payments')
    invoice = models.ForeignKey(Invoice, on_delete=models.SET_NULL, null=True, blank=True, related_name='payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_date = models.DateField()
    payment_method = models.CharField(max_length=20, choices=METHOD_CHOICES, default='cash')
    reference = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def get_method_label(self, lang='fr'):
        labels = {
            'cash': {'fr': 'Espèces', 'ar': 'نقداً'},
            'transfer': {'fr': 'Virement bancaire', 'ar': 'تحويل بنكي'},
            'check': {'fr': 'Chèque', 'ar': 'شيك'},
        }
        return labels.get(self.payment_method, {}).get(lang, self.payment_method)

    def __str__(self):
        return f"Reçu #{self.receipt_number} - {self.student.get_full_name('fr')} ({self.amount} DH)"
"""

with open('finance/models.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('Created finance/models.py')
