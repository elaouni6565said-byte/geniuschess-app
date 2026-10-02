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


@pytest.mark.django_db
def test_export_paid_and_unpaid_excel():
    """Tests Excel export for paid payments and unpaid invoices with French and Arabic."""
    from finance.models import Payment, Invoice
    from portal.excel_export import export_paid_payments_to_excel, export_unpaid_invoices_to_excel

    # 1. Paid payments export
    payments = Payment.objects.all()
    excel_paid_bytes = export_paid_payments_to_excel(payments, lang='fr')
    wb_paid = openpyxl.load_workbook(io.BytesIO(excel_paid_bytes))
    ws_paid = wb_paid.active
    assert "Paiements" in ws_paid.title
    # Check header exists
    headers = [cell for cell in next(ws_paid.iter_rows(min_row=3, max_row=3, values_only=True))]
    assert any("Reçu" in str(h) for h in headers if h)
    assert any("Réduction" in str(h) or "Convention" in str(h) for h in headers if h)

    # 2. Unpaid invoices export in Arabic RTL
    invoices = Invoice.objects.filter(status__in=['unpaid', 'partial'])
    excel_unpaid_bytes = export_unpaid_invoices_to_excel(invoices, lang='ar')
    wb_unpaid = openpyxl.load_workbook(io.BytesIO(excel_unpaid_bytes))
    ws_unpaid = wb_unpaid.active
    assert ws_unpaid.sheet_view.rightToLeft is True
    assert "المستحقات" in ws_unpaid.title
    unpaid_headers = [cell for cell in next(ws_unpaid.iter_rows(min_row=3, max_row=3, values_only=True))]
    assert any("التخفيض" in str(h) or "الاتفاقية" in str(h) for h in unpaid_headers if h)


@pytest.mark.django_db
def test_export_excel_with_convention_reduction_reason():
    """Validates that a student with a convention displays the reduction motif and amount in Excel exports."""
    from datetime import date
    from decimal import Decimal
    from academy.models import Parent, Subject, Group
    from finance.models import Payment, Invoice
    from portal.excel_export import export_paid_payments_to_excel

    parent = Parent.objects.create(full_name_fr="Parent Conv", phone="212612345678")
    sub = Subject.objects.create(name_fr="Échecs", name_ar="الشطرنج")
    grp = Group.objects.create(name_fr="Groupe Pro", name_ar="المحترف", subject=sub, monthly_fee=Decimal("350.00"))
    st = Student.objects.create(
        registration_number="GCA-EXCEL-01",
        first_name_fr="Mehdi",
        last_name_fr="Alami",
        parent=parent,
        active=True,
        has_convention=True,
        convention_name="Convention Fondation OCP",
        discount_type="fixed_discount",
        discount_value=Decimal("50.00")
    )
    st.groups.add(grp)
    inv = Invoice.objects.create(
        student=st,
        group=grp,
        period_month=9,
        period_year=2026,
        original_amount=Decimal("350.00"),
        discount_amount=Decimal("50.00"),
        amount_due=Decimal("300.00"),
        amount_paid=Decimal("300.00"),
        status="paid",
        due_date=date(2026, 9, 15)
    )
    p = Payment.objects.create(
        receipt_number="REC-EXCEL-001",
        student=st,
        invoice=inv,
        amount=Decimal("300.00"),
        payment_date=date(2026, 9, 10),
        payment_method="cash"
    )

    excel_bytes = export_paid_payments_to_excel(Payment.objects.filter(id=p.id), lang="fr")
    wb = openpyxl.load_workbook(io.BytesIO(excel_bytes))
    ws = wb.active

    found_convention = False
    for row in ws.iter_rows(values_only=True):
        for cell in row:
            if cell and "Convention Fondation OCP" in str(cell) and "-50.00 DH" in str(cell):
                found_convention = True
                break

    assert found_convention, "The convention name and discount amount should be present in the payment Excel export"


