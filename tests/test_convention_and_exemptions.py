import pytest
from decimal import Decimal
from datetime import date
from django.test import Client
from academy.models import Student, Parent, Group, Subject, User, Attendance, SessionSchedule
from finance.models import Invoice, Payment, PaymentExemption
from portal.views import sync_invoices_with_actual_attendances, get_billable_unpaid_invoices_qs
from portal.forms import StudentForm


@pytest.mark.django_db
def test_convention_pricing_calculations():
    """
    Vérifie les calculs de tarification pour les conventions :
    1. Élève standard sans convention (plein tarif).
    2. Convention avec tarif mensuel forfaitaire personnalisé (ex: 200 DH).
    3. Convention avec réduction en pourcentage (ex: 25% de remise).
    4. Convention avec réduction fixe en montant (ex: -50 DH).
    """
    sub = Subject.objects.create(name_fr="Échecs", name_ar="الشطرنج")
    grp = Group.objects.create(name_fr="Groupe Elite", name_ar="النخبة", subject=sub, monthly_fee=Decimal("400.00"))
    parent = Parent.objects.create(full_name_fr="Parent Test", phone="212611223344")

    # 1. Sans convention
    st_normal = Student.objects.create(
        registration_number="GCA-TEST-01",
        first_name_fr="Amine",
        last_name_fr="Idrissi",
        parent=parent,
        active=True
    )
    st_normal.groups.add(grp)
    base, disc, final = st_normal.calculate_monthly_fee()
    assert base == Decimal("400.00")
    assert disc == Decimal("0.00")
    assert final == Decimal("400.00")

    # 2. Convention Tarif fixe (custom_fee = 250 DH)
    st_custom = Student.objects.create(
        registration_number="GCA-TEST-02",
        first_name_fr="Karim",
        last_name_fr="Tazi",
        parent=parent,
        active=True,
        has_convention=True,
        convention_name="Convention OCP",
        discount_type="custom_fee",
        discount_value=Decimal("250.00")
    )
    st_custom.groups.add(grp)
    base, disc, final = st_custom.calculate_monthly_fee()
    assert base == Decimal("400.00")
    assert disc == Decimal("150.00")
    assert final == Decimal("250.00")

    # 3. Convention Pourcentage (percentage = 20%)
    st_pct = Student.objects.create(
        registration_number="GCA-TEST-03",
        first_name_fr="Salma",
        last_name_fr="Berrada",
        parent=parent,
        active=True,
        has_convention=True,
        convention_name="Convention Enseignants",
        discount_type="percentage",
        discount_value=Decimal("20.00")
    )
    st_pct.groups.add(grp)
    base, disc, final = st_pct.calculate_monthly_fee()
    assert base == Decimal("400.00")
    assert disc == Decimal("80.00")
    assert final == Decimal("320.00")

    # 4. Convention Réduction fixe (fixed_discount = 50 DH)
    st_fixed = Student.objects.create(
        registration_number="GCA-TEST-04",
        first_name_fr="Omar",
        last_name_fr="Alaoui",
        parent=parent,
        active=True,
        has_convention=True,
        convention_name="Convention Fratrie",
        discount_type="fixed_discount",
        discount_value=Decimal("50.00")
    )
    st_fixed.groups.add(grp)
    base, disc, final = st_fixed.calculate_monthly_fee()
    assert base == Decimal("400.00")
    assert disc == Decimal("50.00")
    assert final == Decimal("350.00")


