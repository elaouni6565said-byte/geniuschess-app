from datetime import date
from decimal import Decimal
from django.db import migrations


def fix_september_exact_invoices(apps, schema_editor):
    Student = apps.get_model('academy', 'Student')
    Invoice = apps.get_model('finance', 'Invoice')
    Group = apps.get_model('academy', 'Group')

    # 1. Supprimer les factures erronées de Septembre pour IMRANE BAALACHE et Majd el miles
    for bad_name in ['BAALACHE', 'miles']:
        bad_students = Student.objects.filter(last_name_fr__icontains=bad_name)
        for s in bad_students:
            Invoice.objects.filter(student_id=s.id, period_month=9, period_year=2026, amount_paid=Decimal('0.00')).delete()

    # 2. Configurer et rétablir avec exactitude les 3 élèves redevables de Septembre (Total = 550 DH)
    # BELMAHJOUB KARIM: 200 DH
    # BELMAHJOUB TAHA: 200 DH
    # AHDOUN AMIN: 150 DH
    target_students_config = [
        ('BELMAHJOUB', 'KARIM', Decimal('200.00')),
        ('BELMAHJOUB', 'TAHA', Decimal('200.00')),
        ('AHDOUN', 'AMIN', Decimal('150.00')),
    ]

    due_date = date(2026, 9, 15)

    for last_q, first_q, expected_amount in target_students_config:
        st = Student.objects.filter(
            last_name_fr__icontains=last_q,
            first_name_fr__icontains=first_q
        ).first()

        if not st:
            # Recherche plus souple par nom de famille
            st = Student.objects.filter(last_name_fr__icontains=last_q).first()

        if st:
            first_grp = st.groups.first() or Group.objects.first()
            inv, created = Invoice.objects.get_or_create(
                student_id=st.id,
                period_month=9,
                period_year=2026,
                defaults={
                    'group': first_grp,
                    'original_amount': expected_amount,
                    'discount_amount': Decimal('0.00'),
                    'amount_due': expected_amount,
                    'amount_paid': Decimal('0.00'),
                    'status': 'unpaid',
                    'is_exempt': False,
                    'due_date': due_date
                }
            )
            if not created:
                inv.amount_due = expected_amount
                inv.status = 'unpaid'
                inv.is_exempt = False
                inv.amount_paid = Decimal('0.00')
                inv.save()


def reverse_fix(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('finance', '0007_cleanup_unattended_invoices'),
    ]

    operations = [
        migrations.RunPython(fix_september_exact_invoices, reverse_fix),
    ]
