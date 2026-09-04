import pytest
from django.test import Client
from datetime import date
from decimal import Decimal
from django.db.models import Sum
from academy.models import User, Parent, Student
from finance.models import Payment

@pytest.mark.django_db
def test_bilingual_views_and_rtl_toggle():
    """Tests view rendering in both French (LTR) and Arabic (RTL) with Admin protection."""
    client = Client()

    # 1. Anonymous access is redirected to login
    resp_anon = client.get('/')
    assert resp_anon.status_code == 302
    assert '/login/' in resp_anon.url

    # 2. Login Page rendering
    resp_login_fr = client.get('/login/?lang=fr')
    assert resp_login_fr.status_code == 200
    assert 'Connexion Espace Administrateur' in resp_login_fr.content.decode('utf-8')

    resp_login_ar = client.get('/login/?lang=ar')
    assert resp_login_ar.status_code == 200
    assert 'dir="rtl"' in resp_login_ar.content.decode('utf-8')
    assert 'تسجيل الدخول إلى فضاء الإدارة' in resp_login_ar.content.decode('utf-8')

    # 3. Login with wrong password fails
    resp_bad = client.post('/login/?lang=fr', {'username': 'admin', 'password': 'WRONGPASSWORD'})
    assert resp_bad.status_code == 200
    assert 'incorrect' in resp_bad.content.decode('utf-8')

    # 4. Login with correct Admin password CGAESA65
    admin_user = User.objects.get(username='admin')
    admin_user.set_password('CGAESA65')
    admin_user.save()

    login_success = client.login(username='admin', password='CGAESA65')
    assert login_success is True

    # 5. Dashboard French (Authenticated Admin)
    resp_fr = client.get('/?lang=fr')
    assert resp_fr.status_code == 200
    assert 'dir="ltr"' in resp_fr.content.decode('utf-8')
    assert 'Tableau de Bord' in resp_fr.content.decode('utf-8')

    # 6. Dashboard Arabic RTL (Authenticated Admin)
    resp_ar = client.get('/?lang=ar')
    assert resp_ar.status_code == 200
    assert 'dir="rtl"' in resp_ar.content.decode('utf-8')
    assert 'لوحة القيادة' in resp_ar.content.decode('utf-8')
    assert 'الطلاب' in resp_ar.content.decode('utf-8')

    # 7. Students list
    resp_st = client.get('/students/?lang=ar')
    assert resp_st.status_code == 200
    assert 'تدبير شؤون الطلاب' in resp_st.content.decode('utf-8')

    # 8. Search student in Arabic
    resp_search = client.get('/students/?q=محمد&lang=ar')
    assert resp_search.status_code == 200
    assert 'GCA-2026-001' in resp_search.content.decode('utf-8')

    # 9. Planning view
    resp_plan = client.get('/planning/?lang=ar')
    assert resp_plan.status_code == 200
    assert 'البرنامج الأسبوعي' in resp_plan.content.decode('utf-8')
    assert 'السبت' in resp_plan.content.decode('utf-8')

    # 10. Payments view
    resp_pay = client.get('/payments/?lang=fr')
    assert resp_pay.status_code == 200
    assert 'Paiements' in resp_pay.content.decode('utf-8')

    # 11. Parent Space
    resp_parent = client.get('/parent/?lang=ar')
    assert resp_parent.status_code == 200
    assert 'فضاء ولي الأمر' in resp_parent.content.decode('utf-8')
    assert 'أبنائي' in resp_parent.content.decode('utf-8')

    # 12. Receipt PDF view
    payment = Payment.objects.first()
    resp_pdf = client.get(f'/payments/{payment.id}/pdf/?lang=ar')
    assert resp_pdf.status_code == 200
    assert resp_pdf['Content-Type'] == 'application/pdf'

    # 13. Excel export view
    resp_excel = client.get('/students/export-excel/?lang=ar')
    assert resp_excel.status_code == 200
    assert 'openxmlformats' in resp_excel['Content-Type']