@pytest.mark.django_db
def test_payment_exemptions_and_invoice_sync():
    """
    Vérifie qu'un élève exonéré de paiement pour des mois :
    1. A bien son enregistrement PaymentExemption.
    2. La synchronisation automatique crée une facture avec is_exempt=True, status='exempt', amount_due=0 DH.
    3. Cette facture n'apparaît JAMAIS dans les impayés exigibles get_billable_unpaid_invoices_qs.
    """
    today = date.today()
    month = today.month
    year = today.year

    sub = Subject.objects.create(name_fr="Robotique", name_ar="روبوتيك")
    grp = Group.objects.create(name_fr="Groupe Robotique", name_ar="مجموعة روبوتيك", subject=sub, monthly_fee=Decimal("300.00"))
    parent = Parent.objects.create(full_name_fr="Parent Bourse", phone="212622334455")
    schedule = SessionSchedule.objects.create(group=grp, day_of_week=0, start_time="10:00", end_time="12:00")

    st = Student.objects.create(
        registration_number="GCA-TEST-EX01",
        first_name_fr="Youssef",
        last_name_fr="Chraibi",
        parent=parent,
        active=True
    )
    st.groups.add(grp)

    # Définir une exonération pour le mois en cours
    PaymentExemption.objects.create(
        student=st,
        period_month=month,
        period_year=year,
        reason="Bourse d'excellence sportive"
    )

    is_ex, reason = st.is_exempt_for_period(month, year)
    assert is_ex is True
    assert "Bourse" in reason

    # Enregistrer une présence pour déclencher la synchronisation
    Attendance.objects.create(
        student=st,
        session=schedule,
        date=today,
        status="present"
    )

    sync_invoices_with_actual_attendances()

    inv = Invoice.objects.get(student=st, period_month=month, period_year=year)
    assert inv.is_exempt is True
    assert inv.status == "exempt"
    assert inv.amount_due == Decimal("0.00")
    assert inv.get_balance() == Decimal("0.00")
    assert inv.is_overdue() is False
    assert "Bourse" in inv.exemption_reason

    # Vérifier que cette facture N'EST PAS dans les impayés
    unpaid_qs = get_billable_unpaid_invoices_qs()
    assert inv not in unpaid_qs


@pytest.mark.django_db
def test_invoice_exempt_and_unexempt_views():
    """
    Vérifie les actions de l'administration pour :
    1. Exonérer une facture impayée existante via POST /payments/invoices/<id>/exempt/.
    2. Rétablir la facture et annuler l'exonération via POST /payments/invoices/<id>/unexempt/.
    """
    client = Client()
    admin_user = User.objects.create_superuser(username="admin_test", password="AdminPassword123")
    client.force_login(admin_user)

    sub = Subject.objects.create(name_fr="Calcul Mental", name_ar="حساب ذهني")
    grp = Group.objects.create(name_fr="Groupe Soroban", name_ar="السوربان", subject=sub, monthly_fee=Decimal("200.00"))
    parent = Parent.objects.create(full_name_fr="Parent Soroban", phone="212633445566")

    st = Student.objects.create(
        registration_number="GCA-TEST-ACT01",
        first_name_fr="Nour",
        last_name_fr="Fassi",
        parent=parent,
        active=True
    )
    st.groups.add(grp)

    inv = Invoice.objects.create(
        student=st,
        group=grp,
        period_month=11,
        period_year=2026,
        amount_due=Decimal("200.00"),
        amount_paid=Decimal("0.00"),
        status="unpaid",
        due_date=date(2026, 11, 15)
    )

    # 1. Action Exonérer
    resp_exempt = client.post(f"/payments/invoices/{inv.id}/exempt/", {"reason": "Mois de bienvenue offert"})
    assert resp_exempt.status_code == 302

    inv.refresh_from_db()
    assert inv.is_exempt is True
    assert inv.status == "exempt"
    assert inv.amount_due == Decimal("0.00")
    assert inv.exemption_reason == "Mois de bienvenue offert"
    assert PaymentExemption.objects.filter(student=st, period_month=11, period_year=2026).exists()

    # 2. Action Rétablir / Annuler exonération
    resp_unexempt = client.post(f"/payments/invoices/{inv.id}/unexempt/", {})
    assert resp_unexempt.status_code == 302

    inv.refresh_from_db()
    assert inv.is_exempt is False
    assert inv.status == "unpaid"
    assert inv.amount_due == Decimal("200.00")
    assert not PaymentExemption.objects.filter(student=st, period_month=11, period_year=2026).exists()


