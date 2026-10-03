import datetime
from django.db import migrations, models


def update_robotique_schedule(apps, schema_editor):
    SessionSchedule = apps.get_model('academy', 'SessionSchedule')
    Group = apps.get_model('academy', 'Group')
    Level = apps.get_model('academy', 'Level')
    Subject = apps.get_model('academy', 'Subject')

    adv_level = Level.objects.filter(name_fr__icontains='Avanc').first()

    # Trouver le groupe robotique existant
    robotics_groups = Group.objects.filter(
        models.Q(name_fr__icontains='robot') | models.Q(subject__name_fr__icontains='robot')
    )

    if robotics_groups.exists():
        target_group = robotics_groups.first()
        target_group.name_fr = "Groupe Robotique N3"
        target_group.name_ar = "مجموعة الروبوتيك N3"
        if adv_level:
            target_group.level = adv_level
        target_group.save()
    else:
        subj = Subject.objects.filter(name_fr__icontains='robot').first()
        if not subj:
            subj = Subject.objects.create(name_fr="Robotique", name_ar="الروبوتيك")
        target_group = Group.objects.create(
            name_fr="Groupe Robotique N3",
            name_ar="مجموعة الروبوتيك N3",
            subject=subj,
            level=adv_level,
        )

    # Mettre à jour ou créer la séance Robotique N3 le dimanche de 10h30 à 12h00 avec notification à 09h30
    sched = SessionSchedule.objects.filter(group=target_group).first()
    if sched:
        sched.day_of_week = 6  # Dimanche
        sched.start_time = datetime.time(10, 30)
        sched.end_time = datetime.time(12, 0)
        sched.notification_time = datetime.time(9, 30)
        sched.save()
    else:
        SessionSchedule.objects.create(
            group=target_group,
            day_of_week=6,
            start_time=datetime.time(10, 30),
            end_time=datetime.time(12, 0),
            notification_time=datetime.time(9, 30),
            trainer_name_fr="Formateur GCA",
            trainer_name_ar="مدرب الأكاديمية",
        )

    # Compléter les séances sans notification_time
    for s in SessionSchedule.objects.filter(notification_time__isnull=True):
        s.notification_time = datetime.time(9, 30)
        s.save()


def reverse_update(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('academy', '0007_student_convention_name_student_discount_type_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='sessionschedule',
            name='notification_time',
            field=models.TimeField(
                blank=True,
                default=datetime.time(9, 30),
                help_text="Heure d'envoi du rappel WhatsApp (ex: 09:30)",
                null=True,
                verbose_name='Heure de notification / وقت إرسال التذكير'
            ),
        ),
        migrations.RunPython(update_robotique_schedule, reverse_update),
    ]
