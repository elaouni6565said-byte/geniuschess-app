import os
from datetime import date, datetime
from django.core.management.base import BaseCommand
from academy.whatsapp_watchdog import (
    run_reminders_watchdog_loop,
    check_waha_health,
    repair_waha_service,
)
from core.i18n import FRENCH_MONTHS


class Command(BaseCommand):
    help = "Exécute la boucle de surveillance (Watchdog), auto-réparation WAHA et contrôle de distribution des rappels WhatsApp."

    def add_arguments(self, parser):
        parser.add_argument(
            '--date',
            type=str,
            help="Date cible au format AAAA-MM-JJ (par défaut aujourd'hui)."
        )
        parser.add_argument(
            '--force-repair',
            action='store_true',
            help="Forcer le redémarrage d'urgence du conteneur WAHA."
        )
        parser.add_argument(
            '--force-resend',
            action='store_true',
            help="Forcer le renvoi même si déjà marqué comme envoyé."
        )

    def handle(self, *args, **options):
        target_date = date.today()
        if options.get('date'):
            try:
                target_date = datetime.strptime(options['date'], '%Y-%m-%d').date()
            except ValueError:
                self.stderr.write(self.style.ERROR(f"Format de date invalide: {options['date']}. Attendu: AAAA-MM-JJ."))
                return

        if options.get('force_repair'):
            self.stdout.write(self.style.WARNING("⚡ Exécution du redémarrage forcé de WAHA..."))
            rep = repair_waha_service()
            self.stdout.write(str(rep))

        self.stdout.write(self.style.MIGRATE_HEADING("\n" + "=" * 80))
        self.stdout.write(self.style.MIGRATE_HEADING(f"  BOUCLE DE CONTROLE & AUTO-REPARATION WHATSAPP (WATCHDOG)"))
        self.stdout.write(self.style.MIGRATE_HEADING(f"  Date: {target_date.strftime('%d/%m/%Y')} | Heure: {datetime.now().strftime('%H:%M:%S')}"))
        self.stdout.write(self.style.MIGRATE_HEADING("=" * 80 + "\n"))

        res = run_reminders_watchdog_loop(target_date=target_date, force_resend=options.get('force_resend', False))

        health = res['waha_initial_health'] or {}
        waha_badge = "🟢 EN LIGNE" if health.get('healthy') else "🔴 HORS LIGNE"
        self.stdout.write(f"1. Passerelle WhatsApp : {waha_badge} ({health.get('status')} - {health.get('detail')})")
        if res.get('waha_repaired'):
            self.stdout.write(self.style.SUCCESS("   ✓ Auto-réparation déclenchée : Conteneur Docker redémarré avec succès !"))

        self.stdout.write(f"\n2. Bilan de la distribution des rappels de séance :")
        self.stdout.write(f"   • Total élèves programmés : {res['total_expected']}")
        self.stdout.write(f"   • Déjà distribués précédemment : {res['already_delivered']}")
        self.stdout.write(f"   • Nouveaux messages expédiés avec succès : {res['newly_sent']}")
        self.stdout.write(f"   • En cours de ré-essai automatique : {res['failed_attempts']}")
        self.stdout.write(f"   • Échecs définitifs après 3 essais : {res['permanent_failures']}")

        if res['details']:
            self.stdout.write("\n3. Détail des actions menées :")
            for d in res['details']:
                st = d.get('status')
                if st == 'success':
                    self.stdout.write(self.style.SUCCESS(f"   ✓ [Succès] {d.get('student')} ({d.get('phone')}) - Essai {d.get('attempt')}"))
                elif st == 'failed':
                    self.stdout.write(self.style.WARNING(f"   ⚠️ [Échec] {d.get('student')} ({d.get('phone')}) - Essai {d.get('attempt')}: {d.get('error')}"))
                else:
                    self.stdout.write(f"   ℹ️ [{st}] {d.get('student')}: {d.get('message')}")

        # Enregistrement dans le fichier log si accessible
        log_line = (
            f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] WATCHDOG DATE={target_date} "
            f"WAHA={health.get('status')} EXP={res['total_expected']} DELIV={res['already_delivered']} "
            f"SENT={res['newly_sent']} RETRY={res['failed_attempts']} FAIL={res['permanent_failures']}\n"
        )
        for log_path in ['/var/log/gca_whatsapp_watchdog.log', 'gca_whatsapp_watchdog.log']:
            try:
                with open(log_path, 'a', encoding='utf-8') as f:
                    f.write(log_line)
                break
            except Exception:
                pass

        self.stdout.write("\n" + "=" * 80)
        self.stdout.write(self.style.SUCCESS("  FIN DU CYCLE DE CONTROLE ET DE REPARATION"))
        self.stdout.write("=" * 80 + "\n")