@pytest.mark.django_db
def test_student_form_convention_and_exemptions_save():
    """
    Vérifie que le StudentForm enregistre correctement les conventions et les mois exonérés.
    """
    parent = Parent.objects.create(full_name_fr="Parent Form", phone="212644556677")
    sub = Subject.objects.create(name_fr="Robotique", name_ar="روبوتيك")
    grp = Group.objects.create(name_fr="Groupe B", name_ar="فوج ب", subject=sub, monthly_fee=Decimal("250.00"))

    form_data = {
        "registration_number": "GCA-FORM-01",
        "first_name_fr": "Ilyas",
        "last_name_fr": "Bennani",
        "first_name_ar": "إلياس",
        "last_name_ar": "بنانى",
        "parent": parent.id,
        "groups": [grp.id],
        "active": True,
        "has_convention": True,
        "convention_name": "Convention Club Partenaire",
        "discount_type": "custom_fee",
        "discount_value": "180.00",
        "exempted_months": ["9", "10"], # Septembre et Octobre
        "exemption_reason": "Bourse sportive annuelle"
    }

    form = StudentForm(data=form_data)
    assert form.is_valid(), form.errors
    student = form.save()

    assert student.has_convention is True
    assert student.convention_name == "Convention Club Partenaire"
    assert student.discount_value == Decimal("180.00")

    # Vérification des mois exonérés créés
    exemptions = student.payment_exemptions.filter(period_year=2026)
    assert exemptions.count() == 2
    assert set(exemptions.values_list("period_month", flat=True)) == {9, 10}
    assert exemptions.first().reason == "Bourse sportive annuelle"


@pytest.mark.django_db
def test_payment_create_view_with_exemption():
    """
    Vérifie qu'un enregistrement d'exonération depuis le formulaire de paiement (payment_create_view) :
    1. Crée bien l'enregistrement PaymentExemption.
    2. Marque la facture correspondante en status='exempt', is_exempt=True, amount_due=0 DH.
    """
    admin_user = User.objects.create_user(username="admin_pay", password="password", role="admin")
    client = Client()
    client.login(username="admin_pay", password="password")

    parent = Parent.objects.create(full_name_fr="Parent Ex", phone="212699887766")
    sub = Subject.objects.create(name_fr="Échecs", name_ar="الشطرنج")
    grp = Group.objects.create(name_fr="Groupe C", name_ar="فوج ج", subject=sub, monthly_fee=Decimal("300.00"))
    st = Student.objects.create(
        registration_number="GCA-PAY-EX-01",
        first_name_fr="Youssef",
        last_name_fr="Naciri",
        parent=parent,
        active=True
    )
    st.groups.add(grp)
    inv = Invoice.objects.create(
        student=st,
        group=grp,
        period_month=12,
        period_year=2026,
        original_amount=Decimal("300.00"),
        amount_due=Decimal("300.00"),
        status="unpaid",
        due_date=date(2026, 12, 15)
    )

    resp = client.post("/payments/add/", {
        "security_code": "8081",
        "student": st.id,
        "invoice": inv.id,
        "is_exemption": "on",
        "exemption_reason": "Bourse d'honneur",
        "amount": "0.00",
        "payment_date": "2026-12-05",
        "payment_method": "cash"
    })
    assert resp.status_code == 302

    inv.refresh_from_db()
    assert inv.is_exempt is True
    assert inv.status == "exempt"
    assert inv.amount_due == Decimal("0.00")
    assert inv.exemption_reason == "Bourse d'honneur"
    assert PaymentExemption.objects.filter(student=st, period_month=12, period_year=2026).exists()