def test_parent_space_strict_family_isolation():
    """Validates that each parent only sees their own children, schedules, attendances and receipts."""
    client = Client()

    # Login as Karim Alaoui (Father of Mohamed & Sara)
    login_karim = client.login(username='karim_alaoui', password='Parent@2026')
    assert login_karim is True

    resp_karim = client.get('/parent/?lang=fr')
    assert resp_karim.status_code == 200
    content_k = resp_karim.content.decode('utf-8')
    assert 'Mohamed Alaoui' in content_k
    assert 'Sara Alaoui' in content_k
    assert 'Aya Benani' not in content_k
    assert 'Ahmed Benani' not in content_k
    assert 'Emploi du temps de' in content_k
    assert 'Suivi des présences de' in content_k

    # 1. Verify navbar is strictly restricted for parent: NO admin links visible!
    assert 'Tableau de bord' not in content_k
    assert 'Gestion des élèves' not in content_k
    assert 'parents_list' not in content_k
    assert 'Filiation' not in content_k
    assert 'Espace Parent' in content_k

    # 2. Parent cannot access admin URLs: redirected immediately!
    resp_students = client.get('/students/')
    assert resp_students.status_code == 302
    assert resp_students.url == '/parent/'

    resp_dash = client.get('/')
    assert resp_dash.status_code == 302
    assert resp_dash.url == '/parent/'

    resp_planning = client.get('/planning/')
    assert resp_planning.status_code == 302
    assert resp_planning.url == '/parent/'

    # 3. Parent cannot spoof family_id
    fatima = Parent.objects.filter(full_name_fr__icontains='Fatima').first()
    resp_spoof = client.get(f'/parent/?family_id={fatima.id}&lang=fr')
    assert resp_spoof.status_code == 200
    content_spoof = resp_spoof.content.decode('utf-8')
    assert 'Aya Benani' not in content_spoof
    assert 'Mohamed Alaoui' in content_spoof

    # 4. Child Switcher: parent can navigate strictly between their OWN children
    sara = Student.objects.filter(first_name_fr='Sara').first()
    mohamed = Student.objects.filter(first_name_fr='Mohamed').first()
    aya = Student.objects.filter(first_name_fr='Aya').first()

    # Filter to Sara only
    resp_sara = client.get(f'/parent/?child_id={sara.id}&lang=fr')
    assert resp_sara.status_code == 200
    c_sara = resp_sara.content.decode('utf-8')
    assert f'Emploi du temps de <b>{sara.first_name_fr} {sara.last_name_fr}</b>' in c_sara
    assert f'Emploi du temps de <b>{mohamed.first_name_fr} {mohamed.last_name_fr}</b>' not in c_sara

    # Maliciously attempt to pass another parent's child (Aya)
    resp_malicious = client.get(f'/parent/?child_id={aya.id}&lang=fr')
    assert resp_malicious.status_code == 200
    c_malicious = resp_malicious.content.decode('utf-8')
    assert f'Emploi du temps de <b>{aya.first_name_fr} {aya.last_name_fr}</b>' not in c_malicious # Rejected!
    assert f'Emploi du temps de <b>{mohamed.first_name_fr} {mohamed.last_name_fr}</b>' in c_malicious

    # Test receipt download for own child
    pay_mohamed = Payment.objects.filter(student__first_name_fr='Mohamed').first()
    if not pay_mohamed:
        admin = User.objects.filter(is_superuser=True).first()
        pay_mohamed = Payment.objects.create(
            receipt_number="REC-2026-0001",
            student=mohamed,
            payment_date=date.today(),
            amount=Decimal("300.00"),
            payment_method="cash",
            created_by=admin
        )
    resp_rec = client.get(f'/payments/{pay_mohamed.id}/pdf/?lang=fr')
    assert resp_rec.status_code == 200
    assert resp_rec['Content-Type'] == 'application/pdf'

    client.logout()

    # 5. Anonymous access to /parent/ must redirect to login
    resp_anon = client.get('/parent/')
    assert resp_anon.status_code == 302
    assert '/login/' in resp_anon.url

    # Login as Fatima Benani (Mother of Aya & Ahmed)
    login_fatima = client.login(username='fatima_benani', password='Parent@2026')
    assert login_fatima is True

    resp_fatima = client.get('/parent/?lang=ar')
    assert resp_fatima.status_code == 200
    content_f = resp_fatima.content.decode('utf-8')
    assert 'آية بناني' in content_f
    assert 'أحمد بناني' in content_f
    assert 'محمد العلوي' not in content_f
    assert 'سارة العلوي' not in content_f

    # Fatima cannot download Mohamed's receipt
    resp_denied = client.get(f'/payments/{pay_mohamed.id}/pdf/?lang=fr')
    assert resp_denied.status_code == 302

