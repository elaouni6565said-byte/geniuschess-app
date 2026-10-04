from datetime import date
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.db.models import Q, Sum
from academy.models import Student, Group
from finance.models import Invoice, Payment, PaymentExemption
from core.i18n import FRENCH_MONTHS


class Command(BaseCommand):
    help = "Vérifie l'exhaustivité financière d'un mois : Total Élèves Actifs = Payés + Impayés + Exonérés."

    def add_arguments(self, parser):
        parser.add_argument('--month', type=int, default=9, help="Mois à auditer (ex: 9 pour Septembre)")
        parser.add_argument('--year', type=int, default=2026, help="Année à auditer (ex: 2026)")
        parser.add_argument('--fix', action='store_true', help="Générer automatiquement les factures manquantes pour les élèves actifs")

    def handle(self, *args, **options):
        month = options['month']
        year = options['year']
        auto_fix = options['fix']
        month_label = FRENCH_MONTHS.get(month, str(month)).capitalize()

        self.stdout.write(self.style.MIGRATE_HEADING(f"\n========================================================"))
        self.stdout.write(self.style.MIGRATE_HEADING(f" AUDIT DE RÉCONCILIATION FINANCIÈRE — {month_label} {year}"))
        self.stdout.write(self.style.MIGRATE_HEADING(f"========================================================\n"))

        # 1. Rapprochement préalable des paiements et factures existantes
        for p in Payment.objects.filter(invoice__isnull=True).select_related('student'):
            p_m = p.period_month or (p.payment_date.month if p.payment_date else month)
            p_y = p.period_year or (p.payment_date.year if p.payment_date else year)
            target = Invoice.objects.filter(student=p.student, period_month=p_m, period_year=p_y).first()
            if target:
                p.invoice = target
                p.period_month = target.period_month
                p.period_year = target.period_year
                p.save()
            else:
                p.save()

        for p in Payment.objects.filter(invoice__isnull=False).select_related('invoice'):
            if p.period_month != p.invoice.period_month or p.period_year != p.invoice.period_year:
                p.period_month = p.invoice.period_month
                p.period_year = p.invoice.period_year
                p.save(update_fields=['period_month', 'period_year'])
                p.invoice.update_totals()

        # 2. Récupérer tous les élèves actifs
        active_students = Student.objects.filter(active=True).prefetch_related('groups')
        total_active_count = active_students.count()

        # 3. Analyser les factures du mois
        month_invoices = Invoice.objects.filter(period_month=month, period_year=year).select_related('student', 'group')

        # Identifier les élèves par catégorie
        paid_students = []
        unpaid_students = []
        exempt_students = []

        invoiced_student_ids = set()

        for inv in month_invoices:
            st = inv.student
            if not st or not st.active:
                continue
            invoiced_student_ids.add(st.id)

            if inv.is_exempt or inv.status == 'exempt':
                exempt_students.append({
                    'student': st,
                    'invoice': inv,
                    'reason': inv.exemption_reason or "Exonération accordée"
                })
            elif inv.status == 'paid':
                paid_students.append({
                    'student': st,
                    'invoice': inv,
                    'amount_paid': inv.amount_paid
                })
            elif inv.status in ['unpaid', 'partial']:
                unpaid_students.append({
                    'student': st,
                    'invoice': inv,
                    'amount_due': inv.amount_due,
                    'amount_paid': inv.amount_paid,
                    'balance': inv.get_balance(),
                    'status': inv.status
                })

        # 4. Vérifier s'il y a des paiements pour des élèves sans facture rattachée
        orphan_month_pays = Payment.objects.filter(
            period_month=month,
            period_year=year,
            invoice__isnull=True
        ).select_related('student')
        for op in orphan_month_pays:
            if op.student and op.student.active and op.student.id not in invoiced_student_ids:
                invoiced_student_ids.add(op.student.id)
                paid_students.append({
                    'student': op.student,
                    'invoice': None,
                    'amount_paid': op.amount
                })

        # 5. Identifier les élèves manquants (Actifs mais sans facture ni paiement pour ce mois)
        missing_students = [st for st in active_students if st.id not in invoiced_student_ids]

        # 6. Traitement automatique avec --fix si demandé
        if auto_fix and missing_students:
            self.stdout.write(self.style.WARNING(f"\n[ACTION --fix] Création des factures pour les {len(missing_students)} élèves manquants..."))
            due_date = date(year, month, 15)
            for st in missing_students:
                first_grp = st.groups.first()
                if not first_grp:
                    continue
                is_ex, ex_reason = st.is_exempt_for_period(month, year)
                base_fee, discount, final_fee = st.calculate_monthly_fee()

                if is_ex:
                    inv = Invoice.objects.create(
                        student=st,
                        group=first_grp,
                        period_month=month,
                        period_year=year,
                        original_amount=base_fee,
                        discount_amount=base_fee,
                        amount_due=Decimal('0.00'),
                        amount_paid=Decimal('0.00'),
                        status='exempt',
                        is_exempt=True,
                        exemption_reason=ex_reason or "Exonération accordée",
                        due_date=due_date
                    )
                    exempt_students.append({'student': st, 'invoice': inv, 'reason': ex_reason})
                else:
                    inv = Invoice.objects.create(
                        student=st,
                        group=first_grp,
                        period_month=month,
                        period_year=year,
                        original_amount=base_fee,
                        discount_amount=discount,
                        amount_due=final_fee,
                        amount_paid=Decimal('0.00'),
                        status='unpaid',
                        is_exempt=False,
                        exemption_reason='',
                        due_date=due_date
                    )
                    inv.update_totals()
                    if inv.status == 'paid':
                        paid_students.append({'student': st, 'invoice': inv, 'amount_paid': inv.amount_paid})
                    else:
                        unpaid_students.append({
                            'student': st,
                            'invoice': inv,
                            'amount_due': inv.amount_due,
                            'amount_paid': inv.amount_paid,
                            'balance': inv.get_balance(),
                            'status': inv.status
                        })
                invoiced_student_ids.add(st.id)

            missing_students = [st for st in active_students if st.id not in invoiced_student_ids]

        # 7. Affichage du rapport d'audit
        count_paid = len(paid_students)
        count_unpaid = len(unpaid_students)
        count_exempt = len(exempt_students)
        total_accounted = count_paid + count_unpaid + count_exempt

        tot_rev = sum((p['amount_paid'] for p in paid_students), Decimal('0.00')) + sum((u['amount_paid'] for u in unpaid_students), Decimal('0.00'))
        tot_unpaid_amount = sum((u['balance'] for u in unpaid_students), Decimal('0.00'))

        self.stdout.write(f"1. Total eleves actifs dans l'academie : {self.style.SUCCESS(str(total_active_count))}")
        self.stdout.write(f"--------------------------------------------------------")
        self.stdout.write(f"  * [PAYE]    Eleves PAYES / Regles          : {count_paid:2d} eleves (Total encaisse : {tot_rev:.2f} DH)")
        self.stdout.write(f"  * [IMPAYE]  Eleves IMPAYES / En retard     : {count_unpaid:2d} eleves (Total reliquat : {self.style.NOTICE(f'{tot_unpaid_amount:.2f} DH')})")
        self.stdout.write(f"  * [EXONERE] Eleves EXONERES (0 DH)         : {count_exempt:2d} eleves")
        self.stdout.write(f"--------------------------------------------------------")
        self.stdout.write(f"2. Somme des listes (Payes + Impayes + Exoneres) : {total_accounted} eleves")

        # Détail des élèves impayés
        if unpaid_students:
            self.stdout.write(self.style.WARNING(f"\n--- Detail des {count_unpaid} eleves Impayes de {month_label} {year} ---"))
            for idx, u in enumerate(unpaid_students, 1):
                st = u['student']
                bal = u['balance']
                self.stdout.write(
                    f"  {idx}. [{st.registration_number}] {st.first_name_fr} {st.last_name_fr} "
                    f"| Du: {u['amount_due']} DH | Paye: {u['amount_paid']} DH | RESTE: {self.style.ERROR(f'{bal} DH')}"
                )

        # Détail des élèves exonérés
        if exempt_students:
            self.stdout.write(self.style.MIGRATE_LABEL(f"\n--- Detail des {count_exempt} eleves Exoneres de {month_label} {year} ---"))
            for idx, e in enumerate(exempt_students, 1):
                st = e['student']
                self.stdout.write(f"  {idx}. [{st.registration_number}] {st.first_name_fr} {st.last_name_fr} | Motif: {e['reason']}")

        # Détail des élèves manquants
        if missing_students:
            self.stdout.write(self.style.ERROR(f"\n--- [!] ATTENTION : {len(missing_students)} eleves actifs n'ont aucune facture pour {month_label} {year} ---"))
            for idx, st in enumerate(missing_students, 1):
                grps = ", ".join([g.name_fr for g in st.groups.all()]) or "Aucun groupe"
                self.stdout.write(f"  {idx}. [{st.registration_number}] {st.first_name_fr} {st.last_name_fr} | Groupes: {grps}")
            self.stdout.write(self.style.WARNING("\n  --> Conseil : Vous pouvez executer cette commande avec '--fix' pour generer leurs factures."))

        # 8. Verdict final de la réconciliation
        self.stdout.write(f"\n========================================================")
        if total_active_count == total_accounted and not missing_students:
            self.stdout.write(self.style.SUCCESS(f" [OK] RECONCILIATION PARFAITE (100% CONFORME) !"))
            self.stdout.write(self.style.SUCCESS(f" Total Eleves Actifs ({total_active_count}) = Payes ({count_paid}) + Impayes ({count_unpaid}) + Exoneres ({count_exempt})"))
        else:
            diff = total_active_count - total_accounted
            self.stdout.write(self.style.ERROR(f" [ECART DETECTE] Il y a {abs(diff)} eleve(s) d'ecart entre les actifs et le systeme de facturation."))
        self.stdout.write(f"========================================================\n")