@pytest.mark.django_db
def test_check_duplicate_payment_ajax_view():
    """
    Vérifie le fonctionnement de l'API AJAX de détection anti-doublon :
    - Sans élève : pas de risque
    - Élève sans paiement : pas de risque
    - Élève avec paiement complet existant : risque de doublon détecté (100% réglé, balance=0.00)
    - Élève avec versement partiel : reliquat calculé et bouton d'ajustement
    - Élève exonéré pour le mois : alerte exonération (0 DH)
    """
    admin_user = User.objects.create_user(username="admin_dup", password="password", role="admin")
    client = Client()
    client.login(username="admin_dup", password="password")

    parent = Parent.objects.create(full_name_fr="Parent Dup", phone="212688776655")
    sub = Subject.objects.create(name_fr="Échecs", name_ar="الشطرنج")
    grp = Group.objects.create(name_fr="Groupe Dup", name_ar="فوج", subject=sub, monthly_fee=Decimal("300.00"))
    st = Student.objects.create(
        registration_number="GCA-DUP-01",
        first_name_fr="Sami",
        last_name_fr="Alami",
        parent=parent,
        active=True
    )
    st.groups.add(grp)

    # 1. Sans student_id
    r1 = client.get("/payments/check-duplicate/")
    assert r1.status_code == 200
    d1 = r1.json()
    assert d1["is_duplicate_risk"] is False

    # 2. Avec élève sans aucun paiement ni exonération
    r2 = client.get(f"/payments/check-duplicate/?student={st.id}&date=2026-10-05")
    assert r2.status_code == 200
    d2 = r2.json()
    assert d2["is_duplicate_risk"] is False
    assert d2["is_exempt"] is False
    assert len(d2["existing_payments"]) == 0

    # 3. Créer une facture de 300 DH pour 10/2026 et un paiement complet de 300 DH
    inv = Invoice.objects.create(
        student=st,
        group=grp,
        period_month=10,
        period_year=2026,
        original_amount=Decimal("300.00"),
        amount_due=Decimal("300.00"),
        amount_paid=Decimal("300.00"),
        status="paid",
        due_date=date(2026, 10, 15)
    )
    pay = Payment.objects.create(
        invoice=inv,
        student=st,
        amount=Decimal("300.00"),
        payment_date=date(2026, 10, 2),
        payment_method="cash",
        receipt_number="REC-202610-001"
    )

    r3 = client.get(f"/payments/check-duplicate/?student={st.id}&invoice={inv.id}")
    assert r3.status_code == 200
    d3 = r3.json()
    assert d3["is_duplicate_risk"] is True
    assert d3["balance_remaining"] == "0.00"
    assert len(d3["existing_payments"]) == 1
    assert d3["existing_payments"][0]["receipt_number"] == "REC-202610-001"
    assert "100%" in d3["status_badge_fr"]

    # 4. Versement partiel pour un autre mois (ex: 11/2026 : montant 300 DH, payé 100 DH, reste 200 DH)
    inv2 = Invoice.objects.create(
        student=st,
        group=grp,
        period_month=11,
        period_year=2026,
        original_amount=Decimal("300.00"),
        amount_due=Decimal("300.00"),
        amount_paid=Decimal("100.00"),
        status="partial",
        due_date=date(2026, 11, 15)
    )
    pay2 = Payment.objects.create(
        invoice=inv2,
        student=st,
        amount=Decimal("100.00"),
        payment_date=date(2026, 11, 3),
        payment_method="transfer",
        receipt_number="REC-202611-002"
    )

    r4 = client.get(f"/payments/check-duplicate/?student={st.id}&invoice={inv2.id}")
    assert r4.status_code == 200
    d4 = r4.json()
    assert d4["is_duplicate_risk"] is True
    assert d4["balance_remaining"] == "200.00"
    assert "Partiel" in d4["status_badge_fr"]
    assert len(d4["existing_payments"]) == 1

    # 5. Élève exonéré pour le mois 12/2026
    PaymentExemption.objects.create(
        student=st,
        period_month=12,
        period_year=2026,
        reason="Convention Partenaire Gratuite"
    )
    r5 = client.get(f"/payments/check-duplicate/?student={st.id}&date=2026-12-10")
    assert r5.status_code == 200
    d5 = r5.json()
    assert d5["is_duplicate_risk"] is True
    assert d5["is_exempt"] is True
    assert "Exonéré" in d5["status_badge_fr"]
    assert "Convention Partenaire Gratuite" in d5["warning_msg_fr"]


