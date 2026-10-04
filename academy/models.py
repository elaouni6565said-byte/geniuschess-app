from django.db import models
from django.contrib.auth.models import AbstractUser
from decimal import Decimal
from datetime import time, datetime, timedelta, date
from core.i18n import FRENCH_DAYS, ARABIC_DAYS

class User(AbstractUser):
    ROLE_CHOICES = [
        ('admin', 'Administrateur'),
        ('trainer', 'Formateur'),
        ('parent', 'Parent'),
    ]
    LANGUAGE_CHOICES = [
        ('fr', 'Français'),
        ('ar', 'العربية'),
    ]
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='admin')
    preferred_language = models.CharField(max_length=5, choices=LANGUAGE_CHOICES, default='fr')
    phone = models.CharField(max_length=30, blank=True)

    def is_admin_role(self):
        return self.role == 'admin' or self.is_superuser

    def is_parent_role(self):
        return self.role == 'parent'

    def is_trainer_role(self):
        return self.role == 'trainer'


class Subject(models.Model):
    name_fr = models.CharField(max_length=100, verbose_name="Nom (FR)")
    name_ar = models.CharField(max_length=100, verbose_name="Nom (AR)")
    description_fr = models.TextField(blank=True)
    description_ar = models.TextField(blank=True)
    color = models.CharField(max_length=20, default="#0077CE")
    icon = models.CharField(max_length=50, default="chess")

    def get_name(self, lang="fr"):
        return self.name_ar if lang == "ar" and self.name_ar else self.name_fr

    def get_bilingual_name(self):
        return f"{self.name_fr} / {self.name_ar}"

    def __str__(self):
        return f"{self.name_fr} ({self.name_ar})"


class Level(models.Model):
    name_fr = models.CharField(max_length=100)
    name_ar = models.CharField(max_length=100)

    def get_name(self, lang="fr"):
        return self.name_ar if lang == "ar" and self.name_ar else self.name_fr

    def __str__(self):
        return f"{self.name_fr} ({self.name_ar})"


class Room(models.Model):
    name_fr = models.CharField(max_length=100)
    name_ar = models.CharField(max_length=100)
    capacity = models.PositiveIntegerField(default=15)

    def get_name(self, lang="fr"):
        return self.name_ar if lang == "ar" and self.name_ar else self.name_fr

    def __str__(self):
        return f"{self.name_fr} ({self.name_ar})"


class Group(models.Model):
    PALETTE = [
        "#2563EB",  # Royal Blue
        "#7C3AED",  # Violet / Purple
        "#059669",  # Emerald Green
        "#D97706",  # Amber / Gold
        "#DC2626",  # Crimson Red
        "#0891B2",  # Cyan
        "#4F46E5",  # Indigo
        "#EA580C",  # Vivid Orange
        "#0D9488",  # Teal
        "#DB2777",  # Rose / Pink
        "#475569",  # Slate
        "#16A34A",  # Forest Green
    ]

    name_fr = models.CharField(max_length=100)
    name_ar = models.CharField(max_length=100)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name="groups")
    level = models.ForeignKey(Level, on_delete=models.SET_NULL, null=True, blank=True)
    monthly_fee = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("300.00"))
    color = models.CharField(max_length=20, default="", blank=True, verbose_name="Couleur du Groupe / لون المجموعة")

    def get_color(self):
        if self.color:
            return self.color
        return self.PALETTE[(self.id or 0) % len(self.PALETTE)]

    def get_name(self, lang="fr"):
        return self.name_ar if lang == "ar" and self.name_ar else self.name_fr

    def __str__(self):
        return f"{self.name_fr} ({self.name_ar})"


