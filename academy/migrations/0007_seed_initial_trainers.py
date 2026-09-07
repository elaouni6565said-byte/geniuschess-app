from django.db import migrations
from decimal import Decimal
from django.contrib.auth.hashers import make_password

def seed_trainers(apps, schema_editor):
    Trainer = apps.get_model('academy', 'Trainer')
    SessionSchedule = apps.get_model('academy', 'SessionSchedule')
    User = apps.get_model('academy', 'User')

    # 1. Trainer 1: Yassine Alami
    t1, _ = Trainer.objects.get_or_create(
        cin="CD123456",
        defaults={
            "first_name_fr": "Yassine",
            "last_name_fr": "Alami",
            "first_name_ar": "ياسين",
            "last_name_ar": "العلمي",
            "phone": "0661122334",
            "email": "yassine.alami@gca.ma",
            "specialty": "Échecs",
            "address": "Sidi Kacem",
            "compensation_type": "per_session",
            "default_rate": Decimal("150.00"),
            "bank_name": "Attijariwafa Bank",
            "bank_rib": "007780000123456789012345",
            "active": True
        }
    )

    # 2. Trainer 2: Mehdi Berrada
    t2, _ = Trainer.objects.get_or_create(
        cin="CD234567",
        defaults={
            "first_name_fr": "Mehdi",
            "last_name_fr": "Berrada",
            "first_name_ar": "مهدي",
            "last_name_ar": "برادة",
            "phone": "0662233445",
            "email": "mehdi.berrada@gca.ma",
            "specialty": "Robotique & IA",
            "address": "Sidi Kacem",
            "compensation_type": "per_session",
            "default_rate": Decimal("150.00"),
            "bank_name": "Banque Populaire",
            "bank_rib": "181780000234567890123456",
            "active": True
        }
    )

    # 3. Trainer 3: Salma Bennani
    t3, _ = Trainer.objects.get_or_create(
        cin="CD345678",
        defaults={
            "first_name_fr": "Salma",
            "last_name_fr": "Bennani",
            "first_name_ar": "سلمى",
            "last_name_ar": "بناني",
            "phone": "0663344556",
            "email": "salma.bennani@gca.ma",
            "specialty": "Calcul Mental Soroban",
            "address": "Sidi Kacem",
            "compensation_type": "per_session",
            "default_rate": Decimal("120.00"),
            "bank_name": "CIH Bank",
            "bank_rib": "230780000345678901234567",
            "active": True
        }
    )

    # Link schedules
    for sch in SessionSchedule.objects.all():
        name_lower = (sch.trainer_name_fr or "").lower()
        if "yassine" in name_lower:
            sch.trainer = t1
        elif "mehdi" in name_lower:
            sch.trainer = t2
        elif "salma" in name_lower:
            sch.trainer = t3
        elif not sch.trainer:
            sch.trainer = t1
        sch.save()

    # Create / Link User accounts for each trainer
    trainers_info = [
        (t1, "trainer_yassine"),
        (t2, "trainer_mehdi"),
        (t3, "trainer_salma"),
    ]
    encoded_pw = make_password("Trainer@2026")
    for tr, username in trainers_info:
        u = User.objects.filter(username=username).first()
        if not u:
            u = User.objects.create(
                username=username,
                password=encoded_pw,
                first_name=tr.first_name_fr,
                last_name=tr.last_name_fr,
                email=tr.email,
                role="trainer",
                preferred_language="fr",
                phone=tr.phone
            )
        if not tr.user:
            tr.user = u
            tr.save()


def reverse_seed(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('academy', '0006_trainer_sessionschedule_trainer'),
    ]

    operations = [
        migrations.RunPython(seed_trainers, reverse_seed),
    ]