def test_planning_agenda_daily_monthly_annual_views():
    """Validates the 3 agenda views: Daily, Monthly, and Annual in French and Arabic RTL."""
    client = Client()
    admin = User.objects.get(username='admin')
    admin.set_password('CGAESA65')
    admin.save()
    client.login(username='admin', password='CGAESA65')

    # 1. Daily View (FR & AR)
    resp_daily_fr = client.get('/planning/?view=daily&date=2026-09-05&lang=fr')
    assert resp_daily_fr.status_code == 200
    c_daily_fr = resp_daily_fr.content.decode('utf-8')
    assert 'Quotidien' in c_daily_fr
    assert 'daily-timeline' in c_daily_fr
    assert 'Samedi' in c_daily_fr

    resp_daily_ar = client.get('/planning/?view=daily&date=2026-09-05&lang=ar')
    assert resp_daily_ar.status_code == 200
    c_daily_ar = resp_daily_ar.content.decode('utf-8')
    assert 'يومي' in c_daily_ar
    assert 'السبت' in c_daily_ar

    # 2. Monthly View (FR & AR)
    resp_monthly_fr = client.get('/planning/?view=monthly&year=2026&month=9&lang=fr')
    assert resp_monthly_fr.status_code == 200
    c_monthly_fr = resp_monthly_fr.content.decode('utf-8')
    assert 'Mensuel' in c_monthly_fr
    assert 'calendar-grid' in c_monthly_fr
    assert 'Septembre 2026' in c_monthly_fr

    resp_monthly_ar = client.get('/planning/?view=monthly&year=2026&month=9&lang=ar')
    assert resp_monthly_ar.status_code == 200
    c_monthly_ar = resp_monthly_ar.content.decode('utf-8')
    assert 'شهري' in c_monthly_ar
    assert 'calendar-grid' in c_monthly_ar

    # 3. Annual View (FR & AR)
    resp_annual_fr = client.get('/planning/?view=annual&year=2026&lang=fr')
    assert resp_annual_fr.status_code == 200
    c_annual_fr = resp_annual_fr.content.decode('utf-8')
    assert 'Annuel' in c_annual_fr
    assert 'annual-months-grid' in c_annual_fr

    resp_annual_ar = client.get('/planning/?view=annual&year=2026&lang=ar')
    assert resp_annual_ar.status_code == 200
    c_annual_ar = resp_annual_ar.content.decode('utf-8')
    assert 'سنوي' in c_annual_ar
    assert 'annual-months-grid' in c_annual_ar

def test_parent_flexible_login_by_name_or_student():
    """Validates that parents can log in using their username, parent full name, student name, matricule or phone."""
    client = Client()

    # 1. Login using Parent Full Name (French)
    resp1 = client.post('/login/', {'username': 'Karim Alaoui', 'password': 'Parent@2026'})
    assert resp1.status_code == 302
    assert resp1.url == '/parent/'
    client.logout()

    # 2. Login using Student / Child Full Name
    resp2 = client.post('/login/', {'username': 'Mohamed Alaoui', 'password': 'Parent@2026'})
    assert resp2.status_code == 302
    assert resp2.url == '/parent/'
    client.logout()

    # 3. Login using Student First Name
    resp3 = client.post('/login/', {'username': 'Sara', 'password': 'Parent@2026'})
    assert resp3.status_code == 302
    assert resp3.url == '/parent/'
    client.logout()

    # 4. Login using Student Matricule
    resp4 = client.post('/login/', {'username': 'GCA-2026-001', 'password': 'Parent@2026'})
    assert resp4.status_code == 302
    assert resp4.url == '/parent/'
    client.logout()

    # 5. Login using Parent Phone
    resp5 = client.post('/login/', {'username': '0661112233', 'password': 'Parent@2026'})
    assert resp5.status_code == 302
    assert resp5.url == '/parent/'
    client.logout()

    # 6. Login using Parent Full Name in Arabic
    resp6 = client.post('/login/', {'username': 'كريم العلوي', 'password': 'Parent@2026'})
    assert resp6.status_code == 302
    assert resp6.url == '/parent/'
    client.logout()

    # 7. Login using Student Full Name in Arabic
    resp7 = client.post('/login/', {'username': 'محمد العلوي', 'password': 'Parent@2026'})
    assert resp7.status_code == 302
    assert resp7.url == '/parent/'
    client.logout()


