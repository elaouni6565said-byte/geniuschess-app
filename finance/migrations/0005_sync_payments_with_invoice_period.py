from django.db import migrations


def sync_payments_with_invoice_period(apps, schema_editor):
    Payment = apps.get_model('finance', 'Payment')
    Invoice = apps.get_model('finance', 'Invoice')

    # 1. Aligner period_month et period_year sur la facture associée
    for p in Payment.objects.filter(invoice__isnull=False).select_related('invoice'):
        if p.invoice:
            updated = False
            if p.period_month != p.invoice.period_month:
                p.period_month = p.invoice.period_month
                updated = True
            if p.period_year != p.invoice.period_year:
                p.period_year = p.invoice.period_year
                updated = True
            if updated:
                p.save(update_fields=['period_month', 'period_year'])

    # 2. Rattacher les paiements orphelins si une facture correspondante existe
    for p in Payment.objects.filter(invoice__isnull=True):
        p_m = p.period_month or (p.payment_date.month if p.payment_date else 9)
        p_y = p.period_year or (p.payment_date.year if p.payment_date else 2026)
        inv = Invoice.objects.filter(student_id=p.student_id, period_month=p_m, period_year=p_y).first()
        if inv:
            p.invoice = inv
            p.period_month = inv.period_month
            p.period_year = inv.period_year
            p.save(update_fields=['invoice', 'period_month', 'period_year'])


def reverse_sync(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('finance', '0004_alter_payment_payment_date'),
    ]

    operations = [
        migrations.RunPython(sync_payments_with_invoice_period, reverse_sync),
    ]
