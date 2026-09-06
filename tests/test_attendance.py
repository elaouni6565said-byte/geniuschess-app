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