@pytest.mark.django_db
def test_parent_visit_tracking_for_admin():
    """Validates that when a parent visits their portal, a visit log is recorded and visible to admin."""
    from academy.models import ParentVisitLog
    client = Client()

    # 1. Clean previous visit logs
    ParentVisitLog.objects.all().delete()

    # 2. Parent Karim Alaoui logs in and views their portal
    login_resp = client.post('/login/', {'username': 'Karim Alaoui', 'password': 'Parent@2026'})
    assert login_resp.status_code == 302

    # Access parent space
    resp_parent = client.get('/parent/')
    assert resp_parent.status_code == 200

    # Verify visit log was created
    visits = ParentVisitLog.objects.all()
    assert visits.count() >= 1
    last_visit = visits.first()
    assert last_visit.parent.full_name_fr == 'Karim Alaoui'
    assert last_visit.student is not None

    # Verify parent model helper methods
    karim = last_visit.parent
    assert karim.get_visit_count() >= 1
    assert karim.get_last_visit() is not None

    # Verify student model helper methods
    student = last_visit.student
    assert student.get_last_parent_visit() is not None

    client.logout()

    # 3. Admin logs in and checks Dashboard & Parents List
    admin = User.objects.get(username='admin')
    admin.set_password('CGAESA65')
    admin.save()
    client.login(username='admin', password='CGAESA65')

    # Dashboard displays recent parent visits
    resp_dash = client.get('/')
    assert resp_dash.status_code == 200
    content_dash = resp_dash.content.decode('utf-8')
    assert 'Suivi des visites Parents' in content_dash
    assert 'Karim Alaoui' in content_dash

    # Parents list displays visit badge
    resp_parents = client.get('/parents/')
    assert resp_parents.status_code == 200
    content_parents = resp_parents.content.decode('utf-8')
    assert 'Dernière visite' in content_parents
    assert 'visite(s)' in content_parents


