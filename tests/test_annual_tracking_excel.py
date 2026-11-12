import io
from datetime import date, time
from decimal import Decimal
import pytest
from django.test import Client
from django.urls import reverse
from openpyxl import load_workbook

from academy.models import User, Subject, Group, Parent, Student, SessionSchedule, Attendance
from finance.models import Invoice, Payment, PaymentExemption
from portal.excel_annual_matrix import generate_annual_tracking_excel


@pytest.mark.django_db
def test_annual_tracking_excel_structure_and_data():
    # 1. Créer activités, groupes, formateurs
    subj_chess = Subject.objects.create(name_fr="Échecs", name_ar="شطرنج")
    subj_robot = Subject.objects.create(name_fr="Robotique", name_ar="روبوتيك")

    grp_chess = Group.objects.create(name_fr="Échecs N3", name_ar="شطرنج 3", subject=subj_chess, monthly_fee=Decimal("300.00"))
    grp_robot = Group.objects.create(name_fr="Robotique N3", name_ar="روبوتيك 3", subject=subj_robot, monthly_fee=Decimal("350.00"))

    sched_chess = SessionSchedule.objects.create(
        group=grp_chess,
        trainer_name_fr="Elaouni Said",
        trainer_name_ar="سعيد العوني",
        day_of_week=5,
        start_time=time(10, 0),
        end_time=time(11, 30),
    )
    sched_robot = SessionSchedule.objects.create(
        group=grp_robot,
        trainer_name_fr="Elaouni",
        trainer_name_ar="العوني",
        day_of_week=6,
        start_time=time(14, 0),
        end_time=time(15, 30),
    )

    parent = Parent.objects.create(
        full_name_fr="Parent Test",
        full_name_ar="ولي الأمر",
        phone="0600000001",
    )

    st1 = Student.objects.create(
        registration_number="GCA-T01",
        first_name_fr="Malak",
        last_name_fr="Chahboun",
        first_name_ar="ملاك",
        last_name_ar="شهبون",
        parent=parent,
        active=True,
    )
    st1.groups.add(grp_chess, grp_robot)

    st2 = Student.objects.create(
        registration_number="GCA-T02",
        first_name_fr="Majd",
        last_name_fr="Elabdali",
        first_name_ar="مجد",
        last_name_ar="العبدلي",
        parent=parent,
        active=True,
    )
    st2.groups.add(grp_chess)

    st_unassigned = Student.objects.create(
        registration_number="GCA-T03",
        first_name_fr="Amine",
        last_name_fr="Sansgroupe",
        first_name_ar="أمين",
        last_name_ar="بدون فوج",
        parent=parent,
        active=True,
    )

    # 2. Présences en Novembre 2026 (mois index 2 dans Sept..Juin)
    Attendance.objects.create(student=st1, session=sched_chess, date=date(2026, 11, 7), status="present")
    Attendance.objects.create(student=st2, session=sched_chess, date=date(2026, 11, 7), status="late")
    Attendance.objects.create(student=st1, session=sched_chess, date=date(2026, 11, 14), status="absent")
    Attendance.objects.create(student=st2, session=sched_chess, date=date(2026, 11, 14), status="justified")

    # 3. Paiements et exonérations
    Invoice.objects.create(
        student=st1,
        group=grp_chess,
        period_month=11,
        period_year=2026,
        amount_due=Decimal("300.00"),
        amount_paid=Decimal("300.00"),
        status="paid",
        due_date=date(2026, 11, 15),
    )
    PaymentExemption.objects.create(
        student=st2,
        period_month=11,
        period_year=2026,
        reason="Bourse",
    )

    # 4. Générer le classeur Excel
    excel_bytes = generate_annual_tracking_excel(academic_start_year=2026, lang="fr")
    wb = load_workbook(io.BytesIO(excel_bytes))

    # Vérifier les onglets : Suivi Global + Échecs + Robotique
    assert "Suivi Global" in wb.sheetnames
    assert "Échecs" in wb.sheetnames
    assert "Robotique" in wb.sheetnames

    ws = wb["Suivi Global"]
    all_values = [
        [cell.value for cell in row]
        for row in ws.iter_rows(values_only=False)
    ]

    flat_text = "\n".join(" | ".join(str(v) for v in r if v is not None) for r in all_values)
    assert "Échecs N3" in flat_text
    assert "Robotique N3" in flat_text
    assert "Elaouni Said" in flat_text
    assert "Malak Chahboun" in flat_text
    assert "Majd Elabdali" in flat_text
    assert "Amine Sansgroupe" in flat_text
    assert "Novembre 2026" in flat_text
    assert "S1" in flat_text and "S4" in flat_text
    assert "Payé" in flat_text

    # Vérifier les codes P, A, R, J et OUI / EXONÉRÉ sur l'onglet Échecs
    ws_chess = wb["Échecs"]
    chess_values = [
        [cell.value for cell in row]
        for row in ws_chess.iter_rows(values_only=False)
    ]
    malak_row = next(r for r in chess_values if len(r) > 1 and r[1] == "Malak Chahboun")
    majd_row = next(r for r in chess_values if len(r) > 1 and r[1] == "Majd Elabdali")

    # Novembre 2026 est le 3ème mois (index 2 : Sept=0, Oct=1, Nov=2) -> colonnes 0-based : 2 + 2*6 = 14 (S1), 15 (S2), 18 (OUI), 19 (NON)
    nov_base = 2 + 2 * 6
    assert malak_row[nov_base] == "P"
    assert malak_row[nov_base + 1] == "A"
    assert malak_row[nov_base + 4] == "OUI"

    assert majd_row[nov_base] == "R"
    assert majd_row[nov_base + 1] == "J"
    assert majd_row[nov_base + 4] == "EXONÉRÉ"

    # Vérifier la ligne de total des payants du groupe Échecs N3
    total_grp_row = next(
        r for r in chess_values
        if r and r[0] and "TOTAL PAYANTS (Échecs N3)" in str(r[0])
    )
    assert total_grp_row[nov_base + 4] == 1  # 1 payant (Malak Chahboun)
    assert "Payants: 1 (+1 Exon.)" in str(total_grp_row[nov_base])

    # Vérifier la ligne de total général en bas de la feuille
    grand_tot_row = next(
        r for r in chess_values
        if r and r[0] and "TOTAL GÉNÉRAL PAYANTS" in str(r[0])
    )
    assert grand_tot_row[nov_base + 4] >= 1


