from django.db import models
from django.utils import timezone
from decimal import Decimal
from academy.models import Student, Group, User
from core.i18n import FRENCH_MONTHS, ARABIC_MONTHS

class PaymentExemption(models.Model):
    """
    Exonération de paiement mensuel accordée à un élève pour un mois/année spécifique.
    (Ex: Bourse d'excellence, convention 100%, mois offert, situation sociale).
    """
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='payment_exemptions')
    period_month = models.PositiveIntegerField(verbose_name="Mois (1-12)")
    period_year = models.PositiveIntegerField(default=2026, verbose_name="Année")
    reason = models.CharField(max_length=255, blank=True, default="Exonération accordée", verbose_name="Motif / Cause")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('student', 'period_month', 'period_year')
        ordering = ['-period_year', '-period_month']
        verbose_name = "Exonération de paiement"
        verbose_name_plural = "Exonérations de paiement"

    def __str__(self):
        return f"Exonération {self.student.registration_number} - {self.period_month}/{self.period_year} ({self.reason})"


class Invoice(models.Model):
    STATUS_CHOICES = [
        ('paid', 'Réglé / مؤدى'),
        ('partial', 'Partiel / أداء جزئي'),
        ('unpaid', 'Non réglé / غير مؤدى'),
        ('exempt', 'Exonéré / معفى من الأداء'),
    ]
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='invoices')
    group = models.ForeignKey(Group, on_delete=models.CASCADE)
    period_month = models.PositiveIntegerField()
    period_year = models.PositiveIntegerField(default=2026)
    original_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name="Montant de base")
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name="Réduction convention")
    amount_due = models.DecimalField(max_digits=10, decimal_places=2)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='unpaid')
    is_exempt = models.BooleanField(default=False, verbose_name="Exonéré de paiement")
    exemption_reason = models.CharField(max_length=255, blank=True, default='', verbose_name="Motif de l'exonération")
    due_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    def get_balance(self):
        if self.is_exempt or self.status == 'exempt':
            return Decimal('0.00')
        return max(Decimal('0.00'), self.amount_due - self.amount_paid)

    def is_overdue(self):
        if self.is_exempt or self.status == 'exempt':
            return False
        return self.get_balance() > Decimal('0.00')

    def update_totals(self):
        if self.is_exempt:
            self.amount_due = Decimal('0.00')
            self.status = 'exempt'
            self.save(update_fields=['amount_due', 'amount_paid', 'status', 'is_exempt'])
            return self.status
        total_paid = self.payments.aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')
        self.amount_paid = total_paid
        if total_paid >= self.amount_due:
            self.status = 'paid'
        elif total_paid > Decimal('0.00'):
            self.status = 'partial'
        else:
            self.status = 'unpaid'
        self.save(update_fields=['amount_due', 'amount_paid', 'status', 'is_exempt'])
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
            'exempt': {'fr': 'Exonéré', 'ar': 'معفى من الأداء'},
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
    period_month = models.PositiveIntegerField(null=True, blank=True, verbose_name="Mois concerné / الشهر المؤدى عنه (1-12)")
    period_year = models.PositiveIntegerField(default=2026, null=True, blank=True, verbose_name="Année concernée / السنة")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_date = models.DateField(default=timezone.localdate, blank=True)
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

    def get_period_label(self, lang='fr'):
        month = self.period_month
        year = self.period_year or 2026
        if not month and self.invoice:
            month = self.invoice.period_month
            year = self.invoice.period_year
        if not month and self.payment_date:
            month = self.payment_date.month
            year = self.payment_date.year

        if not month:
            return "Cotisation" if lang != 'ar' else "اشتراك"

        if lang == 'ar':
            month_name = ARABIC_MONTHS.get(month, str(month))
            return f"{month_name} {year}"
        month_name = FRENCH_MONTHS.get(month, str(month))
        return f"{month_name.capitalize()} {year}"

    @property
    def period_label_fr(self):
        return self.get_period_label('fr')

    @property
    def period_label_ar(self):
        return self.get_period_label('ar')

    @property
    def is_deferred(self):
        """Indique si le paiement est différé / tardif (mois ou année concerné différent de la date de paiement)."""
        if self.period_month and self.payment_date:
            target_year = self.period_year or 2026
            return (self.period_month != self.payment_date.month) or (target_year != self.payment_date.year)
        return False

    def get_localized(self, field, lang='fr'):
        if field == 'method':
            return self.get_method_label(lang)
        if field == 'period':
            return self.get_period_label(lang)
        return str(getattr(self, field, ''))

    def save(self, *args, **kwargs):
        # 0. Date de paiement par défaut si non renseignée (date de saisie)
        if not self.payment_date:
            from datetime import date
            self.payment_date = date.today()

        # 1. Remplir period_month et period_year par défaut si non spécifiés
        if not self.period_month:
            if self.invoice:
                self.period_month = self.invoice.period_month
                self.period_year = self.invoice.period_year
            elif self.payment_date:
                self.period_month = self.payment_date.month
                self.period_year = self.payment_date.year
        if not self.period_year:
            self.period_year = 2026

        # 2. Si aucune facture n'est associée explicitement, chercher UNIQUEMENT celle correspondant à l'élève et au mois concerné
        if not self.invoice_id and self.student_id:
            target_inv = Invoice.objects.filter(
                student_id=self.student_id,
                period_month=self.period_month,
                period_year=self.period_year
            ).first()
            if target_inv:
                self.invoice = target_inv

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