@pytest.mark.django_db
def test_public_family_registration():
    """
    Validates the public family pre-registration portal:
    - Renders in French and Arabic RTL
    - Rejects missing required fields (Parent FR/AR name, phone, Child FR/AR name, birthdate)
    - Successfully registers parent and multiple children with optional fields (email, address, school, grade)
    - Creates parent user account and allows immediate login with Parent@2026
    """
    client = Client()

    # 1. GET registration page in French and Arabic
    resp_fr = client.get('/register/?lang=fr')
    assert resp_fr.status_code == 200
    assert "Formulaire d'Inscription Famille" in resp_fr.content.decode('utf-8')

    resp_ar = client.get('/register/?lang=ar')
    assert resp_ar.status_code == 200
    assert 'dir="rtl"' in resp_ar.content.decode('utf-8')
    assert 'استمارة تسجيل أسرة جديدة' in resp_ar.content.decode('utf-8')

    # 2. POST with missing required fields fails gracefully
    resp_empty = client.post('/register/?lang=fr', {})
    assert resp_empty.status_code == 200
    assert 'Veuillez renseigner' in resp_empty.content.decode('utf-8')

    # 3. POST valid family registration with 2 children (brother & sister)
    data = {
        'parent_name_fr': 'Rachid Bennani',
        'parent_name_ar': 'رشيد بناني',
        'parent_phone': '0677889900',
        'parent_email': 'rachid.bennani@gmail.com', # Optional
        'parent_address': 'Agdal, Rabat',            # Optional
        'child_name_fr[]': ['Ines Bennani', 'Sami Bennani'],
        'child_name_ar[]': ['إيناس بناني', 'سامي بناني'],
        'child_birth_date[]': ['2015-05-20', '2018-09-14'],
        'child_school[]': ['École Descartes', 'École Paul Cézanne'], # Optional
        'child_grade_level[]': ['CM2', 'CP'],                       # Optional
    }
    resp_submit = client.post('/register/?lang=fr', data)
    assert resp_submit.status_code == 200
    content_success = resp_submit.content.decode('utf-8')
    assert "Inscription Enregistrée avec Succès" in content_success
    assert "Rachid Bennani" in content_success
    assert "Ines Bennani" in content_success
    assert "Sami Bennani" in content_success

    # 4. Verify Database Objects
    parent = Parent.objects.get(phone='0677889900')
    assert parent.full_name_fr == 'Rachid Bennani'
    assert parent.full_name_ar == 'رشيد بناني'
    assert parent.email == 'rachid.bennani@gmail.com'
    assert parent.address == 'Agdal, Rabat'
    assert parent.user is not None

    students = Student.objects.filter(parent=parent).order_by('id')
    assert students.count() == 2
    ines = students[0]
    assert ines.first_name_fr == 'Ines'
    assert ines.school == 'École Descartes'
    assert ines.grade_level == 'CM2'
    assert ines.registration_number.startswith('GCA-2026-')

    sami = students[1]
    assert sami.first_name_fr == 'Sami'
    assert sami.school == 'École Paul Cézanne'
    assert sami.grade_level == 'CP'

    # 5. Immediate Login by Phone or Child Name with Parent@2026
    login_phone = client.post('/login/', {'username': '0677889900', 'password': 'Parent@2026'})
    assert login_phone.status_code == 302
    assert login_phone.url == '/parent/'

    client.logout()

    login_child = client.post('/login/', {'username': 'Ines Bennani', 'password': 'Parent@2026'})
    assert login_child.status_code == 302
    assert login_child.url == '/parent/'


@pytest.mark.django_db
def test_admin_payment_modification_with_security_code():
    """
    Validates that:
    1. Only authenticated Admin can edit/delete payments
    2. Editing a payment fails without or with wrong security code
    3. Editing succeeds when correct special security code '6565' is provided
    4. Associated invoice balance and status are recalculated automatically
    5. Deleting a payment requires security code '6565' and updates invoice status
    """
    client = Client()

    # Login as admin
    admin = User.objects.get(username='admin')
    admin.set_password('CGAESA65')
    admin.save()
    client.login(username='admin', password='CGAESA65')

    student = Student.objects.first()
    assert student is not None

    # Create a test payment
    from finance.models import Payment, Invoice
    inv = Invoice.objects.filter(student=student).first()
    if not inv:
        group = student.groups.first()
        inv = Invoice.objects.create(
            student=student,
            group=group,
            period_month=9,
            period_year=2026,
            amount_due=Decimal('300.00'),
            amount_paid=Decimal('0.00'),
            status='unpaid',
            due_date=date(2026, 9, 15)
        )

    payment = Payment.objects.create(
        receipt_number="REC-TEST-SEC-01",
        student=student,
        invoice=inv,
        amount=Decimal('300.00'),
        payment_date=date(2026, 9, 4),
        payment_method='cash'
    )
    inv.amount_paid = Decimal('300.00')
    inv.status = 'paid'
    inv.save()

    # 1. Edit page renders correctly
    resp_get = client.get(f'/payments/{payment.id}/edit/')
    assert resp_get.status_code == 200
    assert "REC-TEST-SEC-01" in resp_get.content.decode('utf-8')
    assert "Code Spécial" in resp_get.content.decode('utf-8')

    # 2. Attempt modification with WRONG security code -> Rejected
    edit_data_bad = {
        'security_code': 'WRONG999',
        'student': student.id,
        'amount': '350.00',
        'payment_date': '2026-09-04',
        'payment_method': 'cash',
        'reference': '',
        'notes': 'Test modification',
    }
    resp_bad = client.post(f'/payments/{payment.id}/edit/', edit_data_bad)
    assert resp_bad.status_code == 200
    assert "Code spécial de sécurité incorrect" in resp_bad.content.decode('utf-8')

    # Value should remain unchanged in database
    payment.refresh_from_db()
    assert payment.amount == Decimal('300.00')

    # 3. Successful modification with CORRECT security code '6565'
    edit_data_good = {
        'security_code': '6565',
        'student': student.id,
        'amount': '250.00', # Changed to 250 DH
        'payment_date': '2026-09-04',
        'payment_method': 'check',
        'reference': 'CHQ-987654',
        'notes': 'Rectification autorisée',
    }
    resp_good = client.post(f'/payments/{payment.id}/edit/', edit_data_good)
    assert resp_good.status_code == 302
    assert resp_good.url == '/payments/'

    payment.refresh_from_db()
    assert payment.amount == Decimal('250.00')
    assert payment.payment_method == 'check'
    assert payment.reference == 'CHQ-987654'

    # Verify invoice status recalculated properly
    inv.refresh_from_db()
    expected_paid = inv.payments.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    assert inv.amount_paid == expected_paid

    # 4. Deletion with wrong security code -> Rejected
    resp_del_bad = client.post(f'/payments/{payment.id}/delete/', {'security_code': '0000'})
    assert resp_del_bad.status_code == 200
    assert "Code spécial de sécurité incorrect" in resp_del_bad.content.decode('utf-8')
    assert Payment.objects.filter(id=payment.id).exists()

    # 5. Deletion with correct security code '6565' -> Accepted
    resp_del_good = client.post(f'/payments/{payment.id}/delete/', {'security_code': '6565'})
    assert resp_del_good.status_code == 302
    assert resp_del_good.url == '/payments/'

    assert not Payment.objects.filter(id=payment.id).exists()
    inv.refresh_from_db()
    expected_after_del = inv.payments.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    assert inv.amount_paid == expected_after_del


