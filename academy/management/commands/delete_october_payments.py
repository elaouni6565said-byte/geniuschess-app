from decimal import Decimal
from django.core.management.base import BaseCommand
from django.db.models import Q, Sum
from academy.models import Student
from finance.models import Invoice, Payment
from core.i18n import FRENCH_MONTHS


class Command(BaseCommand):
    help = "Supprime tous les paiements dont le mois concerné est Octobre 2026 et réinitialise les factures correspondantes."

    def add_arguments(self, parser):
        parser.add_argument(
            '--month',
            type=int,
            default=10,
            help="Mois concerné à supprimer (par défaut : 10 pour Octobre)"
        )
        parser.add_argument(
            '--year',
            type=int,
            default=2026,
            help="Année concernée (par défaut : 2026)"
        )
        parser.add_argument(
            '--confirm',
            action='store_true',
            help="Confirmer expressément la suppression"
        )

    def handle(self, *args, **options):
        target_month = options['month']
        target_year = options['year']
        confirmed = options['confirm']
        m_label = FRENCH_MONTHS.get(target_month, str(target_month)).capitalize()

        self.stdout.write(self.style.MIGRATE_HEADING("\n" + "=" * 80))
        self.stdout.write(self.style.MIGRATE_HEADING(f"  SUPPRESSION DES PAIEMENTS — MOIS CONCERNÉ : {m_label.upper()} {target_year}"))
        self.stdout.write(self.style.MIGRATE_HEADING("=" * 80 + "\n"))

        # Cibler uniquement les paiements dont le MOIS CONCERNÉ est Octobre 2026
        # (ne pas toucher aux paiements de septembre payés en octobre)
        october_payments = Payment.objects.filter(
            Q(invoice__period_month=target_month, invoice__period_year=target_year) |
            Q(invoice__isnull=True, period_month=target_month, period_year=target_year) |
            Q(period_month=target_month, period_year=target_year)
        ).exclude(
            # Exclure explicitement si la facture liée est pour un autre mois (ex: septembre)
            Q(invoice__isnull=False) & ~Q(invoice__period_month=target_month)
        ).select_related('student', 'invoice').order_by('payment_date', 'id')

        count = october_payments.count()
        total_amount = october_payments.aggregate(t=Sum('amount'))['t'] or Decimal('0.00')

        if count == 0:
            self.stdout.write(self.style.WARNING(f"Aucun paiement trouvé pour le mois concerné {m_label} {target_year}."))
            return

        self.stdout.write(f"Nombre de paiements concernés trouvés : {count}")
        self.stdout.write(f"Montant total à supprimer : {total_amount} DH\n")
        self.stdout.write("-" * 80)

        invoices_to_update = set()
        for p in october_payments:
            st = p.student
            st_name = f"{st.first_name_fr} {st.last_name_fr}" if st else "Inconnu"
            reg = st.registration_number if st else "-"
            inv_str = f"Facture m.{p.invoice.period_month}" if p.invoice else "Sans facture"
            self.stdout.write(
                f"  Reçu #{p.receipt_number:<12} | {reg:<12} | {st_name:<25} | {p.amount:>7} DH | Date: {p.payment_date} | {inv_str}"
            )
            if p.invoice:
                invoices_to_update.add(p.invoice)

        self.stdout.write("-" * 80 + "\n")

        if not confirmed:
            self.stdout.write(self.style.NOTICE(
                f"⚠️  Mode simulation : Aucun paiement n'a été supprimé.\n"
                f"Pour exécuter réellement la suppression, ajoutez le paramètre --confirm :\n\n"
                f"  /var/www/geniuschess/venv/bin/python manage.py delete_october_payments --confirm\n"
            ))
            return

        # Suppression réelle
        deleted_count, _ = october_payments.delete()
        self.stdout.write(self.style.SUCCESS(f"✓ {deleted_count} paiement(s) supprimé(s) avec succès de la base de données."))

        # Réinitialisation et recalcul des factures du mois concerné
        all_month_invoices = Invoice.objects.filter(period_month=target_month, period_year=target_year).select_related('student')
        updated_inv_count = 0

        for inv in all_month_invoices:
            st = inv.student
            if st and st.has_convention:
                base_fee, discount, final_fee = st.calculate_monthly_fee()
                inv.original_amount = base_fee
                inv.discount_amount = discount
                inv.amount_due = final_fee

            inv.amount_paid = Decimal('0.00')
            if inv.is_exempt:
                inv.status = 'exempt'
            else:
                inv.status = 'unpaid'
            inv.save()
            inv.update_totals()
            updated_inv_count += 1

        self.stdout.write(self.style.SUCCESS(f"✓ {updated_inv_count} facture(s) du mois de {m_label} {target_year} réinitialisée(s) en statut 'Non réglé' (avec application des réductions convention)."))
        self.stdout.write(self.style.SUCCESS(f"✓ Les encaissements d'Octobre du Dashboard sont désormais remis à 0,00 DH.\n"))
        self.stdout.write("=" * 80 + "\n")
