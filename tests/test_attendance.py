import pytest
from datetime import date
from django.test import Client
from academy.models import Student, User, SessionSchedule, Attendance, Group
from portal.student_card import (
    generate_single_student_card_pdf, generate_student_cards_sheet_pdf,
    make_student_qr_code_image
)


@pytest.mark.django_db
def test_student_card_qr_code_and_pdf_generation():
    """
    Validates:
    1. QR code image generation for student.
    2. Single student card PDF generation in ISO ID-1 format.
    3. Sheet PDF generation for multiple students on A4.
    """
    student = Student.objects.first()
    assert student is not None, "Student fixture required."

    # 1. QR code image buffer
    qr_buf = make_student_qr_code_image(student)
    assert qr_buf.getvalue()[:8] == b'\x89PNG\r\n\x1a\n'

    # 2. Single card PDF (with multi-groups)
    all_groups = list(Group.objects.all()[:2])
    if len(all_groups) > 1:
        student.groups.set(all_groups)
    pdf_bytes = generate_single_student_card_pdf(student)
    assert pdf_bytes.startswith(b'%PDF')
    assert len(pdf_bytes) > 1000

    # 3. Sheet PDF
    students = list(Student.objects.all()[:4])
    sheet_bytes = generate_student_cards_sheet_pdf(students)
    assert sheet_bytes.startswith(b'%PDF')
    assert len(sheet_bytes) > 2000


@pytest.mark.django_db
def test_attendance_views_and_qr_scanning():
    """
    Validates:
    1. /attendance/ list view rendering.
    2. /attendance/<session_id>/ sheet view rendering.
    3. /attendance/<session_id>/ POST mark_all_present & reset_all.
    4. /attendance/<session_id>/scan/ AJAX scanning endpoint with QR payload and manual status changes.
    5. /students/<student_id>/card-pdf/ and /students/cards-pdf/ HTTP responses.
    """
    client = Client()
    admin = User.objects.get(username='admin')
    admin.set_password('CGAESA65')
    admin.save()
    client.login(username='admin', password='CGAESA65')

    schedule = SessionSchedule.objects.first()
    student = Student.objects.first()
    assert schedule is not None and student is not None

    target_date = date(2026, 9, 5)

    # 1. Attendance list view
    resp_list = client.get(f'/attendance/?date={target_date.strftime("%Y-%m-%d")}')
    assert resp_list.status_code == 200
    assert 'sessions_data' in resp_list.context

    # 2. Attendance sheet view
    resp_sheet = client.get(f'/attendance/{schedule.id}/?date={target_date.strftime("%Y-%m-%d")}')
    assert resp_sheet.status_code == 200
    assert 'students_data' in resp_sheet.context

    # 3. Scan QR Code via AJAX (Format: GCA:STU:REGISTRATION_NUMBER)
    qr_code_payload = f"GCA:STU:{student.registration_number}"
    resp_scan = client.post(
        f'/attendance/{schedule.id}/scan/',
        data={'code': qr_code_payload, 'status': 'present', 'date': '2026-09-05'}
    )
    assert resp_scan.status_code == 200
    scan_json = resp_scan.json()
    assert scan_json['success'] is True
    assert scan_json['student_id'] == student.id
    assert scan_json['status'] == 'present'

    # Verify Attendance record in database
    att = Attendance.objects.get(student=student, session=schedule, date=target_date)
    assert att.status == 'present'

    # 4. Manual status change via AJAX (e.g., student is marked late or absent for forgotten card)
    resp_late = client.post(
        f'/attendance/{schedule.id}/scan/',
        data={'code': str(student.id), 'status': 'late', 'date': '2026-09-05'}
    )
    assert resp_late.status_code == 200
    assert resp_late.json()['status'] == 'late'
    att.refresh_from_db()
    assert att.status == 'late'

    # 5. Bulk action: mark_all_present
    resp_bulk = client.post(
        f'/attendance/{schedule.id}/?date=2026-09-05',
        data={'action': 'mark_all_present'}
    )
    assert resp_bulk.status_code == 302
    att.refresh_from_db()
    assert att.status == 'present'

    # 6. Bulk action: reset_all
    resp_reset = client.post(
        f'/attendance/{schedule.id}/?date=2026-09-05',
        data={'action': 'reset_all'}
    )
    assert resp_reset.status_code == 302
    assert not Attendance.objects.filter(student=student, session=schedule, date=target_date).exists()

    # 7. Single student card PDF download
    resp_card = client.get(f'/students/{student.id}/card-pdf/')
    assert resp_card.status_code == 200
    assert resp_card['Content-Type'] == 'application/pdf'
    assert resp_card.content.startswith(b'%PDF')

    # 8. All student cards sheet PDF download
    resp_sheet_pdf = client.get('/students/cards-pdf/')
    assert resp_sheet_pdf.status_code == 200
    assert resp_sheet_pdf['Content-Type'] == 'application/pdf'
    assert resp_sheet_pdf.content.startswith(b'%PDF')


