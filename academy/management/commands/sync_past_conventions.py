from decimal import Decimal
from django.core.management.base import BaseCommand
from academy.models import Student
from finance.models import Invoice, Payment
from core.i18n import FRENCH_MONTHS


class Command(BaseCommand):
    help = "Synchronise et applique les réductions / conventions sur toutes les factures et paiements passés (Septembre, Octobre...)."

    def add_arguments(self, parser):
        parser.add_argument(
            '--fix-overpaid',
            action='store_true',
            help="Rectifier automatiquement le montant des paiements passés qui avaient été enregistrés au tarif plein (sans réduction) vers le montant net de la convention."
        )

    def handle(self, *args, **options):
        fix_overpaid = options['fix_overpaid']

        self.stdout.write(self.style.MIGRATE_HEADING("\n" + "=" * 80))
        self.stdout.write(self.style.MIGRATE_HEADING("  RÉGULARISATION RÉTROACTIVE DES REMISES & CONVENTIONS (OCTOBRE & SEPTEMBRE)"))
        self.stdout.write(self.style.MIGRATE_HEADING("=" * 80 + "\n"))

        convention_students = Student.objects.filter(has_convention=True).prefetch_related('groups')
        total_students = convention_students.count()

        self.stdout.write(f"Nombre d'élèves sous convention trouvés : {total_students}\n")

        total_invoices_updated = 0
        total_payments_linked = 0
        total_payments_rectified = 0

        for st in convention_students:
            base_fee, discount, final_fee = st.calculate_monthly_fee()
            conv_name = st.convention_name or "Convention Partenaire"

            self.stdout.write(self.style.SUCCESS(f"\n👤 [{st.registration_number}] {st.get_full_name('fr')}"))
            self.stdout.write(f"   Convention: {conv_name} | Type: {st.discount_type} | Val: {st.discount_value}")
            self.stdout.write(f"   Tarif base: {base_fee} DH | Remise: {discount} DH | Tarif Net: {final_fee} DH")

            # 1. Synchroniser toutes les factures non exonérées de cet élève
            invoices = Invoice.objects.filter(student=st, is_exempt=False).order_by('period_year', 'period_month')
            for inv in invoices:
                m_label = FRENCH_MONTHS.get(inv.period_month, str(inv.period_month)).capitalize()
                old_due = inv.amount_due
                old_disc = inv.discount_amount

                inv.original_amount = base_fee
                inv.discount_amount = discount
                inv.amount_due = final_fee
                inv.save()
                inv.update_totals()

                total_invoices_updated += 1
                self.stdout.write(
                    f"   📄 Facture {m_label} {inv.period_year} : "
                    f"Base={base_fee} DH, Remise={discount} DH, Dû={final_fee} DH, "
                    f"Payé={inv.amount_paid} DH -> Statut: {inv.status}"
                )

            # 2. Rapprochement et analyse des paiements de cet élève
            payments = Payment.objects.filter(student=st).order_by('payment_date', 'id')
            for p in payments:
                p_month = p.period_month or (p.invoice.period_month if p.invoice else (p.payment_date.month if p.payment_date else 10))
                p_year = p.period_year or (p.invoice.period_year if p.invoice else 2026)
                m_label = FRENCH_MONTHS.get(p_month, str(p_month)).capitalize()

                # Liaison automatique avec la facture si non liée
                if not p.invoice:
                    matching_inv = Invoice.objects.filter(student=st, period_month=p_month, period_year=p_year).first()
                    if matching_inv:
                        p.invoice = matching_inv
                        p.period_month = matching_inv.period_month
                        p.period_year = matching_inv.period_year
                        p.save()
                        matching_inv.update_totals()
                        total_payments_linked += 1

                # Détection d'un encaissement au tarif plein au lieu du tarif net conventionné
                if p.amount == base_fee and base_fee > final_fee:
                    if fix_overpaid:
                        old_amt = p.amount
                        p.amount = final_fee
                        p.save()
                        if p.invoice:
                            p.invoice.update_totals()
                        total_payments_rectified += 1
                        self.stdout.write(
                            self.style.WARNING(
                                f"   💳 Reçu #{p.receipt_number} ({m_label} {p_year}) : RECTIFIÉ {old_amt} DH -> {final_fee} DH"
                            )
                        )
                    else:
                        self.stdout.write(
                            self.style.NOTICE(
                                f"   ⚠️ Reçu #{p.receipt_number} ({m_label} {p_year}) : Enregistré à {p.amount} DH (Plein tarif). "
                                f"Tarif conventionné = {final_fee} DH (Passez --fix-overpaid pour ajuster)."
                            )
                        )
                else:
                    self.stdout.write(
                        f"   💳 Reçu #{p.receipt_number} ({m_label} {p_year}) : Montant={p.amount} DH | Date={p.payment_date}"
                    )

        self.stdout.write("\n" + "=" * 80)
        self.stdout.write(self.style.SUCCESS("  RÉSUMÉ DU TRAITEMENT"))
        self.stdout.write("=" * 80)
        self.stdout.write(f"✓ Factures synchronisées et remisées : {total_invoices_updated}")
        self.stdout.write(f"✓ Paiements rattachés à leur facture : {total_payments_linked}")
        if fix_overpaid:
            self.stdout.write(self.style.SUCCESS(f"✓ Paiements ajustés au tarif net remisé : {total_payments_rectified}"))
        else:
            self.stdout.write("💡 Note : Pour ajuster automatiquement les reçus passés payés plein tarif, relancez avec l'option --fix-overpaid")
        self.stdout.write("=" * 80 + "\n")
