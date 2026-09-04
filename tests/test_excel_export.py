import pytest
import io
import openpyxl
from academy.models import Student
from portal.excel_export import export_students_to_excel

@pytest.mark.django_db
def test_export_excel_bilingual_utf8():
    """Tests Excel export with mixed French and Arabic characters without corruption (47.14 & 47.15)."""
    students = Student.objects.all()
    excel_bytes = export_students_to_excel(students, lang='ar')

    wb = openpyxl.load_workbook(io.BytesIO(excel_bytes))
    ws = wb.active
    assert ws.title == "قائمة التلاميذ"
    assert ws.sheet_view.rightToLeft is True

    # Search for any student name in Arabic and French
    first_student = students.first()
    assert first_student is not None, "At least one student should exist"

    found_arabic = False
    found_french = False
    for row in ws.iter_rows(values_only=True):
        for cell in row:
            if cell and first_student.first_name_ar in str(cell):
                found_arabic = True
            if cell and first_student.first_name_fr in str(cell):
                found_french = True

    assert found_arabic, f"Arabic student name ({first_student.first_name_ar}) should be present in Excel"
    assert found_french, f"French student name ({first_student.first_name_fr}) should be present in Excel"
