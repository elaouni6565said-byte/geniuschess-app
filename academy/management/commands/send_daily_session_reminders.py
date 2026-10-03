from datetime import date
from django.core.management.base import BaseCommand
from academy.whatsapp_reminders import dispatch_daily_whatsapp_reminders


class Command(BaseCommand):
    help = "Dispatches automated daily session reminders to parents at 13:00 for the day's scheduled sessions."

    def add_arguments(self, parser):
        parser.add_argument(
            '--date',
            type=str,
            help="Target date in YYYY-MM-DD format (defaults to today).",
        )
        parser.add_argument(
            '--time',
            type=str,
            help="Target time threshold in HH:MM format (e.g. 09:30). If provided, only sessions with notification_time <= this time are notified.",
        )

    def handle(self, *args, **options):
        target_date = date.today()
        if options.get('date'):
            from datetime import datetime
            try:
                target_date = datetime.strptime(options['date'], '%Y-%m-%d').date()
            except ValueError:
                self.stderr.write(self.style.ERROR(f"Invalid date format: {options['date']}. Expected YYYY-MM-DD."))
                return

        target_time = options.get('time')
        time_info = f" at/before {target_time}" if target_time else ""
        self.stdout.write(self.style.NOTICE(f"Processing session reminders for {target_date}{time_info}..."))
        result = dispatch_daily_whatsapp_reminders(target_date, target_time=target_time)

        self.stdout.write(
            self.style.SUCCESS(
                f"[OK] Successfully processed {result['total_reminders']} session reminders. "
                f"{result['notifications_created']} internal notifications created for {target_date}."
            )
        )
