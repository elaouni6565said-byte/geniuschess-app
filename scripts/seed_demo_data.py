import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gca_config.settings')
django.setup()

from decimal import Decimal
from datetime import date, time
from academy.models import (
    User, Subject, Level, Room, Group, Parent, Student,
    SessionSchedule, Attendance, Notification
)
from finance.models import Invoice, Payment

print("Seeding bilingual GCA database...")

# Clean previous seed data
Invoice.objects.all().delete()
Payment.objects.all().delete()
Attendance.objects.all().delete()
SessionSchedule.objects.all().delete()
Student.objects.all().delete()
Parent.objects.all().delete()
Group.objects.all().delete()
Level.objects.all().delete()
Room.objects.all().delete()
Subject.objects.all().delete()
User.objects.exclude(username='admin').delete()


admin_user, _ = User.objects.get_or_create(
    username='admin',
    defaults={
        'first_name': 'Directeur',
        'last_name': 'GCA',
        'email': 'contact@geniuschess.ma',
        'role': 'admin',
        'preferred_language': 'fr',
        'is_staff': True,
        'is_superuser': True,
    }
)
admin_user.set_password('CGAESA65')
admin_user.save()

subj_chess, _ = Subject.objects.get_or_create(
    name_fr="Échecs",
    defaults={
        "name_ar": "الشطرنج",
        "description_fr": "Tactique, stratégie et tournois d'échecs pour enfants.",
        "description_ar": "التكتيك، الاستراتيجية وبطولات الشطرنج للأطفال والناشئين.",
        "color": "#001B57",
        "icon": "chess-knight",
    }
)

subj_robotics, _ = Subject.objects.get_or_create(
    name_fr="Robotique",
    defaults={
        "name_ar": "الروبوتيك",
        "description_fr": "Initiation à l'électronique, Arduino et programmation de robots.",
        "description_ar": "مبادئ الإلكترونيات، برمجة الأردوينو وتصميم الروبوتات الذكية.",
        "color": "#0077CE",
        "icon": "robot",
    }
)

subj_math, _ = Subject.objects.get_or_create(
    name_fr="Calcul Mental",
    defaults={
        "name_ar": "الحساب الذهني",
        "description_fr": "Méthode Soroban et gymnastique cérébrale.",
        "description_ar": "طريقة السوربان وتنمية الذكاء وسرعة الحساب الذهني.",
        "color": "#FF6E00",
        "icon": "brain",
    }
)

lvl_beg, _ = Level.objects.get_or_create(name_fr="Débutant", defaults={"name_ar": "مبتدئ"})
lvl_int, _ = Level.objects.get_or_create(name_fr="Intermédiaire", defaults={"name_ar": "متوسط"})
lvl_adv, _ = Level.objects.get_or_create(name_fr="Avancé", defaults={"name_ar": "متقدم"})

room_kasparov, _ = Room.objects.get_or_create(name_fr="Salle Kasparov", defaults={"name_ar": "قاعة كاسباروف", "capacity": 16})
room_khawarizmi, _ = Room.objects.get_or_create(name_fr="Salle Al-Khawarizmi", defaults={"name_ar": "قاعة الخوارزمي", "capacity": 14})
room_turing, _ = Room.objects.get_or_create(name_fr="Salle Turing", defaults={"name_ar": "قاعة تورينغ", "capacity": 12})

grp_chess_sat, _ = Group.objects.get_or_create(
    name_fr="Groupe Échecs Samedi A",
    defaults={
        "name_ar": "مجموعة الشطرنج السبت (أ)",
        "subject": subj_chess,
        "level": lvl_beg,
        "monthly_fee": Decimal("300.00"),
    }
)

grp_robotics_wed, _ = Group.objects.get_or_create(
    name_fr="Groupe Robotique Mercredi",
    defaults={
        "name_ar": "مجموعة الروبوتيك الأربعاء",
        "subject": subj_robotics,
        "level": lvl_int,
        "monthly_fee": Decimal("350.00"),
    }
)

grp_math_sun, _ = Group.objects.get_or_create(
    name_fr="Groupe Calcul Mental Dimanche",
    defaults={
        "name_ar": "مجموعة الحساب الذهني الأحد",
        "subject": subj_math,
        "level": lvl_beg,
        "monthly_fee": Decimal("250.00"),
    }
)

p1_user, _ = User.objects.get_or_create(
    username="karim_alaoui",
    defaults={
        "first_name": "Karim",
        "last_name": "Alaoui",
        "email": "karim.alaoui@gca-test.ma",
        "role": "parent",
        "preferred_language": "ar",
    }
)
p1_user.set_password("Parent@2026")
p1_user.save()

parent1, _ = Parent.objects.get_or_create(
    full_name_fr="Karim Alaoui",
    defaults={
        "user": p1_user,
        "full_name_ar": "كريم العلوي",
        "cin": "CD123456",
        "phone": "0661112233",
        "email": "karim.alaoui@gca-test.ma",
        "preferred_language": "ar",
    }
)

p2_user, _ = User.objects.get_or_create(
    username="fatima_benani",
    defaults={
        "first_name": "Fatima Zahra",
        "last_name": "Benani",
        "email": "fatima.benani@gca-test.ma",
        "role": "parent",
        "preferred_language": "fr",
    }
)
p2_user.set_password("Parent@2026")
p2_user.save()

parent2, _ = Parent.objects.get_or_create(
    full_name_fr="Fatima Zahra Benani",
    defaults={
        "user": p2_user,
        "full_name_ar": "فاطمة الزهراء بناني",
        "cin": "AB987654",
        "phone": "0662223344",
        "email": "fatima.benani@gca-test.ma",
        "preferred_language": "fr",
    }
)