@pytest.mark.django_db
def test_deferred_payment_and_accounting_regularization():
    """
    Vérifie la précision du mois concerné pour les paiements tardifs :
    1. Élève avec une facture impayée pour Septembre (09/2026).
    2. Règlement tardif encaissé en Octobre (15/10/2026) avec period_month=9, period_year=2026.
    3. Vérifie que payment.is_deferred est True, le libellé de période est 'Septembre 2026'.
    4. Vérifie que la facture de Septembre est automatiquement soldée.
    5. Vérifie que l'API anti-doublon AJAX réagit selon le mois sélectionné (period_month=9 -> doublon détecté, period_month=10 -> pas de doublon).
    6. Vérifie la génération du reçu PDF et de l'export Excel avec la période concernée.
    """
    from finance.receipt_pdf import generate_receipt_pdf
    from portal.excel_export import export_paid_payments_to_excel

    sub = Subject.objects.create(name_fr="Calcul Mental", name_ar="الحساب الذهني")
    grp = Group.objects.create(name_fr="Groupe Soroban", name_ar="السوروبان", subject=sub, monthly_fee=Decimal("250.00"))
    parent = Parent.objects.create(full_name_fr="Parent Test Late", phone="212622334455")
    st = Student.objects.create(
        registration_number="GCA-2026-999",
        first_name_fr="Yassine",
        last_name_fr="Chraibi",
        first_name_ar="ياسين",
        last_name_ar="الشرايبي",
        parent=parent,
        active=True
    )
    st.groups.add(grp)

    # 1. Facture pour Septembre 2026
    inv_sept = Invoice.objects.create(
        student=st,
        group=grp,
        period_month=9,
        period_year=2026,
        original_amount=Decimal("250.00"),
        amount_due=Decimal("250.00"),
        amount_paid=Decimal("0.00"),
        status="unpaid",
        due_date=date(2026, 9, 15)
    )

    # 2. Facture pour Octobre 2026
    inv_oct = Invoice.objects.create(
        student=st,
        group=grp,
        period_month=10,
        period_year=2026,
        original_amount=Decimal("250.00"),
        amount_due=Decimal("250.00"),
        amount_paid=Decimal("0.00"),
        status="unpaid",
        due_date=date(2026, 10, 15)
    )

    # 3. Paiement effectué le 15/10/2026 pour régler SEPTEMBRE en retard
    pay = Payment.objects.create(
        student=st,
        amount=Decimal("250.00"),
        payment_date=date(2026, 10, 15),
        period_month=9,
        period_year=2026,
        payment_method="cash",
        receipt_number="REC-2026-LATE01"
    )

    # Vérifications modèle
    assert pay.is_deferred is True
    assert "Septembre 2026" in pay.period_label_fr
    assert "شتنبر 2026" in pay.period_label_ar
    assert pay.invoice == inv_sept

    inv_sept.refresh_from_db()
    assert inv_sept.status == "paid"
    assert inv_sept.amount_paid == Decimal("250.00")

    inv_oct.refresh_from_db()
    assert inv_oct.status == "unpaid"

    # 4. Vérification Anti-doublon AJAX avec period_month
    client = Client()
    admin_user = User.objects.create_superuser(username="admin_test_late", email="adminlate@gca.ma", password="pass")
    client.force_login(admin_user)

    # Vérifier Septembre (qui vient d'être payé tardivement) -> DOIT signaler risque de doublon
    r_sept = client.get(f"/payments/check-duplicate/?student={st.id}&period_month=9&period_year=2026")
    assert r_sept.status_code == 200
    d_sept = r_sept.json()
    assert d_sept["is_duplicate_risk"] is True
    assert "Réglé" in d_sept["status_badge_fr"] or "Payé" in d_sept["status_badge_fr"]

    # Vérifier Octobre -> NE DOIT PAS signaler de risque
    r_oct = client.get(f"/payments/check-duplicate/?student={st.id}&period_month=10&period_year=2026")
    assert r_oct.status_code == 200
    d_oct = r_oct.json()
    assert d_oct["is_duplicate_risk"] is False

    # 5. Vérifier la génération du reçu PDF officiel
    pdf_bytes = generate_receipt_pdf(pay, lang="fr")
    assert len(pdf_bytes) > 1000

    pdf_bytes_ar = generate_receipt_pdf(pay, lang="ar")
    assert len(pdf_bytes_ar) > 1000

    pdf_bytes_bi = generate_receipt_pdf(pay, lang="bilingual")
    assert len(pdf_bytes_bi) > 1000

    # 6. Vérifier l'export Excel consolidé avec la nouvelle colonne
    excel_bytes = export_paid_payments_to_excel(Payment.objects.filter(id=pay.id), Invoice.objects.filter(id=inv_oct.id), lang="fr")
    assert len(excel_bytes) > 2000


