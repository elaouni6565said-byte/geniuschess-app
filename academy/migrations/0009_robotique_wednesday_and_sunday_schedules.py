import datetime
from django.db import migrations, models


def setup_robotics_schedules(apps, schema_editor):
    Subject = apps.get_model('academy', 'Subject')
    Group = apps.get_model('academy', 'Group')
    Level = apps.get_model('academy', 'Level')
    Room = apps.get_model('academy', 'Room')
    SessionSchedule = apps.get_model('academy', 'SessionSchedule')

    # 1. Matière Robotique
    subj = Subject.objects.filter(name_fr__icontains='robot').first()
    if not subj:
        subj = Subject.objects.create(name_fr="Robotique", name_ar="الروبوتيك", color="#3B82F6")

    lvl_beg = Level.objects.filter(name_fr__icontains='Dél').first() or Level.objects.filter(name_fr__icontains='Déb').first() or Level.objects.first()
    lvl_int = Level.objects.filter(name_fr__icontains='Inter').first() or lvl_beg
    lvl_adv = Level.objects.filter(name_fr__icontains='Avanc').first() or lvl_int

    room_turing = Room.objects.filter(name_fr__icontains='Turing').first()

    # 2. Groupe Mercredi 1 : 14h30 à 16h00
    grp_wed_1, _ = Group.objects.get_or_create(
        name_fr="Groupe Robotique Mercredi 1",
        defaults={
            "name_ar": "مجموعة الروبوتيك الأربعاء 1",
            "subject": subj,
            "level": lvl_beg,
            "monthly_fee": 350.00,
            "color": "#3B82F6",
        }
    )
    # Séance Mercredi 1
    sched_wed_1 = SessionSchedule.objects.filter(group=grp_wed_1, day_of_week=2).first()
    if not sched_wed_1:
        SessionSchedule.objects.create(
            group=grp_wed_1,
            room=room_turing,
            day_of_week=2,  # Mercredi
            start_time=datetime.time(14, 30),
            end_time=datetime.time(16, 0),
            notification_time=datetime.time(13, 30),
            trainer_name_fr="Ingénieur Mehdi",
            trainer_name_ar="المهندس مهدي",
        )
    else:
        sched_wed_1.start_time = datetime.time(14, 30)
        sched_wed_1.end_time = datetime.time(16, 0)
        sched_wed_1.notification_time = datetime.time(13, 30)
        sched_wed_1.save()

    # 3. Groupe Mercredi 2 : 17h30 à 19h00
    grp_wed_2, _ = Group.objects.get_or_create(
        name_fr="Groupe Robotique Mercredi 2",
        defaults={
            "name_ar": "مجموعة الروبوتيك الأربعاء 2",
            "subject": subj,
            "level": lvl_int,
            "monthly_fee": 350.00,
            "color": "#2563EB",
        }
    )
    # Séance Mercredi 2
    sched_wed_2 = SessionSchedule.objects.filter(group=grp_wed_2, day_of_week=2).first()
    if not sched_wed_2:
        SessionSchedule.objects.create(
            group=grp_wed_2,
            room=room_turing,
            day_of_week=2,  # Mercredi
            start_time=datetime.time(17, 30),
            end_time=datetime.time(19, 0),
            notification_time=datetime.time(16, 30),
            trainer_name_fr="Ingénieur Mehdi",
            trainer_name_ar="المهندس مهدي",
        )
    else:
        sched_wed_2.start_time = datetime.time(17, 30)
        sched_wed_2.end_time = datetime.time(19, 0)
        sched_wed_2.notification_time = datetime.time(16, 30)
        sched_wed_2.save()

    # 4. Groupe Dimanche N3 : 10h30 à 12h00
    grp_sun_n3, _ = Group.objects.get_or_create(
        name_fr="Groupe Robotique N3",
        defaults={
            "name_ar": "مجموعة الروبوتيك N3",
            "subject": subj,
            "level": lvl_adv,
            "monthly_fee": 350.00,
            "color": "#1D4ED8",
        }
    )
    sched_sun = SessionSchedule.objects.filter(group=grp_sun_n3, day_of_week=6).first()
    if not sched_sun:
        SessionSchedule.objects.create(
            group=grp_sun_n3,
            room=room_turing,
            day_of_week=6,  # Dimanche
            start_time=datetime.time(10, 30),
            end_time=datetime.time(12, 0),
            notification_time=datetime.time(9, 30),
            trainer_name_fr="Ingénieur Mehdi",
            trainer_name_ar="المهندس مهدي",
        )
    else:
        sched_sun.start_time = datetime.time(10, 30)
        sched_sun.end_time = datetime.time(12, 0)
        sched_sun.notification_time = datetime.time(9, 30)
        sched_sun.save()


def reverse_setup(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('academy', '0008_sessionschedule_notification_time_and_update_robotique'),
    ]

    operations = [
        migrations.RunPython(setup_robotics_schedules, reverse_setup),
    ]
