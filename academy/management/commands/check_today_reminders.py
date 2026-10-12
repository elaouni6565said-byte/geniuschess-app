import urllib.request
import urllib.error
from datetime import date, datetime
from django.conf import settings
from django.core.management.base import BaseCommand
from academy.models import SessionSchedule, Notification
from academy.whatsapp_reminders import get_daily_sessions_reminders, is_day_cancelled
from core.i18n import FRENCH_DAYS, ARABIC_DAYS


class Command(BaseCommand):
    help = "Diagnostique l'état des rappels de séances d'aujourd'hui et teste la passerelle WhatsApp."

    def handle(self, *args, **options):
        today = date.today()
        day_idx = today.weekday()
        day_fr = FRENCH_DAYS.get(day_idx, str(day_idx))
        day_ar = ARABIC_DAYS.get(day_idx, str(day_idx))

        self.stdout.write(self.style.MIGRATE_HEADING("\n" + "=" * 80))
        self.stdout.write(self.style.MIGRATE_HEADING(f"  DIAGNOSTIC DES RAPPELS DE SEANCES DU JOUR : {day_fr.upper()} {today.strftime('%d/%m/%Y')}"))
        self.stdout.write(self.style.MIGRATE_HEADING("=" * 80 + "\n"))

        # 1. Vérification de l'état d'annulation globale
        cancelled_day = is_day_cancelled(today)
        if cancelled_day:
            self.stdout.write(self.style.ERROR("⛔ CETTE JOURNEE EST MARQUEE COMME ANNULEE PAR L'ADMINISTRATION !\n"))
        else:
            self.stdout.write(self.style.SUCCESS("✓ Journée active (Non annulée).\n"))

        # 2. Vérification des séances configurées pour ce jour
        schedules = SessionSchedule.objects.filter(day_of_week=day_idx).select_related('group', 'group__subject', 'room')
        self.stdout.write(f"📅 Séances trouvées dans l'emploi du temps pour le {day_fr} : {schedules.count()}")

        if schedules.count() == 0:
            self.stdout.write(self.style.WARNING(f"⚠️ Aucune séance n'est enregistrée dans le planning pour le {day_fr} (day_of_week={day_idx})."))
            self.stdout.write("Veuillez vérifier vos séances dans le menu Planning.")
        else:
            for s in schedules:
                act = s.group.subject.name_fr if s.group.subject else "Général"
                st_count = s.group.students.filter(active=True).count()
                n_time = s.get_notification_time().strftime('%H:%M') if s.get_notification_time() else "Non définie"
                self.stdout.write(
                    f"  • [{act}] {s.group.name_fr} ({s.start_time.strftime('%H:%M')} - {s.end_time.strftime('%H:%M')}) "
                    f"| Heure de rappel: {n_time} | Élèves actifs: {st_count}"
                )

        # 3. Récupération des rappels individuels
        items = get_daily_sessions_reminders(today)
        self.stdout.write(f"\n📲 Nombre de messages de rappel préparés pour aujourd'hui : {len(items)}")

        if len(items) == 0:
            self.stdout.write(self.style.WARNING("⚠️ Aucun message préparé. Les groupes programmés aujourd'hui n'ont peut-être pas d'élèves affectés ou leurs parents n'ont pas de profil."))
        else:
            self.stdout.write("-" * 80)
            for it in items:
                st = it['student']
                p = it['parent']
                st_nom = f"{st.first_name_fr} {st.last_name_fr}"
                p_nom = p.full_name_fr if p else "Sans parent"
                phone = it['whatsapp_phone'] or "Pas de numéro"
                t_str = it['time_str']
                n_t = it['notification_time']
                is_canc = "ANNULÉE" if it.get('is_cancelled') else "OK"

                # Vérifier si une notification existe déjà
                user = p.user if p else None
                already_notified = False
                if user:
                    already_notified = Notification.objects.filter(
                        recipient=user,
                        notification_type='session_reminder',
                        created_at__date=today,
                        message_fr__contains=st.get_full_name('fr')
                    ).exists()

                notif_status = "Déjà notifié" if already_notified else "Pas encore notifié"
                self.stdout.write(f"  👤 Élève: {st_nom:<22} | Parent: {p_nom:<20} | Tél: {phone:<14} | Séance: {t_str} | Statut: {notif_status}")
            self.stdout.write("-" * 80)

        # 4. Diagnostic de la passerelle WhatsApp
        gateway_url = getattr(settings, 'WHATSAPP_GATEWAY_URL', '')
        self.stdout.write(f"\n🌐 Passerelle WhatsApp configurée : {gateway_url or 'Aucune'}")
        
        if gateway_url:
            test_url = gateway_url.replace('/api/sendText', '/api/sessions') if '/api/sendText' in gateway_url else gateway_url
            try:
                req = urllib.request.Request(test_url, headers={'User-Agent': 'GCA-Diagnostic'})
                with urllib.request.urlopen(req, timeout=3) as resp:
                    code = resp.getcode()
                    self.stdout.write(self.style.SUCCESS(f"  ✓ Service WhatsApp en ligne (Code HTTP {code})."))
            except urllib.error.HTTPError as e:
                self.stdout.write(self.style.SUCCESS(f"  ✓ Passerelle répond (Code HTTP {e.code})."))
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"  ⚠️ Service WhatsApp injoignable sur {test_url} : {e}"))
                self.stdout.write("  💡 Si WAHA (Docker) n'est pas lancé, vous devez envoyer les messages via l'interface Web (/reminders/whatsapp/).")

        # 5. Instructions finales
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write(self.style.MIGRATE_HEADING("  SOLUTIONS POUR ENVOYER LE RAPPEL :"))
        self.stdout.write("=" * 80)
        self.stdout.write("1. Via le site web en 1 clic : Ouvrez https://app.geniuschessacademy.ma/reminders/whatsapp/")
        self.stdout.write("   et cliquez sur 'Lancer l'Envoi en Série' ou sur le bouton WhatsApp.")
        self.stdout.write("2. En ligne de commande serveur immédiate :")
        self.stdout.write("   /var/www/geniuschess/venv/bin/python manage.py send_daily_session_reminders")
        self.stdout.write("=" * 80 + "\n")
