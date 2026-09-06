from django.contrib import admin
from finance.models import Invoice, Payment, ExpenseCategory, Expense, FinancialClosing

@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('student', 'group', 'period_month', 'period_year', 'amount_due', 'amount_paid', 'status', 'due_date')
    list_filter = ('status', 'period_year', 'period_month', 'group')
    search_fields = ('student__first_name_fr', 'student__last_name_fr', 'student__registration_number')

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('receipt_number', 'student', 'amount', 'payment_date', 'payment_method', 'created_by')
    list_filter = ('payment_method', 'payment_date')
    search_fields = ('receipt_number', 'student__first_name_fr', 'student__last_name_fr', 'reference')

@admin.register(ExpenseCategory)
class ExpenseCategoryAdmin(admin.ModelAdmin):
    list_display = ('icon', 'name_fr', 'name_ar', 'color', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name_fr', 'name_ar')

@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'amount', 'expense_date', 'payment_method', 'beneficiary', 'created_by')
    list_filter = ('category', 'payment_method', 'expense_date')
    search_fields = ('title', 'beneficiary', 'invoice_number', 'notes')

@admin.register(FinancialClosing)
class FinancialClosingAdmin(admin.ModelAdmin):
    list_display = ('title', 'period_type', 'year', 'month', 'total_collected', 'total_expense', 'net_result', 'status', 'is_locked', 'closing_date')
    list_filter = ('period_type', 'year', 'status', 'is_locked')
    search_fields = ('title', 'treasurer_notes', 'president_notes')