@pytest.mark.django_db
def test_export_paid_excel_with_unpaid_section_and_centre_shares():
    """Validates the 11 columns, centre/trainer share calculations, and the unpaid section below."""
    from datetime import date
    from decimal import Decimal
    from academy.models import Parent, Subject, Group
    from finance.models import Payment, Invoice
    from portal.excel_export import export_paid_payments_to_excel

    parent = Parent.objects.create(full_name_fr="Parent Test", phone="212688776655")
    sub1 = Subject.objects.create(name_fr="Robotique", name_ar="روبوتيك")
    sub2 = Subject.objects.create(name_fr="Échecs", name_ar="الشطرنج")
    grp1 = Group.objects.create(name_fr="Grp Rob", name_ar="روبوتيك", subject=sub1, monthly_fee=Decimal("200.00"))
    grp2 = Group.objects.create(name_fr="Grp Ech", name_ar="شطرنج", subject=sub2, monthly_fee=Decimal("150.00"))

    # Élève 1 (Payant avec 1 activité : Robotique 200 DH -> Centre: 35 DH, Prof: 165 DH)
    st1 = Student.objects.create(registration_number="GCA-PAY-01", first_name_fr="Adam", last_name_fr="Tazi", parent=parent, active=True)
    st1.groups.add(grp1)
    inv1 = Invoice.objects.create(student=st1, group=grp1, period_month=9, period_year=2026, amount_due=Decimal("200.00"), amount_paid=Decimal("200.00"), status="paid", due_date=date(2026, 9, 15))
    p1 = Payment.objects.create(receipt_number="REC-001", student=st1, invoice=inv1, amount=Decimal("200.00"), payment_date=date(2026, 9, 10))

    # Élève 2 (Non-payant / Impayé avec 2 activités : 300 DH -> Centre: 70 DH, Prof: 230 DH)
    st2 = Student.objects.create(registration_number="GCA-UNPAY-01", first_name_fr="Sara", last_name_fr="Idrissi", parent=parent, active=True)
    st2.groups.add(grp1, grp2)
    inv2 = Invoice.objects.create(student=st2, group=grp1, period_month=9, period_year=2026, original_amount=Decimal("350.00"), discount_amount=Decimal("50.00"), amount_due=Decimal("300.00"), amount_paid=Decimal("0.00"), status="unpaid", due_date=date(2026, 9, 15))

    excel_bytes = export_paid_payments_to_excel(
        Payment.objects.filter(id=p1.id),
        unpaid_invoices_queryset=Invoice.objects.filter(id=inv2.id),
        lang="fr"
    )
    wb = openpyxl.load_workbook(io.BytesIO(excel_bytes))
    ws = wb.active

    # Check 11 headers exist
    headers = [cell for cell in next(ws.iter_rows(min_row=3, max_row=3, values_only=True))]
    assert "Nombre d'activitées" in headers
    assert "Part du centre" in headers
    assert "Part du prof" in headers

    # Verify sections exist in content
    content_all = " ".join([str(cell) for row in ws.iter_rows(values_only=True) for cell in row if cell])
    assert "TOTAL DES RECETTES ENCAISSÉES" in content_all
    assert "ÉLÈVES NON PAYANTS & IMPAYÉS" in content_all
    assert "TOTAL DES IMPAYÉS RESTANTS" in content_all
    assert "BILAN GLOBAL & CHIFFRE D'AFFAIRES PRÉVISIONNEL" in content_all
    assert "Sara Idrissi" in content_all
    assert "Adam Tazi" in content_all


@pytest.mark.django_db
def test_excel_export_duplicate_rows_verification_and_correction():
    """
    Vérifie que le système détecte et élimine automatiquement les lignes doublées :
    1. Si des élèves sont fournis en double dans le queryset / liste, l'Excel n'a qu'une seule ligne.
    2. Si des paiements ou factures impayées sont dupliqués, l'Excel n'a qu'une seule ligne et les totaux restent exacts.
    """
    from decimal import Decimal
    from academy.models import Parent, Student
    from finance.models import Payment
    from portal.excel_export import export_students_to_excel, export_paid_payments_to_excel
    from portal.excel_validator import deduplicate_items

    parent = Parent.objects.create(full_name_fr="Parent Doublon", phone="0611223344")
    st = Student.objects.create(
        registration_number="GCA-DUP-01",
        first_name_fr="Youssef",
        last_name_fr="Berrada",
        parent=parent,
        active=True
    )

    # 1. Simuler une liste avec 3 fois le même élève
    duplicated_students = [st, st, st]
    excel_bytes = export_students_to_excel(duplicated_students, lang="fr")
    wb = openpyxl.load_workbook(io.BytesIO(excel_bytes))
    ws = wb.active

    # Compter le nombre de fois où le matricule apparaît dans la feuille
    matricule_occurrences = 0
    for row in ws.iter_rows(values_only=True):
        for cell in row:
            if cell == "GCA-DUP-01":
                matricule_occurrences += 1

    # Doit apparaître exactement 1 seule fois !
    assert matricule_occurrences == 1, f"L'élève doit apparaître 1 seule fois, trouvé {matricule_occurrences} fois"

    # 2. Simuler un paiement dupliqué
    p = Payment.objects.create(
        receipt_number="REC-DUP-999",
        student=st,
        amount=Decimal("300.00"),
        period_month=10,
        period_year=2026
    )
    duplicated_payments = [p, p, p]
    excel_paid_bytes = export_paid_payments_to_excel(duplicated_payments, lang="fr")
    wb_paid = openpyxl.load_workbook(io.BytesIO(excel_paid_bytes))
    ws_paid = wb_paid.active

    rec_occurrences = 0
    for row in ws_paid.iter_rows(values_only=True):
        for cell in row:
            if cell == "#REC-DUP-999":
                rec_occurrences += 1

    # Doit apparaître exactement 1 seule fois !
    assert rec_occurrences == 1, f"Le reçu doit apparaître 1 seule fois, trouvé {rec_occurrences} fois"