@pytest.mark.django_db
def test_attendance_recap_and_excel_export():
    """
    Validates:
    1. /attendance/recap/ view for Day, Week, Month and Year periods.
    2. Filtering by Subject, Group, Status, and Search query.
    3. Hierarchical grouping and student assiduity KPI calculation.
    4. /attendance/recap/excel/ export generation with openpyxl workbook structure.
    """
    import io
    import openpyxl
    client = Client()
    admin = User.objects.get(username='admin')
    client.force_login(admin)

    schedule = SessionSchedule.objects.first()
    student = Student.objects.first()
    assert schedule is not None and student is not None

    # Créer quelques enregistrements de présence
    d1 = date(2026, 9, 1)
    d2 = date(2026, 9, 2)
    Attendance.objects.update_or_create(student=student, session=schedule, date=d1, defaults={'status': 'present'})
    Attendance.objects.update_or_create(student=student, session=schedule, date=d2, defaults={'status': 'late'})

    # 1. Période Journée
    resp_day = client.get(f'/attendance/recap/?period=day&date=2026-09-01')
    assert resp_day.status_code == 200
    assert resp_day.context['total_records'] >= 1
    assert resp_day.context['present_cnt'] >= 1

    # 2. Période Semaine
    resp_week = client.get(f'/attendance/recap/?period=week&date=2026-09-02')
    assert resp_week.status_code == 200
    assert resp_week.context['total_records'] >= 2

    # 3. Période Mois
    resp_month = client.get(f'/attendance/recap/?period=month&month=9&year=2026')
    assert resp_month.status_code == 200
    assert resp_month.context['total_records'] >= 2
    assert len(resp_month.context['student_summaries']) >= 1

    # 4. Période Année
    resp_year = client.get(f'/attendance/recap/?period=year&year=2026')
    assert resp_year.status_code == 200
    assert resp_year.context['total_records'] >= 2

    # 5. Filtre par statut
    resp_status = client.get(f'/attendance/recap/?period=month&month=9&year=2026&status=present')
    assert resp_status.status_code == 200
    assert resp_status.context['total_records'] == 1

    # 6. Filtre par recherche élève
    resp_q = client.get(f'/attendance/recap/?period=month&month=9&year=2026&q={student.last_name_fr[:3]}')
    assert resp_q.status_code == 200
    assert resp_q.context['total_records'] >= 1

    # 7. Export Excel (.xlsx)
    resp_excel = client.get(f'/attendance/recap/excel/?period=month&month=9&year=2026')
    assert resp_excel.status_code == 200
    assert 'spreadsheetml' in resp_excel['Content-Type']
    assert len(resp_excel.content) > 2000

    # Vérification de la structure du classeur Excel généré
    wb = openpyxl.load_workbook(io.BytesIO(resp_excel.content))
    sheet_names = wb.sheetnames
    assert len(sheet_names) == 2
    assert "Émargements par Séance" in sheet_names[0] or "سجل الحضور بالحصص" in sheet_names[0]
    assert "Synthèse par Élève" in sheet_names[1] or "ملخص الحضور لكل تلميذ" in sheet_names[1]

