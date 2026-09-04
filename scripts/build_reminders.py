content = """from decimal import Decimal
from datetime import date
from finance.models import Invoice
from academy.models import Notification

def generate_monthly_reminders(current_date=None):
    \"\"\"
    Automated 10th-of-the-month reminder generator.
    Dispatches notifications strictly in each parent's preferred language.
    \"\"\"
    if current_date is None:
        current_date = date.today()
        
    overdue_invoices = Invoice.objects.filter(
        status__in=['unpaid', 'partial']
    ).select_related('student', 'student__parent', 'student__parent__user')

    sent_records = []
    
    for inv in overdue_invoices:
        balance = inv.get_balance()
        if balance <= Decimal('0.00'):
            continue
            
        student = inv.student
        parent = student.parent
        user = parent.user
        if not user:
            continue
            
        lang = getattr(parent, 'preferred_language', 'fr') or 'fr'
        period_fr = inv.get_period_label('fr')
        period_ar = inv.get_period_label('ar')
        student_name_fr = student.get_full_name('fr')
        student_name_ar = student.get_full_name('ar')
        
        # Format amounts
        amount_fr = f"{balance:,.2f}".replace(",", " ").replace(".", ",")
        amount_ar = f"{balance:,.2f}".replace(",", " ").replace(".", ",")

        title_fr = "⚠️ Rappel de paiement"
        body_fr = f"Votre mensualité ({period_fr}) présente un reliquat de {amount_fr} DH pour l'élève {student_name_fr}."
        
        title_ar = "⚠️ تذكير بالأداء"
        body_ar = f"تتوفر لديكم مستحقات شهرية متبقية قدرها {amount_ar} درهم عن شهر {period_ar} لفائدة التلميذ {student_name_ar}."

        notif = Notification.objects.create(
            recipient=user,
            title_fr=title_fr,
            title_ar=title_ar,
            message_fr=body_fr,
            message_ar=body_ar,
            notification_type='reminder'
        )
        sent_records.append({
            'notification_id': notif.id,
            'parent_name': parent.get_name(lang),
            'student_name': student.get_full_name(lang),
            'language': lang,
            'balance': balance,
            'message': body_ar if lang == 'ar' else body_fr,
        })
        
    return sent_records
"""

with open('finance/reminders.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('Created finance/reminders.py')