@pytest.mark.django_db
def test_payment_student_search_and_default_entry_date():
    """
    Vérifie les deux fonctionnalités demandées :
    1. Présence de la recherche de noms d'élèves dans le formulaire de paiement.
    2. Affectation automatique de la date de saisie (date du jour) comme date de paiement par défaut si non renseignée.
    """
    from portal.forms import PaymentForm

    sub = Subject.objects.create(name_fr="Robotique", name_ar="الروبوتيك")
    grp = Group.objects.create(name_fr="Groupe Robotique", name_ar="مجموعة الروبوتيك", subject=sub, monthly_fee=Decimal("300.00"))
    parent = Parent.objects.create(full_name_fr="Parent Test Search", phone="212633445566")
    st = Student.objects.create(
        registration_number="GCA-2026-SEARCH",
        first_name_fr="Nabil",
        last_name_fr="Bennani",
        first_name_ar="نبيل",
        last_name_ar="بنان",
        parent=parent,
        active=True
    )
    st.groups.add(grp)

    client = Client()
    admin_user = User.objects.create_superuser(username="admin_search_test", email="adminsearch@gca.ma", password="pass")
    client.force_login(admin_user)

    # 1. Vérifier la page GET : champs de recherche de nom et suggestions présents
    res_get = client.get("/payments/add/")
    assert res_get.status_code == 200
    content = res_get.content.decode("utf-8")
    assert "student_search_input" in content
    assert "student_search_dropdown" in content
    assert "student_selected_card" in content

    from django.utils import timezone
    today_date = timezone.localdate()

    # 2. Vérifier PaymentForm avec payment_date vide
    form = PaymentForm(data={
        'security_code': '8081',
        'student': st.id,
        'period_month': 10,
        'period_year': 2026,
        'amount': '300.00',
        'payment_date': '',  # Non renseigné par l'utilisateur
        'payment_method': 'cash',
        'reference': '',
        'notes': 'Test sans date',
    })
    assert form.is_valid(), f"Form errors: {form.errors}"
    assert form.cleaned_data['payment_date'] == today_date

    # 3. Vérifier soumission POST via la vue payment_create_view
    post_data = {
        'security_code': '8081',
        'student': st.id,
        'period_month': 10,
        'period_year': 2026,
        'amount': '300.00',
        'payment_date': '',  # Vide -> doit prendre today_date
        'payment_method': 'cash',
        'reference': 'REF-NO-DATE',
        'notes': 'Paiement sans date explicite',
    }
    res_post = client.post("/payments/add/", data=post_data)
    assert res_post.status_code == 302  # Redirection vers la liste des paiements

    created_pay = Payment.objects.filter(student=st, reference='REF-NO-DATE').first()
    assert created_pay is not None
    assert created_pay.payment_date == today_date

    # 4. Vérifier au niveau du modèle Payment.save() sans date
    pay_model = Payment.objects.create(
        student=st,
        amount=Decimal("300.00"),
        receipt_number="REC-2026-MODEL-NODATE",
        period_month=11,
        period_year=2026,
    )
    assert pay_model.payment_date == today_date


