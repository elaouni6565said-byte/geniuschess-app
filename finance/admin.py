from django.contrib import admin
from .models import Invoice, Payment, PaymentExemption

@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('id', 'student', 'group', 'period_month', 'period_year', 'amount_due', 'amount_paid', 'status', 'is_exempt')
    list_filter = ('period_year', 'period_month', 'status', 'is_exempt')
    search_fields = ('student__first_name_fr', 'student__last_name_fr', 'student__registration_number')

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('receipt_number', 'student', 'amount', 'payment_date', 'payment_method')
    search_fields = ('receipt_number', 'student__first_name_fr', 'student__last_name_fr', 'reference')

@admin.register(PaymentExemption)
class PaymentExemptionAdmin(admin.ModelAdmin):
    list_display = ('student', 'period_month', 'period_year', 'reason', 'created_at')
    list_filter = ('period_year', 'period_month')
    search_fields = ('student__first_name_fr', 'student__last_name_fr', 'reason')
