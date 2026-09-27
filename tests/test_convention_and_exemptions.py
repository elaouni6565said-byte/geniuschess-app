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
        "security_code": "6565",
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