@pytest.mark.django_db
def test_financial_session_single_code_execution_8081_and_excel_month_column():
    """
    Vérifie les deux exigences utilisateur :
    1. Le code de sécurité financier est 8081 et ne doit être exécuté/saisi qu'une seule fois par session.
       Une fois saisi, les opérations ultérieures de la session n'exigent plus le code.
       Le verrouillage manuel /payments/lock-session/ réactive la protection.
    2. L'export Excel des paiements (payants + impayés) et l'export direct des impayés
       comportent bien la colonne du mois concerné.
    """
    client = Client()
    admin_user = User.objects.create_superuser(username="admin_session_test_8081", email="admin8081@gca.ma", password="pass")
    admin_user.preferred_language = 'fr'
    admin_user.save()
    client.force_login(admin_user)

    st = Student.objects.first()

    # 1. Tentative avec l'ancien code 6565 ou mauvais code -> Rejeté
    res_bad = client.post("/payments/add/", {
        'security_code': '6565',
        'student': st.id,
        'amount': '300.00',
        'period_month': 10,
        'period_year': 2026,
        'payment_method': 'cash',
        'reference': 'REF-BAD-01'
    })
    assert res_bad.status_code == 200
    assert "autorisation incorrect" in res_bad.content.decode("utf-8")
    assert not Payment.objects.filter(reference='REF-BAD-01').exists()

    # 2. Saisie du NOUVEAU code 8081 -> Succès et déverrouillage de la session
    res_good = client.post("/payments/add/", {
        'security_code': '8081',
        'student': st.id,
        'amount': '300.00',
        'period_month': 10,
        'period_year': 2026,
        'payment_method': 'cash',
        'reference': 'REF-OK-SESSION-01'
    })
    assert res_good.status_code == 302
    pay1 = Payment.objects.filter(reference='REF-OK-SESSION-01').first()
    assert pay1 is not None
    assert client.session.get('financial_session_unlocked') is True

    # 3. Deuxième opération durant la même session SANS entrer de code -> Doit réussir directement !
    res_session = client.post("/payments/add/", {
        'security_code': '',  # Champ vide
        'student': st.id,
        'amount': '300.00',
        'period_month': 11,
        'period_year': 2026,
        'payment_method': 'cash',
        'reference': 'REF-OK-SESSION-02'
    })
    assert res_session.status_code == 302
    assert Payment.objects.filter(reference='REF-OK-SESSION-02').exists()

    # 4. Modification dans la même session sans code -> Réussit également
    res_edit = client.post(f"/payments/{pay1.id}/edit/", {
        'security_code': '',  # Champ vide
        'student': st.id,
        'amount': '350.00',
        'payment_date': str(pay1.payment_date),
        'payment_method': 'cash',
        'reference': 'REF-OK-SESSION-01-EDITED'
    })
    assert res_edit.status_code == 302
    pay1.refresh_from_db()
    assert pay1.amount == Decimal('350.00')

    # 5. Verrouillage manuel de la session
    res_lock = client.get("/payments/lock-session/")
    assert res_lock.status_code == 302
    assert client.session.get('financial_session_unlocked') is False

    # 6. Après verrouillage, une opération sans code doit être à nouveau rejetée
    res_locked = client.post("/payments/add/", {
        'security_code': '',
        'student': st.id,
        'amount': '300.00',
        'period_month': 12,
        'period_year': 2026,
        'payment_method': 'cash',
        'reference': 'REF-LOCKED-03'
    })
    assert res_locked.status_code == 200
    assert "autorisation incorrect" in res_locked.content.decode("utf-8")
    assert not Payment.objects.filter(reference='REF-LOCKED-03').exists()

    # 7. Vérification des colonnes du mois concerné dans les exports Excel
    from portal.excel_export import export_paid_payments_to_excel, export_unpaid_invoices_to_excel
    import openpyxl
    import io

    # Export des paiements (payants + impayés)
    paid_xlsx_bytes = export_paid_payments_to_excel(Payment.objects.all(), Invoice.objects.all(), lang="fr")
    wb_paid = openpyxl.load_workbook(io.BytesIO(paid_xlsx_bytes))
    ws_paid = wb_paid.active
    header_cells_paid = [ws_paid.cell(row=3, column=c).value for c in range(1, 13)]
    assert "Mois Concerné (Période)" in header_cells_paid

    # Export direct des impayés
    unpaid_xlsx_bytes = export_unpaid_invoices_to_excel(Invoice.objects.all(), lang="fr")
    wb_unpaid = openpyxl.load_workbook(io.BytesIO(unpaid_xlsx_bytes))
    ws_unpaid = wb_unpaid.active
    header_cells_unpaid = [ws_unpaid.cell(row=3, column=c).value for c in range(1, 13)]
    assert "Mois Concerné (Période)" in header_cells_unpaid