s1, _ = Student.objects.get_or_create(
    registration_number="GCA-2026-001",
    defaults={
        "first_name_fr": "Mohamed",
        "last_name_fr": "Alaoui",
        "first_name_ar": "محمد",
        "last_name_ar": "العلوي",
        "birth_date": date(2015, 4, 12),
        "parent": parent1,
        "active": True,
    }
)
s1.groups.add(grp_chess_sat, grp_robotics_wed)

s2, _ = Student.objects.get_or_create(
    registration_number="GCA-2026-002",
    defaults={
        "first_name_fr": "Aya",
        "last_name_fr": "Benani",
        "first_name_ar": "آية",
        "last_name_ar": "بناني",
        "birth_date": date(2016, 7, 24),
        "parent": parent2,
        "active": True,
    }
)
s2.groups.add(grp_math_sun)

s3, _ = Student.objects.get_or_create(
    registration_number="GCA-2026-003",
    defaults={
        "first_name_fr": "Sara",
        "last_name_fr": "Alaoui",
        "first_name_ar": "سارة",
        "last_name_ar": "العلوي",
        "birth_date": date(2017, 9, 3),
        "parent": parent1,
        "active": True,
    }
)
s3.groups.add(grp_chess_sat)

s4, _ = Student.objects.get_or_create(
    registration_number="GCA-2026-004",
    defaults={
        "first_name_fr": "Ahmed",
        "last_name_fr": "Benani",
        "first_name_ar": "أحمد",
        "last_name_ar": "بناني",
        "birth_date": date(2014, 11, 15),
        "parent": parent2,
        "active": True,
    }
)
s4.groups.add(grp_robotics_wed)

sched_chess_sat, _ = SessionSchedule.objects.get_or_create(
    group=grp_chess_sat,
    day_of_week=5,
    start_time=time(10, 0),
    defaults={
        "end_time": time(12, 0),
        "room": room_kasparov,
        "trainer_name_fr": "Maître Yassine",
        "trainer_name_ar": "الأستاذ ياسين",
    }
)

sched_robotics_wed, _ = SessionSchedule.objects.get_or_create(
    group=grp_robotics_wed,
    day_of_week=2,
    start_time=time(15, 0),
    defaults={
        "end_time": time(17, 0),
        "room": room_turing,
        "trainer_name_fr": "Ingénieur Mehdi",
        "trainer_name_ar": "المهندس مهدي",
    }
)

sched_math_sun, _ = SessionSchedule.objects.get_or_create(
    group=grp_math_sun,
    day_of_week=6,
    start_time=time(11, 0),
    defaults={
        "end_time": time(12, 30),
        "room": room_khawarizmi,
        "trainer_name_fr": "Prof. Salma",
        "trainer_name_ar": "الأستاذة سلمى",
    }
)

inv1, _ = Invoice.objects.get_or_create(
    student=s1,
    group=grp_chess_sat,
    period_month=9,
    period_year=2026,
    defaults={
        "amount_due": Decimal("300.00"),
        "amount_paid": Decimal("300.00"),
        "status": "paid",
        "due_date": date(2026, 9, 10),
    }
)

Payment.objects.get_or_create(
    receipt_number="REC-2026-0001",
    defaults={
        "student": s1,
        "invoice": inv1,
        "amount": Decimal("300.00"),
        "payment_date": date(2026, 9, 2),
        "payment_method": "cash",
        "reference": "ESP-09-01",
        "notes": "Règlement complet cotisation septembre",
        "created_by": admin_user,
    }
)

inv2, _ = Invoice.objects.get_or_create(
    student=s1,
    group=grp_robotics_wed,
    period_month=9,
    period_year=2026,
    defaults={
        "amount_due": Decimal("350.00"),
        "amount_paid": Decimal("250.00"),
        "status": "partial",
        "due_date": date(2026, 9, 10),
    }
)

Payment.objects.get_or_create(
    receipt_number="REC-2026-0002",
    defaults={
        "student": s1,
        "invoice": inv2,
        "amount": Decimal("250.00"),
        "payment_date": date(2026, 9, 2),
        "payment_method": "transfer",
        "reference": "VIR-BK-8821",
        "notes": "Acompte robotique, reste 100 DH",
        "created_by": admin_user,
    }
)

inv3, _ = Invoice.objects.get_or_create(
    student=s2,
    group=grp_math_sun,
    period_month=9,
    period_year=2026,
    defaults={
        "amount_due": Decimal("250.00"),
        "amount_paid": Decimal("0.00"),
        "status": "unpaid",
        "due_date": date(2026, 9, 10),
    }
)

Notification.objects.get_or_create(
    recipient=p1_user,
    title_fr="Bienvenue à l'Académie",
    defaults={
        "title_ar": "مرحباً بكم في الأكاديمية",
        "message_fr": "Votre inscription a bien été enregistrée pour la saison 2026.",
        "message_ar": "تم تأكيد تسجيل أبنائكم بنجاح في الموسم الدراسي 2026.",
        "notification_type": "general",
    }
)


# Create sample attendances
for i, (student, schedule) in enumerate([
    (s1, sched_chess_sat), (s1, sched_robotics_wed),
    (s2, sched_math_sun), (s3, sched_chess_sat),
    (s4, sched_robotics_wed)
]):
    Attendance.objects.create(
        student=student,
        session=schedule,
        date=date(2026, 8, 20 + i),
        status='present',
        notes='Excellent travail et assiduité exemplaire.'
    )

print("Demo data seeded successfully!")