class Parent(models.Model):
    user = models.OneToOneField(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="parent_profile")
    full_name_fr = models.CharField(max_length=150)
    full_name_ar = models.CharField(max_length=150)
    cin = models.CharField(max_length=30, blank=True)
    phone = models.CharField(max_length=30)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True, default='', verbose_name="Adresse / Domicile")
    preferred_language = models.CharField(max_length=5, choices=User.LANGUAGE_CHOICES, default="fr")

    def get_name(self, lang="fr"):
        return self.full_name_ar if lang == "ar" and self.full_name_ar else self.full_name_fr

    def get_full_name(self, lang="fr"):
        return self.get_name(lang)

    def get_last_visit(self):
        last_visit = self.visit_logs.order_by('-timestamp').first()
        return last_visit.timestamp if last_visit else None

    def get_visit_count(self):
        return self.visit_logs.count()

    def save(self, *args, **kwargs):
        if self.phone:
            import re
            cleaned = re.sub(r'[^\d]', '', str(self.phone).strip())
            if cleaned.startswith('00212'):
                cleaned = cleaned[2:]
            elif cleaned.startswith('2120') and len(cleaned) >= 12:
                cleaned = '212' + cleaned[4:]
            elif cleaned.startswith('0'):
                cleaned = '212' + cleaned[1:]
            elif not cleaned.startswith('212') and len(cleaned) == 9:
                cleaned = '212' + cleaned
            if cleaned:
                self.phone = cleaned
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.full_name_fr} / {self.full_name_ar} ({self.phone})"


class Student(models.Model):
    registration_number = models.CharField(max_length=50, unique=True)
    first_name_fr = models.CharField(max_length=100)
    last_name_fr = models.CharField(max_length=100)
    first_name_ar = models.CharField(max_length=100)
    last_name_ar = models.CharField(max_length=100)
    birth_date = models.DateField(null=True, blank=True)
    school = models.CharField(max_length=150, blank=True, default='', verbose_name="École de scolarité")
    grade_level = models.CharField(max_length=100, blank=True, default='', verbose_name="Niveau de scolarité")
    parent = models.ForeignKey(Parent, on_delete=models.CASCADE, related_name="students")
    groups = models.ManyToManyField(Group, related_name="students", blank=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # 5. Champs Convention & Réduction de prix
    DISCOUNT_TYPE_CHOICES = [
        ('custom_fee', 'Tarif mensuel forfaitaire (DH) / سومة اتفاقية محددة'),
        ('fixed_discount', 'Réduction fixe en DH / تخفيض بقيمة محددة'),
        ('percentage', 'Pourcentage de réduction (%) / نسبة تخفيض مئوية'),
    ]
    has_convention = models.BooleanField(default=False, verbose_name="Bénéficie d'une convention / يستفيد من اتفاقية")
    convention_name = models.CharField(max_length=150, blank=True, default='', verbose_name="Nom de la convention / Organisme partenaire")
    discount_type = models.CharField(max_length=20, choices=DISCOUNT_TYPE_CHOICES, default='custom_fee', verbose_name="Type de réduction")
    discount_value = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name="Valeur de la réduction ou Tarif (DH ou %)")

    def calculate_monthly_fee(self):
        """
        Calcule le montant de base, le montant de la réduction convention (le cas échéant)
        et le tarif final net mensuel pour l'élève.
        Retourne : (base_fee, discount_amount, final_fee)
        """
        base_fee = sum(g.monthly_fee for g in self.groups.all() if g.monthly_fee > 0) or Decimal('0.00')
        if base_fee == Decimal('0.00') and self.groups.exists():
            base_fee = Decimal('150.00')

        if not self.has_convention or self.discount_value <= Decimal('0.00'):
            return base_fee, Decimal('0.00'), base_fee

        if self.discount_type == 'custom_fee':
            final_fee = max(Decimal('0.00'), self.discount_value)
            discount_amount = max(Decimal('0.00'), base_fee - final_fee)
        elif self.discount_type == 'percentage':
            pct = min(Decimal('100.00'), max(Decimal('0.00'), self.discount_value))
            discount_amount = (base_fee * pct) / Decimal('100.00')
            final_fee = max(Decimal('0.00'), base_fee - discount_amount)
        elif self.discount_type == 'fixed_discount':
            discount_amount = min(base_fee, max(Decimal('0.00'), self.discount_value))
            final_fee = max(Decimal('0.00'), base_fee - discount_amount)
        else:
            discount_amount = Decimal('0.00')
            final_fee = base_fee

        return base_fee, round(discount_amount, 2), round(final_fee, 2)

    def is_exempt_for_period(self, month, year=2026):
        """Vérifie si l'élève est expressément exonéré de paiement pour ce mois/année."""
        ex = self.payment_exemptions.filter(period_month=month, period_year=year).first()
        if ex:
            return True, ex.reason
        return False, ""

    def get_exempted_months_display(self, year=2026, lang="fr"):
        """Retourne la liste lisible des mois exonérés pour l'année donnée."""
        from core.i18n import FRENCH_MONTHS, ARABIC_MONTHS
        exemptions = self.payment_exemptions.filter(period_year=year).order_by('period_month')
        if not exemptions.exists():
            return ""
        labels = []
        month_dict = ARABIC_MONTHS if lang == "ar" else FRENCH_MONTHS
        for ex in exemptions:
            m_name = month_dict.get(ex.period_month, str(ex.period_month))
            labels.append(m_name.capitalize())
        return ", ".join(labels)

    def get_full_name(self, lang="fr"):
        if lang == "ar" and (self.first_name_ar or self.last_name_ar):
            return f"{self.first_name_ar} {self.last_name_ar}".strip()
        return f"{self.first_name_fr} {self.last_name_fr}".strip()

    def get_bilingual_full_name(self):
        fr = f"{self.first_name_fr} {self.last_name_fr}".strip()
        ar = f"{self.first_name_ar} {self.last_name_ar}".strip()
        if ar:
            return f"{fr} / {ar}"
        return fr

    def get_last_parent_visit(self):
        last_visit = self.parent_visits.order_by('-timestamp').first()
        return last_visit.timestamp if last_visit else None

    def __str__(self):
        return f"[{self.registration_number}] {self.get_bilingual_full_name()}"


