from datetime import date
from decimal import Decimal
from django.db import migrations


def sync_all_conventions_and_discounts(apps, schema_editor):
    Student = apps.get_model('academy', 'Student')
    Invoice = apps.get_model('finance', 'Invoice')
    Payment = apps.get_model('finance', 'Payment')

    # 1. Parcourir tous les élèves actifs ayant une convention
    for st in Student.objects.filter(active=True):
        if not getattr(st, 'has_convention', False) or getattr(st, 'discount_value', Decimal('0.00')) <= Decimal('0.00'):
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

        # Mettre à jour toutes les factures non totalement soldées de cet élève
        for inv in Invoice.objects.filter(student=st, is_exempt=False):
            if inv.amount_paid == Decimal('0.00'):
                inv.original_amount = base_fee
                inv.discount_amount = discount
                inv.amount_due = final_fee
                inv.status = 'unpaid'
                inv.save()
            elif inv.amount_paid > Decimal('0.00') and inv.amount_paid < final_fee:
                inv.original_amount = base_fee
                inv.discount_amount = discount
                inv.amount_due = final_fee
                inv.status = 'partial'
                inv.save()


def reverse_sync(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('finance', '0009_fix_ahddoune_and_reconciliation'),
    ]

    operations = [
        migrations.RunPython(sync_all_conventions_and_discounts, reverse_sync),
    ]
