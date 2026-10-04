from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('academy', '0009_robotique_wednesday_and_sunday_schedules'),
    ]

    operations = [
        migrations.AddField(
            model_name='attendance',
            name='scanned_at',
            field=models.TimeField(
                blank=True,
                null=True,
                verbose_name='Heure de pointage / وقت التسجيل'
            ),
        ),
    ]