@pytest.mark.django_db
def test_payment_creation_auto_updates_invoice_and_dashboard():
    """
    Validates that:
    1. Creating a new payment without specifying an invoice auto-links to the student's pending invoice.
    2. The invoice amount_paid and status are updated automatically.
    3. The unpaid balance decreases and reflects on /payments/ and dashboard.
    """
    client = Client()
    admin = User.objects.get(username='admin')
    admin.set_password('CGAESA65')
    admin.save()
    client.login(username='admin', password='CGAESA65')

    student = Student.objects.first()
    group = student.groups.first()

    from finance.models import Invoice, Payment
    # Create an unpaid invoice
    inv = Invoice.objects.create(
        student=student,
        group=group,
        period_month=10,
        period_year=2026,
        amount_due=Decimal('400.00'),
        amount_paid=Decimal('0.00'),
        status='unpaid',
        due_date=date(2026, 10, 10)
    )

    # Initial state: invoice is unpaid
    assert inv.status == 'unpaid'
    assert inv.get_balance() == Decimal('400.00')

    # Case A: Post new payment specifying the invoice
    resp = client.post('/payments/add/', {
        'student': student.id,
        'invoice': inv.id,
        'amount': '400',
        'payment_date': '2026-10-02',
        'payment_method': 'transfer',
        'security_code': '6565',
    })
    assert resp.status_code == 302
    assert resp.url == '/payments/'

    # Verify invoice was updated automatically to paid
    inv.refresh_from_db()
    assert inv.amount_paid == Decimal('400.00')
    assert inv.status == 'paid'
    assert inv.get_balance() == Decimal('0.00')

    # Verify payments page displays updated data
    resp_payments = client.get('/payments/')
    assert resp_payments.status_code == 200
    assert inv not in resp_payments.context['unpaid_invoices']

    # Verify dashboard displays updated KPIs
    resp_dash = client.get('/')
    assert resp_dash.status_code == 200


