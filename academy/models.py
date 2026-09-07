from django.db import models
from django.contrib.auth.models import AbstractUser
from decimal import Decimal
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
    notes = models.TextField(blank=True)

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