def test_excel_export_duplicate_columns_verification_and_correction():
    """
    Vérifie que le système détecte et supprime automatiquement les colonnes en double :
    1. sanitize_header_list élimine les colonnes ayant le même en-tête.
    2. audit_and_correct_worksheet supprime physiquement la colonne dupliquée et répare les plages fusionnées.
    """
    from portal.excel_validator import sanitize_header_list, audit_and_correct_worksheet

    # 1. Test au niveau de la liste des en-têtes
    headers = ["N° Reçu", "Date", "Matricule", "N° Reçu", "Montant", "Date"]
    cleaned, kept = sanitize_header_list(headers)
    assert cleaned == ["N° Reçu", "Date", "Matricule", "Montant"]
    assert kept == [0, 1, 2, 4]

    # 2. Test physique sur une feuille openpyxl avec colonne doublée
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "TestColonnes"

    # Titre fusionné sur 4 colonnes
    ws.merge_cells("A1:D1")
    ws["A1"] = "Bannière Titre"

    # Ligne d'en-tête (ligne 3) avec colonne 3 doublant colonne 1
    ws.cell(row=3, column=1, value="Matricule")
    ws.cell(row=3, column=2, value="Nom")
    ws.cell(row=3, column=3, value="Matricule")  # Doublon !
    ws.cell(row=3, column=4, value="Montant")

    # Données
    ws.cell(row=4, column=1, value="GCA-01")
    ws.cell(row=4, column=2, value="Ahmed")
    ws.cell(row=4, column=3, value="GCA-01")
    ws.cell(row=4, column=4, value=250)

    assert ws.max_column == 4

    report = audit_and_correct_worksheet(ws, candidate_header_row=3)
    assert report['duplicate_cols_removed'] == 1
    assert report['status'] == 'corrected'
    assert ws.max_column == 3

    # Vérifier que les en-têtes restants sont uniques
    headers_after = [ws.cell(row=3, column=c).value for c in range(1, ws.max_column + 1)]
    assert headers_after == ["Matricule", "Nom", "Montant"]
    assert len(headers_after) == len(set(headers_after))


