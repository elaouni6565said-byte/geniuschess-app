with open('scripts/seed_demo_data.py', 'r', encoding='utf-8') as f:
    text = f.read()

wipe_code = '''
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
'''

if 'Invoice.objects.all().delete()' not in text:
    text = text.replace('print("Seeding bilingual GCA database...")', 'print("Seeding bilingual GCA database...")\n' + wipe_code)

attendances_code = '''
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
'''

if 'Attendance.objects.create' not in text:
    text = text.replace('print("Demo data seeded successfully!")', attendances_code + '\nprint("Demo data seeded successfully!")')

with open('scripts/seed_demo_data.py', 'w', encoding='utf-8') as f:
    f.write(text)

print('Updated seed_demo_data.py!')