class SessionSchedule(models.Model):
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="schedules")
    room = models.ForeignKey(Room, on_delete=models.SET_NULL, null=True, blank=True)
    trainer_name_fr = models.CharField(max_length=100, default="Formateur GCA")
    trainer_name_ar = models.CharField(max_length=100, default="مدرب الأكاديمية")
    day_of_week = models.IntegerField(choices=[
        (0, "Lundi / الاثنين"),
        (1, "Mardi / الثلاثاء"),
        (2, "Mercredi / الأربعاء"),
        (3, "Jeudi / الخميس"),
        (4, "Vendredi / الجمعة"),
        (5, "Samedi / السبت"),
        (6, "Dimanche / الأحد"),
    ])
    start_time = models.TimeField()
    end_time = models.TimeField()
    notification_time = models.TimeField(
        default=time(9, 30),
        null=True,
        blank=True,
        verbose_name="Heure de notification / وقت إرسال التذكير",
        help_text="Heure d'envoi du rappel WhatsApp (ex: 09:30)"
    )

    def get_notification_time(self):
        if self.notification_time:
            return self.notification_time
        dt = datetime.combine(date.today(), self.start_time) - timedelta(hours=1)
        return dt.time()

    def get_day_name(self, lang="fr"):
        if lang == "ar":
            return ARABIC_DAYS.get(self.day_of_week, "")
        return FRENCH_DAYS.get(self.day_of_week, "")

    def get_trainer_name(self, lang="fr"):
        return self.trainer_name_ar if lang == "ar" and self.trainer_name_ar else self.trainer_name_fr

    def __str__(self):
        return f"{self.group.name_fr} - {self.get_day_name('fr')} ({self.start_time.strftime('%H:%M')}-{self.end_time.strftime('%H:%M')})"


class Attendance(models.Model):
    STATUS_CHOICES = [
        ("present", "Présent / حاضر"),
        ("absent", "Absent / غائب"),
        ("justified", "Justifié / مبرر"),
        ("late", "Retard / متأخر"),
    ]
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="attendances")
    session = models.ForeignKey(SessionSchedule, on_delete=models.CASCADE)
    date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="present")
    scanned_at = models.TimeField(null=True, blank=True, verbose_name="Heure de pointage / وقت التسجيل")
    notes = models.TextField(blank=True)

    def get_scanned_time_display(self):
        if self.scanned_at:
            return self.scanned_at.strftime('%H:%M')
        return ""

    def get_status_label(self, lang="fr"):
        labels = {
            "present": {"fr": "Présent", "ar": "حاضر"},
            "absent": {"fr": "Absent", "ar": "غائب"},
            "justified": {"fr": "Justifié", "ar": "مبرر"},
            "late": {"fr": "En retard", "ar": "متأخر"},
        }
        return labels.get(self.status, {}).get(lang, self.status)

    class Meta:
        unique_together = ("student", "session", "date")