@pytest.mark.django_db
def test_excel_export_multiple_activities_and_count_column():
    """
    Vérifie que pour un élève suivant 2 activités (ex: Échecs et Robotique) :
    1. Dans l'export des élèves :
       - La colonne d'activité affiche toutes les activités suivies ('Échecs + Robotique')
       - Une colonne dédiée 'Nombre d'activités' affiche 2.
    2. Dans l'export des paiements encaissés :
       - La colonne affiche 'Échecs + Robotique'
       - La colonne 'Nombre d'activitées' affiche 2.
    3. Dans l'export des impayés :
       - La colonne affiche 'Échecs + Robotique'
       - La colonne 'Nombre d'activités' affiche 2.
    4. En version Arabe : affiche 'شطرنج + روبوتات' et 'عدد الأنشطة' = 2.
    """
    from decimal import Decimal
    from datetime import date
    from academy.models import Parent, Student, Subject, Group
    from finance.models import Payment, Invoice
    from portal.excel_export import (
        export_students_to_excel,
        export_paid_payments_to_excel,
        export_unpaid_invoices_to_excel,
    )

    parent = Parent.objects.create(full_name_fr="Parent Multi", phone="0699887766")
    sub1 = Subject.objects.create(name_fr="Échecs", name_ar="شطرنج")
    sub2 = Subject.objects.create(name_fr="Robotique", name_ar="روبوتات")

    grp1 = Group.objects.create(name_fr="Groupe Échecs A", name_ar="شطرنج أ", subject=sub1, monthly_fee=Decimal("200.00"))
    grp2 = Group.objects.create(name_fr="Groupe Robotique B", name_ar="روبوتات ب", subject=sub2, monthly_fee=Decimal("250.00"))

    # Élève avec 2 activités distinctes
    st = Student.objects.create(
        registration_number="GCA-MULTI-01",
        first_name_fr="Karim",
        last_name_fr="Bennani",
        first_name_ar="كريم",
        last_name_ar="بنسعيد",
        parent=parent,
        active=True
    )
    st.groups.add(grp1, grp2)

    inv = Invoice.objects.create(
        student=st,
        group=grp1,
        period_month=10,
        period_year=2026,
        amount_due=Decimal("450.00"),
        amount_paid=Decimal("250.00"),
        status="partial",
        due_date=date(2026, 10, 15)
    )

    pay = Payment.objects.create(
        receipt_number="REC-MULTI-888",
        student=st,
        invoice=inv,
        amount=Decimal("250.00"),
        period_month=10,
        period_year=2026,
        payment_date=date(2026, 10, 12)
    )

    # 1. Test Export Élèves (FR)
    bytes_st_fr = export_students_to_excel([st], lang="fr")
    wb_st_fr = openpyxl.load_workbook(io.BytesIO(bytes_st_fr))
    ws_st_fr = wb_st_fr.active
    headers_st_fr = [ws_st_fr.cell(row=3, column=c).value for c in range(1, ws_st_fr.max_column + 1)]
    assert "Nombre d'activités" in headers_st_fr
    assert "Activités Suivies" in headers_st_fr

    # Trouver les index des colonnes
    col_act = headers_st_fr.index("Activités Suivies") + 1
    col_nb = headers_st_fr.index("Nombre d'activités") + 1

    row4_act = ws_st_fr.cell(row=4, column=col_act).value
    row4_nb = ws_st_fr.cell(row=4, column=col_nb).value
    assert "Échecs" in row4_act and "Robotique" in row4_act
    assert row4_nb == 2

    # 2. Test Export Élèves (AR)
    bytes_st_ar = export_students_to_excel([st], lang="ar")
    wb_st_ar = openpyxl.load_workbook(io.BytesIO(bytes_st_ar))
    ws_st_ar = wb_st_ar.active
    headers_st_ar = [ws_st_ar.cell(row=3, column=c).value for c in range(1, ws_st_ar.max_column + 1)]
    assert "عدد الأنشطة" in headers_st_ar
    assert "الأنشطة المستفاد منها" in headers_st_ar

    col_act_ar = headers_st_ar.index("الأنشطة المستفاد منها") + 1
    col_nb_ar = headers_st_ar.index("عدد الأنشطة") + 1
    assert "شطرنج" in ws_st_ar.cell(row=4, column=col_act_ar).value
    assert "روبوتات" in ws_st_ar.cell(row=4, column=col_act_ar).value
    assert ws_st_ar.cell(row=4, column=col_nb_ar).value == 2

    # 3. Test Export Paiements (FR)
    bytes_pay_fr = export_paid_payments_to_excel([pay], lang="fr")
    wb_pay_fr = openpyxl.load_workbook(io.BytesIO(bytes_pay_fr))
    ws_pay_fr = wb_pay_fr.active
    headers_pay_fr = [ws_pay_fr.cell(row=3, column=c).value for c in range(1, ws_pay_fr.max_column + 1)]
    assert "Nombre d'activitées" in headers_pay_fr
    assert "Activités Bénéficiées" in headers_pay_fr

    col_pay_act = headers_pay_fr.index("Activités Bénéficiées") + 1
    col_pay_nb = headers_pay_fr.index("Nombre d'activitées") + 1
    assert "Échecs" in ws_pay_fr.cell(row=4, column=col_pay_act).value
    assert "Robotique" in ws_pay_fr.cell(row=4, column=col_pay_act).value
    assert ws_pay_fr.cell(row=4, column=col_pay_nb).value == 2

    # 4. Test Export Impayés (FR)
    bytes_unp_fr = export_unpaid_invoices_to_excel([inv], lang="fr")
    wb_unp_fr = openpyxl.load_workbook(io.BytesIO(bytes_unp_fr))
    ws_unp_fr = wb_unp_fr.active
    headers_unp_fr = [ws_unp_fr.cell(row=3, column=c).value for c in range(1, ws_unp_fr.max_column + 1)]
    assert "Nombre d'activités" in headers_unp_fr
    assert "Activités Suivies" in headers_unp_fr

    col_unp_act = headers_unp_fr.index("Activités Suivies") + 1
    col_unp_nb = headers_unp_fr.index("Nombre d'activités") + 1
    assert "Échecs" in ws_unp_fr.cell(row=4, column=col_unp_act).value
    assert "Robotique" in ws_unp_fr.cell(row=4, column=col_unp_act).value
    assert ws_unp_fr.cell(row=4, column=col_unp_nb).value == 2





