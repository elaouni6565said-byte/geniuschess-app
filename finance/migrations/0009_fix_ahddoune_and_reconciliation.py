from datetime import date
from decimal import Decimal
from django.db import migrations


def fix_ahddoune_and_reconciliation(apps, schema_editor):
    Student = apps.get_model('academy', 'Student')
    Invoice = apps.get_model('finance', 'Invoice')
    Group = apps.get_model('academy', 'Group')

    # 1. Rétablir avec certitude le 3ème élève impayé de Septembre : amine ahddoune (150 DH)
    st = Student.objects.filter(
        registration_number='GCA-2026-049'
    ).first()

    if not st:
        st = Student.objects.filter(last_name_fr__icontains='ahddoune').first()

    if st:
        first_grp = st.groups.first() or Group.objects.first()
        inv, _ = Invoice.objects.update_or_create(
            student_id=st.id,
            period_month=9,
            period_year=2026,
            defaults={
                'group': first_grp,
                'original_amount': Decimal('150.00'),
                'discount_amount': Decimal('0.00'),
                'amount_due': Decimal('150.00'),
                'amount_paid': Decimal('0.00'),
                'status': 'unpaid',
                'is_exempt': False,
                'due_date': date(2026, 9, 15)
            }
        )

    # 2. Re-vérifier Karim Belmahjoub et Taha Belmahjoub (200 DH chacun)
    for reg, amt in [('GCA-2026-033', Decimal('200.00')), ('GCA-2026-032', Decimal('200.00'))]:
        s = Student.objects.filter(registration_number=reg).first()
        if s:
            first_grp = s.groups.first() or Group.objects.first()
            Invoice.objects.update_or_create(
                student_id=s.id,
                period_month=9,
                period_year=2026,
                defaults={
                    'group': first_grp,
                    'original_amount': amt,
                    'discount_amount': Decimal('0.00'),
                    'amount_due': amt,
                    'amount_paid': Decimal('0.00'),
                    'status': 'unpaid',
                    'is_exempt': False,
                    'due_date': date(2026, 9, 15)
                }
            )

    # 3. Nettoyer automatiquement le reçu doublon #REC-2026-0040 de Jad Elarbaoui (300 DH)
    Payment = apps.get_model('finance', 'Payment')
    dup = Payment.objects.filter(receipt_number='REC-2026-0040').first()
    if dup:
        inv = dup.invoice
        dup.delete()
        if inv:
            tot = sum((p.amount for p in inv.payments.all()), Decimal('0.00'))
            inv.amount_paid = tot
            if inv.amount_paid >= inv.amount_due and inv.amount_due > Decimal('0.00'):
                inv.status = 'paid'
            elif inv.amount_paid > Decimal('0.00'):
                inv.status = 'partial'
            else:
                inv.status = 'unpaid'
            inv.save()


def reverse_fix(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('finance', '0008_fix_september_exact_invoices'),
    ]

    operations = [
        migrations.RunPython(fix_ahddoune_and_reconciliation, reverse_fix),
    ]