class Notification(models.Model):
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notifications")
    title_fr = models.CharField(max_length=200)
    title_ar = models.CharField(max_length=200)
    message_fr = models.TextField()
    message_ar = models.TextField()
    notification_type = models.CharField(max_length=30, default="general")
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    def get_title(self, lang="fr"):
        return self.title_ar if lang == "ar" and self.title_ar else self.title_fr

    def get_message(self, lang="fr"):
        return self.message_ar if lang == "ar" and self.message_ar else self.message_fr


class ParentVisitLog(models.Model):
    parent = models.ForeignKey(Parent, on_delete=models.CASCADE, related_name="visit_logs")
    student = models.ForeignKey(Student, on_delete=models.CASCADE, null=True, blank=True, related_name="parent_visits")
    timestamp = models.DateTimeField(auto_now_add=True)
    ip_address = models.CharField(max_length=50, blank=True)

    class Meta:
        ordering = ['-timestamp']
        verbose_name = "Visite Parent"
        verbose_name_plural = "Visites Parents"

    def __str__(self):
        st_name = self.student.get_full_name() if self.student else "Tous"
        return f"{self.parent.full_name_fr} -> {st_name} ({self.timestamp.strftime('%d/%m/%Y %H:%M')})"


class SessionCancellation(models.Model):
    """
    Permet à l'administrateur d'annuler une séance précise ou toute une journée.
    Si cancel_all_day=True, toutes les séances et rappels de cette date sont désactivés.
    Si schedule est renseigné, seule cette séance précise pour cette date est désactivée.
    """
    schedule = models.ForeignKey(SessionSchedule, on_delete=models.CASCADE, related_name="cancellations", null=True, blank=True)
    date = models.DateField(db_index=True)
    reason = models.CharField(max_length=255, blank=True, default='')
    cancel_all_day = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-created_at']
        verbose_name = "Annulation de séance"
        verbose_name_plural = "Annulations de séances"

    def __str__(self):
        if self.cancel_all_day:
            return f"Journée entière annulée le {self.date}"
        return f"Séance {self.schedule} annulée le {self.date}"


class GroupMessage(models.Model):
    MESSAGE_TYPES = [
        ('info', 'Information générale / إشعار عام'),
        ('reminder', 'Rappel de séance / تذكير بالحصص'),
        ('pedagogy', 'Pédagogie & Devoirs / محتوى تربوي وتمارين'),
        ('event', 'Événement & Tournoi / حدث أو بطولة'),
        ('urgent', 'Urgent / عاجل'),
    ]

    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="messages")
    author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="group_messages")
    title = models.CharField(max_length=200, blank=True, verbose_name="Titre / Objet")
    content = models.TextField(verbose_name="Message / Contenu")
    message_type = models.CharField(max_length=20, choices=MESSAGE_TYPES, default='info')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Message de Groupe"
        verbose_name_plural = "Messages de Groupe"

    def get_type_badge(self):
        badges = {
            'info': {'color': '#0284C7', 'bg': '#E0F2FE', 'icon': '📢', 'label_fr': 'Info', 'label_ar': 'إشعار'},
            'reminder': {'color': '#D97706', 'bg': '#FEF3C7', 'icon': '⏰', 'label_fr': 'Rappel', 'label_ar': 'تذكير'},
            'pedagogy': {'color': '#7C3AED', 'bg': '#EDE9FE', 'icon': '📚', 'label_fr': 'Pédagogie', 'label_ar': 'تربوي'},
            'event': {'color': '#059669', 'bg': '#D1FAE5', 'icon': '🏆', 'label_fr': 'Événement', 'label_ar': 'حدث'},
            'urgent': {'color': '#DC2626', 'bg': '#FEE2E2', 'icon': '🚨', 'label_fr': 'Urgent', 'label_ar': 'عاجل'},
        }
        return badges.get(self.message_type, badges['info'])

    def __str__(self):
        return f"[{self.group.name_fr}] {self.title or self.content[:30]}"


