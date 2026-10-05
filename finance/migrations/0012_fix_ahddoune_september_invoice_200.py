from decimal import Decimal
from django.db import migrations


def fix_ahddoune_200(apps, schema_editor):
    Student = apps.get_model('academy', 'Student')
    Invoice = apps.get_model('finance', 'Invoice')
    Group = apps.get_model('academy', 'Group')

    st = Student.objects.filter(registration_number='GCA-2026-049').first()
    if not st:
        st = Student.objects.filter(last_name_fr__icontains='ahddoune').first()

    if st:
        # Si l'élève est rattaché à un groupe à 150 DH ou pas de groupe à 200 DH,
        # vérifier s'il existe un groupe à 200 DH ou s'assurer que ses frais sont 200 DH
        inv = Invoice.objects.filter(student=st, period_month=9, period_year=2026).first()
        if inv:
            inv.original_amount = Decimal('200.00')
            inv.discount_amount = Decimal('0.00')
            inv.amount_due = Decimal('200.00')
            inv.save()
        else:
            first_grp = st.groups.first() or Group.objects.first()
            from datetime import date
            Invoice.objects.create(
                student=st,
                group=first_grp,
                period_month=9,
                period_year=2026,
                original_amount=Decimal('200.00'),
                discount_amount=Decimal('0.00'),
                amount_due=Decimal('200.00'),
                amount_paid=Decimal('0.00'),
                status='unpaid',
                is_exempt=False,
                due_date=date(2026, 9, 15)
            )


def reverse_fix(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('finance', '0011_sync_all_past_convention_invoices'),
    ]

    operations = [
        migrations.RunPython(fix_ahddoune_200, reverse_fix),
    ]
