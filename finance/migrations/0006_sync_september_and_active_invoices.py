from datetime import date
from decimal import Decimal
from django.db import migrations


def sync_september_and_active_invoices(apps, schema_editor):
    Student = apps.get_model('academy', 'Student')
    Invoice = apps.get_model('finance', 'Invoice')
    Payment = apps.get_model('finance', 'Payment')
    PaymentExemption = apps.get_model('finance', 'PaymentExemption')

    # Mois clés de la rentrée scolaire 2026-2027 à synchroniser
    periods = [(2026, 9), (2026, 10)]

    for p_year, p_month in periods:
        p_due_date = date(p_year, p_month, 15)

        for st in Student.objects.filter(active=True):
            groups = st.groups.all()
            if not groups.exists():
                continue

            first_grp = groups.first()
            inv = Invoice.objects.filter(student_id=st.id, period_month=p_month, period_year=p_year).first()

            # Calcul des tarifs
            base_fee = sum(g.monthly_fee for g in groups if g.monthly_fee > 0) or Decimal('0.00')
            if base_fee == Decimal('0.00'):
                base_fee = Decimal('150.00')

            discount_amount = Decimal('0.00')
            final_fee = base_fee
            if getattr(st, 'has_convention', False) and getattr(st, 'discount_value', Decimal('0.00')) > Decimal('0.00'):
                disc_type = getattr(st, 'discount_type', 'custom_fee')
                disc_val = getattr(st, 'discount_value', Decimal('0.00'))
                if disc_type == 'custom_fee':
                    final_fee = max(Decimal('0.00'), disc_val)
                    discount_amount = max(Decimal('0.00'), base_fee - final_fee)
                elif disc_type == 'percentage':
                    pct = min(Decimal('100.00'), max(Decimal('0.00'), disc_val))
                    discount_amount = (base_fee * pct) / Decimal('100.00')
                    final_fee = max(Decimal('0.00'), base_fee - discount_amount)
                elif disc_type == 'fixed_discount':
                    discount_amount = min(base_fee, max(Decimal('0.00'), disc_val))
                    final_fee = max(Decimal('0.00'), base_fee - discount_amount)

            # Exonération
            ex = PaymentExemption.objects.filter(student_id=st.id, period_month=p_month, period_year=p_year).first()
            is_exempt = bool(ex)
            ex_reason = ex.reason if ex else ""

            if not inv:
                if is_exempt:
                    inv = Invoice.objects.create(
                        student=st,
                        group=first_grp,
                        period_month=p_month,
                        period_year=p_year,
                        original_amount=base_fee,
                        discount_amount=base_fee,
                        amount_due=Decimal('0.00'),
                        amount_paid=Decimal('0.00'),
                        status='exempt',
                        is_exempt=True,
                        exemption_reason=ex_reason or "Exonération accordée",
                        due_date=p_due_date
                    )
                else:
                    inv = Invoice.objects.create(
                        student=st,
                        group=first_grp,
                        period_month=p_month,
                        period_year=p_year,
                        original_amount=base_fee,
                        discount_amount=discount_amount,
                        amount_due=final_fee,
                        amount_paid=Decimal('0.00'),
                        status='unpaid',
                        is_exempt=False,
                        exemption_reason='',
                        due_date=p_due_date
                    )

            # Rattacher les paiements orphelins ou correspondants
            related_payments = Payment.objects.filter(student_id=st.id, period_month=p_month, period_year=p_year)
            for p in related_payments:
                if p.invoice_id != inv.id:
                    p.invoice = inv
                    p.save(update_fields=['invoice'])

            # Mettre à jour les totaux et le statut de la facture
            tot_paid = sum((p.amount for p in inv.payments.all()), Decimal('0.00'))
            inv.amount_paid = tot_paid
            if inv.is_exempt:
                inv.status = 'exempt'
                inv.amount_due = Decimal('0.00')
            elif inv.amount_paid >= inv.amount_due and inv.amount_due > Decimal('0.00'):
                inv.status = 'paid'
            elif inv.amount_paid > Decimal('0.00'):
                inv.status = 'partial'
            else:
                inv.status = 'unpaid'
            inv.save()


def reverse_sync(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('finance', '0005_sync_payments_with_invoice_period'),
    ]

    operations = [
        migrations.RunPython(sync_september_and_active_invoices, reverse_sync),
    ]