@pytest.mark.django_db
def test_annual_tracking_excel_endpoint():
    admin = User.objects.create_superuser(username="admin_exp", password="pwd", role="admin")
    subj = Subject.objects.create(name_fr="Calcul Mental", name_ar="الحساب الذهني")
    Group.objects.create(name_fr="CM Groupe 1", name_ar="فوج 1", subject=subj)

    client = Client()
    client.force_login(admin)

    url = reverse("portal:export_annual_tracking_excel")
    resp = client.get(url)
    assert resp.status_code == 200
    assert resp["Content-Type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    wb = load_workbook(io.BytesIO(resp.content))
    assert len(wb.sheetnames) >= 1

    # Avec filtre subject
    resp_filtered = client.get(f"{url}?subject={subj.id}")
    assert resp_filtered.status_code == 200
    wb_f = load_workbook(io.BytesIO(resp_filtered.content))
    assert "Suivi Global" in wb_f.sheetnames

    # Vérifier la présence du bouton dans le tableau de bord et la page des paiements
    dash_resp = client.get(reverse("portal:dashboard"))
    assert dash_resp.status_code == 200
    assert url in dash_resp.content.decode("utf-8")

    pay_resp = client.get(reverse("portal:payments"))
    assert pay_resp.status_code == 200
    assert url in pay_resp.content.decode("utf-8")

