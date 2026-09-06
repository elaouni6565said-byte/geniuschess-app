from django.db import models
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

    def update_totals(self):
        total_paid = self.payments.aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')
        self.amount_paid = total_paid
        if total_paid >= self.amount_due:
            self.status = 'paid'
        elif total_paid > Decimal('0.00'):
            self.status = 'partial'
        else:
            self.status = 'unpaid'
        self.save(update_fields=['amount_paid', 'status'])
        return self.status

    def get_period_label(self, lang='fr'):
        if lang == 'ar':
            month_name = ARABIC_MONTHS.get(self.period_month, str(self.period_month))
            return f"{month_name} {self.period_year}"
        month_name = FRENCH_MONTHS.get(self.period_month, str(self.period_month))
        return f"{month_name.capitalize()} {self.period_year}"

    @property
    def period_label_fr(self):
        return self.get_period_label('fr')

    @property
    def period_label_ar(self):
        return self.get_period_label('ar')

    def get_status_label(self, lang='fr'):
        labels = {
            'paid': {'fr': 'Réglé', 'ar': 'مؤدى بالكامل'},
            'partial': {'fr': 'Partiel', 'ar': 'أداء جزئي'},
            'unpaid': {'fr': 'Non réglé', 'ar': 'غير مؤدى'},
        }
        return labels.get(self.status, {}).get(lang, self.status)

    @property
    def status_label_fr(self):
        return self.get_status_label('fr')

    @property
    def status_label_ar(self):
        return self.get_status_label('ar')

    def get_localized(self, field, lang='fr'):
        if field == 'period':
            return self.get_period_label(lang)
        if field == 'status':
            return self.get_status_label(lang)
        return str(getattr(self, field, ''))

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

    @property
    def method_label_fr(self):
        return self.get_method_label('fr')

    @property
    def method_label_ar(self):
        return self.get_method_label('ar')

    def get_localized(self, field, lang='fr'):
        if field == 'method':
            return self.get_method_label(lang)
        return str(getattr(self, field, ''))

    def save(self, *args, **kwargs):
        # If invoice not specified, auto-link to student's pending invoice
        if not self.invoice_id and self.student_id:
            pending_inv = Invoice.objects.filter(
                student_id=self.student_id,
                status__in=['unpaid', 'partial']
            ).order_by('due_date', 'id').first()
            if pending_inv:
                self.invoice = pending_inv
        super().save(*args, **kwargs)
        if self.invoice:
            self.invoice.update_totals()

    def delete(self, *args, **kwargs):
        inv = self.invoice
        res = super().delete(*args, **kwargs)
        if inv:
            inv.update_totals()
        return res

    def __str__(self):
        return f"Reçu #{self.receipt_number} - {self.student.get_full_name('fr')} ({self.amount} DH)"


class ExpenseCategory(models.Model):
    name_fr = models.CharField(max_length=100, verbose_name="Nom (Français)")
    name_ar = models.CharField(max_length=100, verbose_name="Nom (Arabe)")
    icon = models.CharField(max_length=20, default="💸", verbose_name="Icône / Emoji")
    color = models.CharField(max_length=20, default="#0284C7", verbose_name="Couleur Badge (Hex)")
    is_active = models.BooleanField(default=True, verbose_name="Actif")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Catégorie de dépense"
        verbose_name_plural = "Catégories de dépenses"
        ordering = ['name_fr']

    def get_name(self, lang='fr'):
        if lang == 'ar' and self.name_ar:
            return self.name_ar
        return self.name_fr

    def __str__(self):
        return f"{self.icon} {self.name_fr} ({self.name_ar})"


class Expense(models.Model):
    PAYMENT_METHOD_CHOICES = [
        ('cash', 'Espèces / نقداً'),
        ('check', 'Chèque / شيك'),
        ('transfer', 'Virement bancaire / تحويل بنكي'),
    ]

    title = models.CharField(max_length=200, verbose_name="Libellé / Titre de la dépense")
    category = models.ForeignKey(ExpenseCategory, on_delete=models.CASCADE, related_name='expenses', verbose_name="Catégorie")
    amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Montant (DH)")
    expense_date = models.DateField(verbose_name="Date de la dépense")
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, default='cash', verbose_name="Mode de règlement")
    beneficiary = models.CharField(max_length=150, blank=True, verbose_name="Bénéficiaire / Fournisseur")
    invoice_number = models.CharField(max_length=100, blank=True, verbose_name="N° Facture / Référence")
    receipt_file = models.FileField(upload_to='expenses/%Y/%m/', blank=True, null=True, verbose_name="Justificatif (Scan / Reçu / Facture)")
    notes = models.TextField(blank=True, verbose_name="Notes / Observations")
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Enregistré par")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Dépense"
        verbose_name_plural = "Dépenses"
        ordering = ['-expense_date', '-id']

    def get_method_label(self, lang='fr'):
        labels = {
            'cash': {'fr': 'Espèces', 'ar': 'نقداً'},
            'check': {'fr': 'Chèque', 'ar': 'شيك'},
            'transfer': {'fr': 'Virement bancaire', 'ar': 'تحويل بنكي'},
        }
        return labels.get(self.payment_method, {}).get(lang, self.payment_method)

    @property
    def method_label_fr(self):
        return self.get_method_label('fr')

    @property
    def method_label_ar(self):
        return self.get_method_label('ar')

    def __str__(self):
        return f"{self.title} - {self.amount} DH ({self.expense_date})"