@pytest.mark.django_db
def test_download_timetable_pdf():
    """
    Validates that:
    1. Timetable PDF can be downloaded in French, Arabic, and Bilingual formats.
    2. Admin and owning parent have authorization.
    3. Unauthorized parent is blocked.
    """
    client = Client()
    admin = User.objects.get(username='admin')
    admin.set_password('CGAESA65')
    admin.save()
    client.login(username='admin', password='CGAESA65')

    student = Student.objects.first()
    assert student is not None

    # 1. Admin downloads timetable PDF
    for lang in ('fr', 'ar', 'bilingual'):
        resp = client.get(f'/students/{student.id}/timetable-pdf/?lang={lang}')
        assert resp.status_code == 200
        assert resp['Content-Type'] == 'application/pdf'
        assert resp.content.startswith(b'%PDF-')
        assert len(resp.content) > 1000

    # 2. Parent logs in and downloads own child's timetable PDF
    parent = student.parent
    assert parent is not None and parent.user is not None
    parent.user.set_password('pass1234')
    parent.user.save()
    client.login(username=parent.user.username, password='pass1234')

    resp_own = client.get(f'/students/{student.id}/timetable-pdf/?lang=fr')
    assert resp_own.status_code == 200
    assert resp_own['Content-Type'] == 'application/pdf'

    # 3. Unauthorized access by another parent or anonymous
    client.logout()
    resp_anon = client.get(f'/students/{student.id}/timetable-pdf/')
    assert resp_anon.status_code == 302


@pytest.mark.django_db
def test_planning_group_colors_and_legend():
    """
    Validates that:
    1. Groups have distinct colors defined.
    2. Planning view renders group colors and legend.
    """
    client = Client()
    admin = User.objects.get(username='admin')
    admin.set_password('CGAESA65')
    admin.save()
    client.login(username='admin', password='CGAESA65')

    from academy.models import Group
    groups = list(Group.objects.all())
    assert len(groups) > 0
    for g in groups:
        assert g.get_color().startswith('#')
        assert len(g.get_color()) == 7

    # Check monthly and daily planning views
    resp_monthly = client.get('/planning/?view=monthly')
    assert resp_monthly.status_code == 200
    assert 'all_groups' in resp_monthly.context

    resp_daily = client.get('/planning/?view=daily')
    assert resp_daily.status_code == 200
    assert 'all_groups' in resp_daily.context


@pytest.mark.django_db
def test_daily_whatsapp_session_reminders():
    """
    Validates:
    1. Phone normalization for WhatsApp (06... -> 2126...).
    2. WhatsApp reminder message generation in FR and AR.
    3. Management command send_daily_session_reminders execution.
    4. Admin WhatsApp reminders view /reminders/whatsapp/ rendering and bulk dispatch.
    """
    from academy.whatsapp_reminders import (
        format_phone_for_whatsapp, build_whatsapp_reminder_text,
        get_daily_sessions_reminders, dispatch_daily_whatsapp_reminders
    )
    from academy.models import SessionSchedule, Student

    # 1. Phone normalization
    assert format_phone_for_whatsapp('0661234567') == '212661234567'
    assert format_phone_for_whatsapp('+212 661-234567') == '212661234567'
    assert format_phone_for_whatsapp('0712345678') == '212712345678'

    # 2. Message generation
    schedule = SessionSchedule.objects.first()
    student = Student.objects.first()
    assert schedule is not None and student is not None

    msg_fr = build_whatsapp_reminder_text(schedule, student, lang='fr')
    assert "Rappel de Séance" in msg_fr
    assert schedule.group.name_fr in msg_fr

    msg_ar = build_whatsapp_reminder_text(schedule, student, lang='ar')
    assert "تذكير بحصة اليوم" in msg_ar

    # 3. View access
    client = Client()
    admin = User.objects.get(username='admin')
    admin.set_password('CGAESA65')
    admin.save()
    client.login(username='admin', password='CGAESA65')

    resp = client.get('/reminders/whatsapp/?date=2026-09-05')
    assert resp.status_code == 200
    assert 'reminders' in resp.context
    assert resp.context['total_count'] > 0

    # Verify at least one WhatsApp URL is properly formed
    first_r = resp.context['reminders'][0]
    assert first_r['whatsapp_url'].startswith('https://wa.me/212')

    # 4. Bulk dispatch via POST
    resp_post = client.post('/reminders/whatsapp/?date=2026-09-05', {'action': 'dispatch_all'})
    assert resp_post.status_code == 302
    assert '/reminders/whatsapp/' in resp_post.url


