from decimal import Decimal
from django.db import migrations, models


def sync_all_past_conventions(apps, schema_editor):
    Student = apps.get_model('academy', 'Student')
    Invoice = apps.get_model('finance', 'Invoice')
    Payment = apps.get_model('finance', 'Payment')

    for st in Student.objects.filter(has_convention=True):
        if getattr(st, 'discount_value', Decimal('0.00')) <= Decimal('0.00'):
            continue

        groups = st.groups.all()
        base_fee = sum(g.monthly_fee for g in groups if g.monthly_fee > 0) or Decimal('0.00')
        if base_fee == Decimal('0.00') and groups.exists():
            base_fee = Decimal('150.00')

        disc_type = getattr(st, 'discount_type', 'custom_fee')
        disc_val = getattr(st, 'discount_value', Decimal('0.00'))
        if disc_type == 'custom_fee':
            final_fee = max(Decimal('0.00'), disc_val)
            discount = max(Decimal('0.00'), base_fee - final_fee)
        elif disc_type == 'percentage':
            pct = min(Decimal('100.00'), max(Decimal('0.00'), disc_val))
            discount = round((base_fee * pct) / Decimal('100.00'), 2)
            final_fee = max(Decimal('0.00'), base_fee - discount)
        elif disc_type == 'fixed_discount':
            discount = min(base_fee, max(Decimal('0.00'), disc_val))
            final_fee = max(Decimal('0.00'), base_fee - discount)
        else:
            discount = Decimal('0.00')
            final_fee = base_fee

        # Mettre à jour TOUTES les factures de cet élève (même payées) pour refléter la remise convention
        for inv in Invoice.objects.filter(student=st, is_exempt=False):
            inv.original_amount = base_fee
            inv.discount_amount = discount
            inv.amount_due = final_fee
            inv.save()

            # Recalculer les totaux payés et statut
            total_paid = inv.payments.aggregate(t=models.Sum('amount'))['t'] if hasattr(inv, 'payments') else None
            # En migration, on interroge Payment directement :
            total_p = Payment.objects.filter(invoice=inv).aggregate(t=models.Sum('amount'))['t'] or Decimal('0.00')
            inv.amount_paid = total_p
            if total_p >= final_fee:
                inv.status = 'paid'
            elif total_p > Decimal('0.00'):
                inv.status = 'partial'
            else:
                inv.status = 'unpaid'
            inv.save()


def reverse_sync(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('finance', '0010_sync_all_conventions_and_discounts'),
    ]

    operations = [
        migrations.RunPython(sync_all_past_conventions, reverse_sync),
    ]
