from decimal import Decimal
from django.db import migrations


def cleanup_unattended_invoices(apps, schema_editor):
    Invoice = apps.get_model('finance', 'Invoice')
    Attendance = apps.get_model('academy', 'Attendance')

    # Supprimer les factures créées sans aucun paiement pour des élèves n'ayant aucune présence dans le mois concerné
    for inv in Invoice.objects.filter(amount_paid=Decimal('0.00'), is_exempt=False):
        has_pres_in_month = Attendance.objects.filter(
            student_id=inv.student_id,
            status='present',
            date__year=inv.period_year,
            date__month=inv.period_month
        ).exists()
        if not has_pres_in_month:
            inv.delete()


def reverse_cleanup(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('finance', '0006_sync_september_and_active_invoices'),
    ]

    operations = [
        migrations.RunPython(cleanup_unattended_invoices, reverse_cleanup),
    ]