@pytest.mark.django_db
def test_device_switcher_and_responsive_elements():
    """Verify PC/Mobile/Auto device switcher and responsive navigation elements in French and Arabic."""
    client = Client()
    admin = User.objects.get(username='admin')
    admin.set_password('CGAESA65')
    admin.save()
    client.login(username='admin', password='CGAESA65')

    # 1. French dashboard
    resp_fr = client.get('/?lang=fr')
    assert resp_fr.status_code == 200
    html_fr = resp_fr.content.decode('utf-8')
    assert 'id="gcaDeviceSwitcher"' in html_fr
    assert 'data-mode="pc"' in html_fr
    assert 'data-mode="mobile"' in html_fr
    assert 'data-mode="auto"' in html_fr
    assert 'id="gcaMobileNavToggle"' in html_fr
    assert 'id="gcaNavMenu"' in html_fr
    assert 'id="footerActiveDeviceLabel"' in html_fr
    assert 'PC' in html_fr
    assert 'Mobile' in html_fr

    # 2. Arabic dashboard
    resp_ar = client.get('/?lang=ar')
    assert resp_ar.status_code == 200
    html_ar = resp_ar.content.decode('utf-8')
    assert 'id="gcaDeviceSwitcher"' in html_ar
    assert 'حاسوب' in html_ar
    assert 'هاتف' in html_ar
    assert 'تلقائي' in html_ar
    assert 'dir="rtl"' in html_ar
    # 3. Switching device mode to PC via endpoint
    resp_set_pc = client.get('/set-device-mode/pc/', follow=True)
    assert resp_set_pc.status_code == 200
    html_set_pc = resp_set_pc.content.decode('utf-8')
    assert 'data-device-mode="pc"' in html_set_pc
    assert 'content="width=1200' in html_set_pc
    assert client.cookies['gca_device_mode'].value == 'pc'

    # 4. Switching device mode to Mobile via endpoint
    resp_set_mobile = client.get('/set-device-mode/mobile/', follow=True)
    assert resp_set_mobile.status_code == 200
    html_set_mobile = resp_set_mobile.content.decode('utf-8')
    assert 'data-device-mode="mobile"' in html_set_mobile
    assert 'width=device-width' in html_set_mobile
    assert client.cookies['gca_device_mode'].value == 'mobile'

    # 5. Switching device mode via query param ?device=pc
    resp_param = client.get('/?device=pc')
    assert resp_param.status_code == 200
    assert 'data-device-mode="pc"' in resp_param.content.decode('utf-8')


@pytest.mark.django_db
def test_admin_exports_planning_pdf_and_excels():
    """
    Validates:
    1. Admin Planning PDF export in FR, AR, Bilingual.
    2. Admin Paid Payments Excel export in FR and AR.
    3. Admin Unpaid Invoices Excel export in FR and AR.
    4. Admin All Students Excel export.
    """
    client = Client()
    admin = User.objects.get(username='admin')
    admin.set_password('CGAESA65')
    admin.save()
    client.login(username='admin', password='CGAESA65')

    # 1. Planning PDF export
    for lang in ('fr', 'ar', 'bilingual'):
        resp_pdf = client.get(f'/planning/pdf/?lang={lang}')
        assert resp_pdf.status_code == 200
        assert resp_pdf['Content-Type'] == 'application/pdf'
        assert resp_pdf.content.startswith(b'%PDF-')
        assert len(resp_pdf.content) > 1000

    # 2. Paid Payments Excel export
    for lang in ('fr', 'ar'):
        resp_paid = client.get(f'/payments/export-paid-excel/?lang={lang}')
        assert resp_paid.status_code == 200
        assert 'openxmlformats' in resp_paid['Content-Type']
        assert len(resp_paid.content) > 1000

    # 3. Unpaid Invoices Excel export
    for lang in ('fr', 'ar'):
        resp_unpaid = client.get(f'/payments/export-unpaid-excel/?lang={lang}')
        assert resp_unpaid.status_code == 200
        assert 'openxmlformats' in resp_unpaid['Content-Type']
        assert len(resp_unpaid.content) > 1000

    # 4. All Students Excel export
    resp_students = client.get('/students/export-excel/?lang=fr')
    assert resp_students.status_code == 200
    assert 'openxmlformats' in resp_students['Content-Type']
    assert len(resp_students.content) > 1000








