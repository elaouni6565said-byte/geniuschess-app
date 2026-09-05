from portal.forms import StudentForm, ParentForm, SubjectForm, GroupForm, SessionScheduleForm, PaymentForm
from decimal import Decimal
from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.contrib import messages
from django.db.models import Sum, Count, Q
from django.views.decorators.http import require_POST

from core.i18n import (
    SUPPORTED_LANGUAGES, DEFAULT_LANGUAGE, normalize_text_for_search,
    get_translation, format_currency
)
from academy.models import (
    Student, Parent, Group, Subject, Room, SessionSchedule,
    Attendance, Notification, User, ParentVisitLog
)
from finance.models import Payment, Invoice
from finance.receipt_pdf import generate_receipt_pdf
from finance.reminders import generate_monthly_reminders
from portal.excel_export import export_students_to_excel, export_paid_payments_to_excel, export_unpaid_invoices_to_excel
from portal.planning_pdf import generate_master_planning_pdf
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from portal.decorators import admin_required


def set_language(request, lang):
    """
    Immediately switches application language and persists across:
    1. Authenticated User model
    2. Request Session
    3. Long-lived Cookie
    """
    if lang in SUPPORTED_LANGUAGES:
        request.session['gca_language'] = lang
        if request.user.is_authenticated:
            request.user.preferred_language = lang
            request.user.save(update_fields=['preferred_language'])

    next_url = request.META.get('HTTP_REFERER', '/')
    response = redirect(next_url)
    if lang in SUPPORTED_LANGUAGES:
        response.set_cookie('gca_language', lang, max_age=365*24*60*60, samesite='Lax')
    return response


def set_device_mode(request, mode):
    """
    Sets the active device display mode: 'pc', 'mobile', or 'auto'.
    Saves in session and cookie, then redirects back to the previous page.
    """
    if mode not in ('pc', 'mobile', 'auto'):
        mode = 'auto'
    
    request.session['gca_device_mode'] = mode
    next_url = request.META.get('HTTP_REFERER', '/')
    response = redirect(next_url)
    response.set_cookie('gca_device_mode', mode, max_age=365*24*60*60, samesite='Lax')
    return response


def reconcile_orphan_payments():
    orphans = Payment.objects.filter(invoice__isnull=True).select_related('student')
    for p in orphans:
        p.save()

@admin_required
def dashboard_view(request):
    lang = getattr(request, 'LANGUAGE_CODE', DEFAULT_LANGUAGE)
    reconcile_orphan_payments()
    total_students = Student.objects.filter(active=True).count()
    active_groups = Group.objects.count()
    
    # Financial KPIs
    total_revenue = Payment.objects.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    invoices = Invoice.objects.filter(status__in=['unpaid', 'partial'])
    total_unpaid = sum((inv.get_balance() for inv in invoices), Decimal('0.00'))
    
    # Attendance Rate
    total_att = Attendance.objects.count()
    present_att = Attendance.objects.filter(status='present').count()
    att_rate = int((present_att / total_att * 100)) if total_att > 0 else 94

    # Today's sessions
    import datetime
    today_weekday = datetime.date.today().weekday()
    today_sessions = SessionSchedule.objects.filter(day_of_week=today_weekday).select_related('group', 'room')

    recent_payments = Payment.objects.select_related('student', 'invoice').order_by('-payment_date', '-id')[:6]
    recent_parent_visits = ParentVisitLog.objects.select_related('parent', 'student').order_by('-timestamp')[:8]
    activities = Subject.objects.all()

    context = {
        'total_students': total_students,
        'active_groups': active_groups,
        'total_revenue': total_revenue,
        'total_unpaid': total_unpaid,
        'attendance_rate': att_rate,
        'today_sessions': today_sessions,
        'recent_payments': recent_payments,
        'recent_parent_visits': recent_parent_visits,
        'activities': activities,
    }
    return render(request, 'portal/dashboard.html', context)


@admin_required
def students_list_view(request):
    lang = getattr(request, 'LANGUAGE_CODE', DEFAULT_LANGUAGE)
    query = request.GET.get('q', '').strip()
    activity_id = request.GET.get('activity')

    students = Student.objects.filter(active=True).select_related('parent').prefetch_related('groups__subject')

    if activity_id:
        students = students.filter(groups__subject_id=activity_id)

    if query:
        norm_query = normalize_text_for_search(query)
        # Search across both FR and AR first name and last name
        all_students = list(students)
        matched_ids = []
        for st in all_students:
            haystack = " ".join([
                st.registration_number,
                st.first_name_fr, st.last_name_fr,
                st.first_name_ar, st.last_name_ar,
                st.parent.full_name_fr if st.parent else "",
                st.parent.full_name_ar if st.parent else "",
                st.parent.phone if st.parent else ""
            ])
            if norm_query in normalize_text_for_search(haystack):
                matched_ids.append(st.id)
        students = Student.objects.filter(id__in=matched_ids).select_related('parent').prefetch_related('groups__subject')

    activities = Subject.objects.all()
    context = {
        'students': students,
        'activities': activities,
        'query': query,
        'selected_activity': int(activity_id) if activity_id and activity_id.isdigit() else None,
    }
    return render(request, 'portal/students.html', context)


@admin_required
def export_students_excel_view(request):
    """Export the complete list of all students (active & inactive) to Excel."""
    lang = getattr(request, 'LANGUAGE_CODE', DEFAULT_LANGUAGE)
    students = Student.objects.all().select_related('parent').prefetch_related('groups__subject').order_by('last_name_fr', 'first_name_fr')
    excel_data = export_students_to_excel(students, lang=lang)

    filename = f"GCA_Tous_Eleves_{lang}.xlsx"
    response = HttpResponse(
        excel_data,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@admin_required
def download_planning_pdf_view(request):
    """Export the official master timetable of the academy to a Landscape A4 PDF."""
    lang = getattr(request, 'LANGUAGE_CODE', DEFAULT_LANGUAGE)
    room_id = request.GET.get('room')
    room = None
    schedules = SessionSchedule.objects.select_related('group', 'group__subject', 'room').all()
    if room_id and room_id.isdigit():
        schedules = schedules.filter(room_id=int(room_id))
        room = Room.objects.filter(id=int(room_id)).first()

    pdf_data = generate_master_planning_pdf(schedules, lang=lang, room=room)
    filename = f"GCA_Planning_Officiel_{lang}.pdf"
    response = HttpResponse(pdf_data, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="{filename}"'
    return response


@admin_required
def export_paid_payments_excel_view(request):
    """Export the list of paid payments / encaissements to an official Excel workbook."""
    lang = getattr(request, 'LANGUAGE_CODE', DEFAULT_LANGUAGE)
    payments = Payment.objects.select_related('student', 'student__parent', 'invoice', 'invoice__group', 'invoice__group__subject').order_by('-payment_date', '-id')
    excel_data = export_paid_payments_to_excel(payments, lang=lang)

    filename = f"GCA_Liste_Payants_{lang}.xlsx"
    response = HttpResponse(
        excel_data,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@admin_required
def export_unpaid_invoices_excel_view(request):
    """Export the list of unpaid/partially paid students (Impayés) to an official Excel workbook."""
    lang = getattr(request, 'LANGUAGE_CODE', DEFAULT_LANGUAGE)
    unpaid_invoices = Invoice.objects.filter(status__in=['unpaid', 'partial']).select_related('student', 'student__parent', 'group', 'group__subject').order_by('-period_year', '-period_month', 'student__last_name_fr')
    excel_data = export_unpaid_invoices_to_excel(unpaid_invoices, lang=lang)

    filename = f"GCA_Liste_Impayes_{lang}.xlsx"
    response = HttpResponse(
        excel_data,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@admin_required
def planning_view(request):
    import calendar
    from datetime import date, datetime, time, timedelta
    from core.i18n import FRENCH_DAYS, ARABIC_DAYS, FRENCH_MONTHS, ARABIC_MONTHS

    lang = getattr(request, 'LANGUAGE_CODE', DEFAULT_LANGUAGE)
    current_view = request.GET.get('view', 'monthly')
    if current_view not in ('daily', 'monthly', 'annual'):
        current_view = 'monthly'

    room_id = request.GET.get('room')
    schedules = SessionSchedule.objects.select_related('group', 'group__subject', 'room').order_by('day_of_week', 'start_time')
    if room_id and room_id.isdigit():
        schedules = schedules.filter(room_id=int(room_id))

    rooms = Room.objects.all()
    days_dict = ARABIC_DAYS if lang == 'ar' else FRENCH_DAYS
    months_dict = ARABIC_MONTHS if lang == 'ar' else FRENCH_MONTHS

    # Today anchor
    today = date(2026, 9, 3)
    all_groups = Group.objects.select_related('subject').all()

    context = {
        'current_view': current_view,
        'rooms': rooms,
        'selected_room': int(room_id) if room_id and room_id.isdigit() else None,
        'today': today,
        'all_groups': all_groups,
    }

    if current_view == 'daily':
        # --- DAILY VIEW ---
        date_param = request.GET.get('date')
        if date_param:
            try:
                sel_date = datetime.strptime(date_param, '%Y-%m-%d').date()
            except ValueError:
                sel_date = today
        else:
            sel_date = today

        day_of_week = sel_date.weekday()
        day_sessions = list(schedules.filter(day_of_week=day_of_week))
        
        hourly_timeline = []
        for hour in range(8, 20):
            matching = [s for s in day_sessions if s.start_time.hour == hour]
            hourly_timeline.append({
                'hour': f"{hour:02d}:00",
                'sessions': matching
            })

        context.update({
            'sel_date': sel_date,
            'day_name': days_dict.get(day_of_week, ''),
            'prev_date': (sel_date - timedelta(days=1)).strftime('%Y-%m-%d'),
            'next_date': (sel_date + timedelta(days=1)).strftime('%Y-%m-%d'),
            'day_sessions': day_sessions,
            'hourly_timeline': hourly_timeline,
            'is_today': sel_date == today,
        })

    elif current_view == 'monthly':
        # --- MONTHLY VIEW ---
        try:
            year = int(request.GET.get('year', today.year))
            month = int(request.GET.get('month', today.month))
        except (ValueError, TypeError):
            year, month = today.year, today.month

        if month < 1:
            month = 1
        elif month > 12:
            month = 12

        cal = calendar.Calendar(firstweekday=0)
        month_weeks = []
        for week in cal.monthdatescalendar(year, month):
            week_days = []
            for d in week:
                d_dow = d.weekday()
                d_sessions = [s for s in schedules if s.day_of_week == d_dow]
                week_days.append({
                    'date': d,
                    'date_str': d.strftime('%Y-%m-%d'),
                    'day_num': d.day,
                    'is_current_month': d.month == month,
                    'is_today': d == today,
                    'day_of_week': d_dow,
                    'sessions': d_sessions,
                })
            month_weeks.append(week_days)

        if month == 1:
            prev_m, prev_y = 12, year - 1
        else:
            prev_m, prev_y = month - 1, year

        if month == 12:
            next_m, next_y = 1, year + 1
        else:
            next_m, next_y = month + 1, year

        weekdays_header = [days_dict.get(i, '') for i in range(7)]

        context.update({
            'year': year,
            'month': month,
            'month_name': months_dict.get(month, '').capitalize(),
            'month_weeks': month_weeks,
            'weekdays_header': weekdays_header,
            'prev_month': prev_m,
            'prev_year': prev_y,
            'next_month': next_m,
            'next_year': next_y,
        })

    elif current_view == 'annual':
        # --- ANNUAL VIEW ---
        try:
            year = int(request.GET.get('year', today.year))
        except (ValueError, TypeError):
            year = today.year

        annual_months = []
        cal = calendar.Calendar(firstweekday=0)
        total_year_sessions = 0
        subjects = Subject.objects.all()

        for m in range(1, 13):
            m_cal_days = [d for d in cal.itermonthdates(year, m) if d.month == m]
            m_total_sessions = 0
            m_subject_counts = {subj.id: {'subj': subj, 'count': 0} for subj in subjects}
            
            for d in m_cal_days:
                d_dow = d.weekday()
                for s in schedules:
                    if s.day_of_week == d_dow:
                        m_total_sessions += 1
                        if s.group.subject_id in m_subject_counts:
                            m_subject_counts[s.group.subject_id]['count'] += 1

            total_year_sessions += m_total_sessions
            annual_months.append({
                'month_num': m,
                'month_name': months_dict.get(m, '').capitalize(),
                'year': year,
                'total_sessions': m_total_sessions,
                'subject_counts': [v for v in m_subject_counts.values() if v['count'] > 0],
                'is_current_month': (m == today.month and year == today.year),
            })

        context.update({
            'year': year,
            'prev_year': year - 1,
            'next_year': year + 1,
            'annual_months': annual_months,
            'total_year_sessions': total_year_sessions,
        })

    return render(request, 'portal/planning.html', context)


@admin_required
def payments_list_view(request):
    lang = getattr(request, 'LANGUAGE_CODE', DEFAULT_LANGUAGE)
    reconcile_orphan_payments()
    payments = Payment.objects.select_related('student', 'invoice', 'invoice__group').order_by('-payment_date', '-id')
    unpaid_invoices = Invoice.objects.filter(status__in=['unpaid', 'partial']).select_related('student', 'group')
    
    context = {
        'payments': payments,
        'unpaid_invoices': unpaid_invoices,
    }
    return render(request, 'portal/payments.html', context)


def download_receipt_pdf_view(request, payment_id):
    lang = request.GET.get('lang')
    if not lang:
        lang = getattr(request, 'LANGUAGE_CODE', DEFAULT_LANGUAGE)
        
    payment = get_object_or_404(Payment.objects.select_related('student__parent', 'invoice'), id=payment_id)
    
    # Check permissions: Admin or Parent of this student
    is_admin = request.user.is_authenticated and (request.user.is_admin_role() or request.user.is_superuser)
    is_owner_parent = request.user.is_authenticated and hasattr(request.user, 'parent_profile') and payment.student.parent == request.user.parent_profile
    if not (is_admin or is_owner_parent):
        if not request.user.is_authenticated:
            return redirect(f'/login/?next={request.path}')
        messages.error(request, get_translation('errors.permission_denied', lang=lang))
        return redirect('portal:parent_space')

    pdf_bytes = generate_receipt_pdf(payment, lang=lang)
    
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    filename = f"Recu_{payment.receipt_number}_{lang}.pdf"
    response['Content-Disposition'] = f'inline; filename="{filename}"'
    return response


def download_timetable_pdf_view(request, student_id):
    from portal.timetable_pdf import generate_timetable_pdf
    lang = request.GET.get('lang')
    if not lang:
        lang = getattr(request, 'LANGUAGE_CODE', DEFAULT_LANGUAGE)
        
    student = get_object_or_404(Student.objects.select_related('parent').prefetch_related('groups__subject', 'groups__schedules__room'), id=student_id)
    
    # Check permissions: Admin or Parent of this student
    is_admin = request.user.is_authenticated and (request.user.is_admin_role() or request.user.is_superuser)
    is_owner_parent = request.user.is_authenticated and hasattr(request.user, 'parent_profile') and student.parent == request.user.parent_profile
    if not (is_admin or is_owner_parent):
        if not request.user.is_authenticated:
            return redirect(f'/login/?next={request.path}')
        messages.error(request, get_translation('errors.permission_denied', lang=lang))
        return redirect('portal:parent_space')

    pdf_bytes = generate_timetable_pdf(student, lang=lang)
    filename = f"Emploi_Du_Temps_{student.registration_number}_{lang}.pdf"
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="{filename}"'
    return response


@admin_required
def run_reminders_view(request):
    lang = getattr(request, 'LANGUAGE_CODE', DEFAULT_LANGUAGE)
    sent = generate_monthly_reminders()
    count = len(sent)
    
    if count > 0:
        msg = get_translation('reminders.count_sent', lang=lang, count=count)
        messages.success(request, f"✓ {msg}")
    else:
        empty_msg = "Aucun impayé à relancer. Tous les paiements sont à jour." if lang == 'fr' else "لا توجد مستحقات معلقة حالياً. جميع الحسابات مسواة."
        messages.info(request, empty_msg)
        
    return redirect('portal:dashboard')


def parent_space_view(request):
    lang = getattr(request, 'LANGUAGE_CODE', DEFAULT_LANGUAGE)
    
    # 1. Require Authentication: Anonymous users cannot access parent space!
    if not request.user.is_authenticated:
        return redirect(f'/login/?next=/parent/')

    all_parents = []
    parent = None
    
    # 2. If user is a Parent:
    if request.user.is_parent_role():
        if hasattr(request.user, 'parent_profile'):
            parent = request.user.parent_profile
        else:
            parent = Parent.objects.filter(user=request.user).first()
        # Strictly empty: a parent NEVER has access to any other family list!
        all_parents = []
    
    # 3. If user is Admin / Superuser (for preview purposes only)
    elif request.user.is_admin_role() or request.user.is_superuser:
        all_parents = list(Parent.objects.all().order_by('id'))
        family_id = request.GET.get('family_id')
        if family_id and family_id.isdigit():
            parent = Parent.objects.filter(id=int(family_id)).first()
        if not parent and all_parents:
            parent = all_parents[0]
    else:
        return redirect('portal:login')

    if not parent:
        messages.warning(request, "Aucun profil parent associé à ce compte." if lang == 'fr' else "لا يوجد ملف ولي أمر مرتبط بهذا الحساب.")
        return redirect('portal:login')

    # 4. Get all children belonging STRICTLY to this parent
    all_children = list(parent.students.filter(active=True).prefetch_related(
        'groups__subject', 'groups__schedules__room'
    ))

    # Process all children metrics
    for ch in all_children:
        child_schedules = []
        for g in ch.groups.all():
            for sch in g.schedules.all():
                child_schedules.append({
                    'group': g,
                    'subject': g.subject,
                    'room': sch.room or g.room,
                    'schedule': sch,
                    'day_of_week': sch.day_of_week,
                    'day_name_fr': sch.get_day_name('fr'),
                    'day_name_ar': sch.get_day_name('ar'),
                    'start_time': sch.start_time,
                    'end_time': sch.end_time,
                    'trainer_fr': sch.get_trainer_name('fr'),
                    'trainer_ar': sch.get_trainer_name('ar'),
                })
        child_schedules.sort(key=lambda x: (x['day_of_week'], x['start_time']))
        ch.child_schedules = child_schedules

        child_att = list(Attendance.objects.filter(student=ch).select_related('session__group__subject').order_by('-date'))
        ch.child_attendances = child_att
        ch.total_sessions = len(child_att)
        ch.present_count = len([a for a in child_att if a.status == 'present'])
        ch.justified_count = len([a for a in child_att if a.status == 'justified'])
        ch.absent_count = len([a for a in child_att if a.status == 'absent'])
        ch.late_count = len([a for a in child_att if a.status == 'late'])
        ch.attendance_rate = round((ch.present_count / ch.total_sessions) * 100) if ch.total_sessions > 0 else 100

    # 5. Child filtering (navigation between the parent's OWN children)
    child_id_param = request.GET.get('child_id')
    selected_child_id = None
    if child_id_param and child_id_param.isdigit():
        target_id = int(child_id_param)
        # Verify strictly that target_id is among THIS parent's children!
        if any(c.id == target_id for c in all_children):
            selected_child_id = target_id
            children = [c for c in all_children if c.id == target_id]
        else:
            children = all_children
    else:
        children = all_children

    # Invoices & Payments strictly for the selected / all children of THIS parent
    visible_child_ids = [c.id for c in children]
    invoices = Invoice.objects.filter(student_id__in=visible_child_ids).select_related('student', 'group').order_by('-due_date')
    payments = Payment.objects.filter(student_id__in=visible_child_ids).select_related('student', 'invoice').order_by('-payment_date')
    
    user_notifications = Notification.objects.filter(recipient=parent.user).order_by('-created_at')[:8] if parent and parent.user else []

    # Enregistrement de la visite parent pour le suivi admin (avec anti-spam de 5 min)
    if request.user.is_parent_role() and parent:
        import datetime
        from django.utils import timezone
        now = timezone.now()
        client_ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', ''))
        if client_ip and ',' in client_ip:
            client_ip = client_ip.split(',')[0].strip()

        # Enregistrer pour l'enfant visualisé spécifiquement ou le premier enfant
        target_student = children[0] if children else None
        if target_student:
            recent_visit = ParentVisitLog.objects.filter(
                parent=parent,
                student=target_student,
                timestamp__gte=now - datetime.timedelta(minutes=5)
            ).first()
            if not recent_visit:
                ParentVisitLog.objects.create(
                    parent=parent,
                    student=target_student,
                    ip_address=client_ip or ''
                )

    context = {
        'parent': parent,
        'all_parents': all_parents,
        'all_children': all_children,
        'children': children,
        'selected_child_id': selected_child_id,
        'invoices': invoices,
        'payments': payments,
        'notifications': user_notifications,
    }
    return render(request, 'portal/parent_space.html', context)


def login_view(request):
    import re
    lang = getattr(request, 'LANGUAGE_CODE', DEFAULT_LANGUAGE)
    next_url = request.GET.get('next') or request.POST.get('next') or '/'

    if request.user.is_authenticated:
        if request.user.is_parent_role():
            return redirect('portal:parent_space')
        elif request.user.is_admin_role() or request.user.is_superuser:
            return redirect(next_url if next_url != '/login/' else '/')

    error_msg = None
    entered_username = request.GET.get('u', '')

    if request.method == 'POST':
        raw_identifier = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()
        entered_username = raw_identifier

        user = None

        # 1. Standard Django authenticate by exact username
        if raw_identifier:
            user = authenticate(request, username=raw_identifier, password=password)

        # 2. Normalized username (replace spaces with underscores, lowercase)
        if user is None and raw_identifier:
            slug_username = re.sub(r'[\s\-]+', '_', raw_identifier.strip().lower())
            user = authenticate(request, username=slug_username, password=password)

        norm_input = normalize_text_for_search(raw_identifier)

        # 3. Look up Parent by Parent Name (French or Arabic) with full unicode normalization
        if user is None and norm_input:
            for p in Parent.objects.select_related('user').all():
                p_norm_fr = normalize_text_for_search(p.full_name_fr)
                p_norm_ar = normalize_text_for_search(p.full_name_ar)
                if (norm_input == p_norm_fr or 
                    norm_input == p_norm_ar or 
                    norm_input in p_norm_fr or 
                    p_norm_fr in norm_input or
                    norm_input in p_norm_ar or 
                    p_norm_ar in norm_input):
                    if p.user and p.user.check_password(password):
                        user = p.user
                        break

        # 4. Look up Parent by Student / Child Name (French or Arabic) or Registration Number
        if user is None and norm_input:
            # Check registration number (matricule)
            st_mat = Student.objects.filter(registration_number__iexact=raw_identifier).select_related('parent__user').first()
            if st_mat and st_mat.parent and st_mat.parent.user and st_mat.parent.user.check_password(password):
                user = st_mat.parent.user

            if user is None:
                # Search students by normalized name
                for st in Student.objects.select_related('parent__user').all():
                    fr_full = normalize_text_for_search(f"{st.first_name_fr} {st.last_name_fr}")
                    ar_full = normalize_text_for_search(f"{st.first_name_ar} {st.last_name_ar}")
                    st_fn_fr = normalize_text_for_search(st.first_name_fr)
                    st_ln_fr = normalize_text_for_search(st.last_name_fr)
                    st_fn_ar = normalize_text_for_search(st.first_name_ar)
                    st_ln_ar = normalize_text_for_search(st.last_name_ar)
                    
                    if (norm_input == fr_full or 
                        norm_input == ar_full or 
                        norm_input == st_fn_fr or 
                        norm_input == st_ln_fr or
                        norm_input == st_fn_ar or 
                        norm_input == st_ln_ar or
                        norm_input in fr_full or 
                        fr_full in norm_input or
                        norm_input in ar_full or
                        ar_full in norm_input):
                        if st.parent and st.parent.user and st.parent.user.check_password(password):
                            user = st.parent.user
                            break

        # 5. Look up Parent by Phone Number, CIN or Email
        if user is None and raw_identifier:
            cleaned_phone = re.sub(r'[^0-9]', '', raw_identifier)
            parent_contact = Parent.objects.filter(
                Q(phone__icontains=raw_identifier) |
                (Q(phone__icontains=cleaned_phone) if cleaned_phone else Q(id__isnull=True)) |
                Q(cin__iexact=raw_identifier) |
                Q(email__iexact=raw_identifier)
            ).select_related('user').first()
            if parent_contact and parent_contact.user and parent_contact.user.check_password(password):
                user = parent_contact.user

        if user is not None:
            auth_login(request, user)
            # Sync language
            if user.preferred_language:
                request.session['gca_language'] = user.preferred_language
            if user.is_parent_role():
                return redirect('portal:parent_space')
            return redirect(next_url if next_url != '/login/' else '/')
        else:
            error_msg = get_translation('auth.invalid_credentials', lang=lang)

    context = {
        'error_msg': error_msg,
        'next_url': next_url,
        'entered_username': entered_username,
    }
    return render(request, 'portal/login.html', context)

def logout_view(request):
    lang = getattr(request, 'LANGUAGE_CODE', DEFAULT_LANGUAGE)
    auth_logout(request)
    messages.info(request, get_translation('auth.logged_out', lang=lang))
    return redirect('portal:login')


def csrf_failure_view(request, reason=""):
    """Graceful bilingual error page for expired CSRF tokens."""
    return render(request, 'portal/csrf_failure.html', status=403)


# ==========================================
# 1. ÉLÈVES CRUD (MULTI-ACTIVITÉS)
# ==========================================

@admin_required
def student_create_view(request):
    lang = getattr(request, 'LANGUAGE_CODE', DEFAULT_LANGUAGE)
    if request.method == 'POST':
        form = StudentForm(request.POST)
        if form.is_valid():
            student = form.save()
            msg = get_translation('crud.created_success', lang=lang)
            messages.success(request, f"✓ {msg} ({student.get_bilingual_full_name()})")
            return redirect('portal:students')
    else:
        form = StudentForm()

    context = {
        'form': form,
        'is_edit': False,
        'title': get_translation('student_crud.add_title', lang=lang),
    }
    return render(request, 'portal/student_form.html', context)


@admin_required
def student_edit_view(request, student_id):
    lang = getattr(request, 'LANGUAGE_CODE', DEFAULT_LANGUAGE)
    student = get_object_or_404(Student, id=student_id)
    if request.method == 'POST':
        form = StudentForm(request.POST, instance=student)
        if form.is_valid():
            student = form.save()
            msg = get_translation('crud.updated_success', lang=lang)
            messages.success(request, f"✓ {msg}")
            return redirect('portal:students')
    else:
        form = StudentForm(instance=student)

    context = {
        'form': form,
        'student': student,
        'is_edit': True,
        'title': get_translation('student_crud.edit_title', lang=lang),
    }
    return render(request, 'portal/student_form.html', context)


@admin_required
def student_delete_view(request, student_id):
    lang = getattr(request, 'LANGUAGE_CODE', DEFAULT_LANGUAGE)
    student = get_object_or_404(Student, id=student_id)
    if request.method == 'POST':
        name = student.get_bilingual_full_name()
        student.delete()
        msg = get_translation('crud.deleted_success', lang=lang)
        messages.success(request, f"✓ {msg} ({name})")
        return redirect('portal:students')

    context = {
        'item_name': student.get_bilingual_full_name(),
        'item_type': 'Élève / تلميذ',
        'cancel_url': '/students/',
    }
    return render(request, 'portal/confirm_delete.html', context)


# ==========================================
# 2. PARENTS CRUD
# ==========================================

@admin_required
def parents_list_view(request):
    parents = Parent.objects.annotate(children_count=Count('students')).order_by('-id')
    context = {
        'parents': parents,
    }
    return render(request, 'portal/parents_list.html', context)


@admin_required
def parent_create_view(request):
    lang = getattr(request, 'LANGUAGE_CODE', DEFAULT_LANGUAGE)
    if request.method == 'POST':
        form = ParentForm(request.POST)
        if form.is_valid():
            parent = form.save()
            msg = get_translation('crud.created_success', lang=lang)
            messages.success(request, f"✓ {msg} ({parent.full_name_fr} / {parent.full_name_ar})")
            return redirect('portal:parents_list')
    else:
        form = ParentForm()

    context = {
        'form': form,
        'is_edit': False,
        'title': get_translation('parent_crud.add_title', lang=lang),
    }
    return render(request, 'portal/parent_form.html', context)


@admin_required
def parent_edit_view(request, parent_id):
    lang = getattr(request, 'LANGUAGE_CODE', DEFAULT_LANGUAGE)
    parent = get_object_or_404(Parent, id=parent_id)
    if request.method == 'POST':
        form = ParentForm(request.POST, instance=parent)
        if form.is_valid():
            form.save()
            msg = get_translation('crud.updated_success', lang=lang)
            messages.success(request, f"✓ {msg}")
            return redirect('portal:parents_list')
    else:
        form = ParentForm(instance=parent)

    context = {
        'form': form,
        'parent': parent,
        'is_edit': True,
        'title': get_translation('parent_crud.edit_title', lang=lang),
    }
    return render(request, 'portal/parent_form.html', context)


@admin_required
def parent_delete_view(request, parent_id):
    lang = getattr(request, 'LANGUAGE_CODE', DEFAULT_LANGUAGE)
    parent = get_object_or_404(Parent, id=parent_id)
    if request.method == 'POST':
        name = f"{parent.full_name_fr} / {parent.full_name_ar}"
        # Also clean up associated user if any
        if parent.user:
            parent.user.delete()
        parent.delete()
        msg = get_translation('crud.deleted_success', lang=lang)
        messages.success(request, f"✓ {msg} ({name})")
        return redirect('portal:parents_list')

    context = {
        'item_name': f"{parent.full_name_fr} / {parent.full_name_ar}",
        'item_type': 'Parent / ولي أمر',
        'cancel_url': '/parents/',
    }
    return render(request, 'portal/confirm_delete.html', context)


# ==========================================
# 3. ACTIVITÉS & GROUPES CRUD
# ==========================================

@admin_required
def activities_list_view(request):
    subjects = Subject.objects.prefetch_related('groups__students', 'groups__level').all()
    context = {
        'subjects': subjects,
    }
    return render(request, 'portal/activities_list.html', context)


@admin_required
def activity_create_view(request):
    lang = getattr(request, 'LANGUAGE_CODE', DEFAULT_LANGUAGE)
    if request.method == 'POST':
        form = SubjectForm(request.POST)
        if form.is_valid():
            subj = form.save()
            msg = get_translation('crud.created_success', lang=lang)
            messages.success(request, f"✓ {msg} ({subj.get_bilingual_name()})")
            return redirect('portal:activities_list')
    else:
        form = SubjectForm()

    context = {
        'form': form,
        'is_edit': False,
        'title': get_translation('activity_crud.add_activity', lang=lang),
    }
    return render(request, 'portal/activity_form.html', context)


@admin_required
def activity_edit_view(request, subject_id):
    lang = getattr(request, 'LANGUAGE_CODE', DEFAULT_LANGUAGE)
    subject = get_object_or_404(Subject, id=subject_id)
    if request.method == 'POST':
        form = SubjectForm(request.POST, instance=subject)
        if form.is_valid():
            subj = form.save()
            msg = get_translation('crud.updated_success', lang=lang)
            messages.success(request, f"✓ {msg} ({subj.get_bilingual_name()})")
            return redirect('portal:activities_list')
    else:
        form = SubjectForm(instance=subject)

    context = {
        'form': form,
        'is_edit': True,
        'subject': subject,
        'title': get_translation('activity_crud.edit_activity', lang=lang),
    }
    return render(request, 'portal/activity_form.html', context)


@admin_required
def activity_delete_view(request, subject_id):
    lang = getattr(request, 'LANGUAGE_CODE', DEFAULT_LANGUAGE)
    subject = get_object_or_404(Subject, id=subject_id)
    if request.method == 'POST':
        name = subject.get_bilingual_name()
        subject.delete()
        msg = get_translation('crud.deleted_success', lang=lang)
        messages.success(request, f"✓ {msg} ({name})")
        return redirect('portal:activities_list')

    context = {
        'item_name': subject.get_bilingual_name(),
        'item_type': 'Activité / نشاط',
        'cancel_url': '/activities/',
    }
    return render(request, 'portal/confirm_delete.html', context)


@admin_required
def group_create_view(request):
    lang = getattr(request, 'LANGUAGE_CODE', DEFAULT_LANGUAGE)
    if request.method == 'POST':
        form = GroupForm(request.POST)
        if form.is_valid():
            group = form.save()
            msg = get_translation('crud.created_success', lang=lang)
            messages.success(request, f"✓ {msg} ({group.name_fr})")
            return redirect('portal:activities_list')
    else:
        form = GroupForm()

    context = {
        'form': form,
        'is_edit': False,
        'title': get_translation('activity_crud.add_group', lang=lang),
    }
    return render(request, 'portal/group_form.html', context)


@admin_required
def group_edit_view(request, group_id):
    lang = getattr(request, 'LANGUAGE_CODE', DEFAULT_LANGUAGE)
    group = get_object_or_404(Group, id=group_id)
    if request.method == 'POST':
        form = GroupForm(request.POST, instance=group)
        if form.is_valid():
            grp = form.save()
            msg = get_translation('crud.updated_success', lang=lang)
            messages.success(request, f"✓ {msg} ({grp.name_fr})")
            return redirect('portal:activities_list')
    else:
        form = GroupForm(instance=group)

    context = {
        'form': form,
        'is_edit': True,
        'group': group,
        'title': get_translation('activity_crud.edit_group', lang=lang),
    }
    return render(request, 'portal/group_form.html', context)


@admin_required
def group_delete_view(request, group_id):
    lang = getattr(request, 'LANGUAGE_CODE', DEFAULT_LANGUAGE)
    group = get_object_or_404(Group, id=group_id)
    if request.method == 'POST':
        name = group.name_fr
        group.delete()
        msg = get_translation('crud.deleted_success', lang=lang)
        messages.success(request, f"✓ {msg} ({name})")
        return redirect('portal:activities_list')

    context = {
        'item_name': group.name_fr,
        'item_type': 'Groupe / مجموعة',
        'cancel_url': '/activities/',
    }
    return render(request, 'portal/confirm_delete.html', context)


# ==========================================
# 4. PLANNING & CRÉNEAUX CRUD
# ==========================================

@admin_required
def session_create_view(request):
    lang = getattr(request, 'LANGUAGE_CODE', DEFAULT_LANGUAGE)
    if request.method == 'POST':
        form = SessionScheduleForm(request.POST)
        if form.is_valid():
            session = form.save()
            msg = get_translation('crud.created_success', lang=lang)
            messages.success(request, f"✓ {msg}")
            return redirect('portal:planning')
    else:
        form = SessionScheduleForm()

    context = {
        'form': form,
        'is_edit': False,
        'title': get_translation('planning_crud.add_session', lang=lang),
    }
    return render(request, 'portal/session_form.html', context)


@admin_required
def session_edit_view(request, session_id):
    lang = getattr(request, 'LANGUAGE_CODE', DEFAULT_LANGUAGE)
    session = get_object_or_404(SessionSchedule, id=session_id)
    if request.method == 'POST':
        form = SessionScheduleForm(request.POST, instance=session)
        if form.is_valid():
            form.save()
            msg = get_translation('crud.updated_success', lang=lang)
            messages.success(request, f"✓ {msg}")
            return redirect('portal:planning')
    else:
        form = SessionScheduleForm(instance=session)

    context = {
        'form': form,
        'session': session,
        'is_edit': True,
        'title': get_translation('planning_crud.edit_session', lang=lang),
    }
    return render(request, 'portal/session_form.html', context)


@admin_required
def session_delete_view(request, session_id):
    lang = getattr(request, 'LANGUAGE_CODE', DEFAULT_LANGUAGE)
    session = get_object_or_404(SessionSchedule, id=session_id)
    if request.method == 'POST':
        session.delete()
        msg = get_translation('crud.deleted_success', lang=lang)
        messages.success(request, f"✓ {msg}")
        return redirect('portal:planning')

    context = {
        'item_name': str(session),
        'item_type': 'Créneau de cours / حصة دراسية',
        'cancel_url': '/planning/',
    }
    return render(request, 'portal/confirm_delete.html', context)


def register_view(request):
    """
    Public family registration portal.
    Parents can self-register their family and one or more children.
    """
    import re
    import datetime
    lang = getattr(request, 'LANGUAGE_CODE', DEFAULT_LANGUAGE)
    error_msg = None

    if request.method == 'POST':
        parent_name_fr = request.POST.get('parent_name_fr', '').strip()
        parent_name_ar = request.POST.get('parent_name_ar', '').strip()
        parent_phone = request.POST.get('parent_phone', '').strip()
        parent_email = request.POST.get('parent_email', '').strip()
        parent_address = request.POST.get('parent_address', '').strip()

        # Nettoyage
        parent_name_fr = re.sub(r'[\u064B-\u0652\u0670]', '', parent_name_fr)
        parent_name_fr = re.sub(r'\s+', ' ', parent_name_fr).strip()
        parent_name_ar = re.sub(r'\s+', ' ', parent_name_ar).strip()

        # 1. Validation des champs obligatoires du tuteur
        if not parent_name_fr or not parent_name_ar or not parent_phone:
            error_msg = (
                "Veuillez renseigner le nom complet du tuteur (FR et AR) ainsi que le numéro de téléphone."
                if lang == 'fr' else
                "يرجى ملء الاسم الكامل لولي الأمر (بالعربية والفرنسية) ورقم الهاتف الإلزامي."
            )
        else:
            # 2. Validation des enfants
            children_names_fr = request.POST.getlist('child_name_fr[]')
            children_names_ar = request.POST.getlist('child_name_ar[]')
            children_birth_dates = request.POST.getlist('child_birth_date[]')
            children_schools = request.POST.getlist('child_school[]')
            children_grades = request.POST.getlist('child_grade_level[]')

            valid_children = []
            for i in range(len(children_names_fr)):
                cfr = children_names_fr[i].strip() if i < len(children_names_fr) else ''
                car = children_names_ar[i].strip() if i < len(children_names_ar) else ''
                cbd = children_birth_dates[i].strip() if i < len(children_birth_dates) else ''
                csc = children_schools[i].strip() if i < len(children_schools) else ''
                cgr = children_grades[i].strip() if i < len(children_grades) else ''

                if cfr or car or cbd or csc or cgr:
                    if not cfr or not car or not cbd:
                        error_msg = (
                            "Pour chaque enfant, le nom en français, le nom en arabe et la date de naissance sont obligatoires."
                            if lang == 'fr' else
                            "بالنسبة لكل طفل، الاسم بالفرنسية والاسم بالعربية وتاريخ الازدياد إلزامي."
                        )
                        break
                    valid_children.append({
                        'name_fr': cfr,
                        'name_ar': car,
                        'birth_date': cbd,
                        'school': csc,
                        'grade_level': cgr,
                    })

            if not error_msg and not valid_children:
                error_msg = (
                    "Veuillez inscrire au moins un enfant (fils ou fille)."
                    if lang == 'fr' else
                    "يرجى تسجيل طفل واحد على الأقل (ابن أو ابنة)."
                )

            if not error_msg:
                # 3. Création ou association du Parent
                clean_phone = re.sub(r'[^0-9+]', '', parent_phone)
                phone_suffix = clean_phone[-9:] if len(clean_phone) >= 9 else clean_phone
                parent = Parent.objects.filter(phone__icontains=phone_suffix).first() if phone_suffix else None

                if not parent:
                    parent = Parent.objects.create(
                        full_name_fr=parent_name_fr,
                        full_name_ar=parent_name_ar,
                        phone=parent_phone,
                        email=parent_email,
                        address=parent_address,
                        preferred_language=lang
                    )
                else:
                    if parent_email and not parent.email:
                        parent.email = parent_email
                    if parent_address and not parent.address:
                        parent.address = parent_address
                    parent.save()

                # Création automatique du compte Espace Parent si inexistant
                if not parent.user:
                    clean_name = re.sub(r'[^a-zA-Z0-9]+', '_', parent.full_name_fr.strip().lower()).strip('_')
                    username = f"parent_{clean_name}"[:25]
                    if User.objects.filter(username=username).exists():
                        username = f"{username}_{User.objects.count()}"[:30]

                    user = User.objects.create_user(
                        username=username,
                        email=parent.email or f"{username}@gca.ma",
                        password="Parent@2026",
                        role="parent",
                        preferred_language=lang
                    )
                    parent.user = user
                    parent.save(update_fields=['user'])

                # 4. Création des élèves
                created_students = []
                for ch in valid_children:
                    parts_fr = ch['name_fr'].split()
                    first_name_fr = parts_fr[0] if parts_fr else ch['name_fr']
                    last_name_fr = " ".join(parts_fr[1:]) if len(parts_fr) > 1 else ""

                    parts_ar = ch['name_ar'].split()
                    first_name_ar = parts_ar[0] if parts_ar else ch['name_ar']
                    last_name_ar = " ".join(parts_ar[1:]) if len(parts_ar) > 1 else ""

                    count = Student.objects.count() + 1
                    reg = f"GCA-2026-{count:03d}"
                    while Student.objects.filter(registration_number=reg).exists():
                        count += 1
                        reg = f"GCA-2026-{count:03d}"

                    try:
                        bdate = datetime.datetime.strptime(ch['birth_date'], '%Y-%m-%d').date()
                    except (ValueError, TypeError):
                        bdate = None

                    st = Student.objects.create(
                        registration_number=reg,
                        first_name_fr=first_name_fr,
                        last_name_fr=last_name_fr,
                        first_name_ar=first_name_ar,
                        last_name_ar=last_name_ar,
                        birth_date=bdate,
                        school=ch['school'],
                        grade_level=ch['grade_level'],
                        parent=parent,
                        active=True
                    )
                    created_students.append(st)

                return render(request, 'portal/register_success.html', {
                    'parent': parent,
                    'students': created_students,
                    'CURRENT_LANG': lang,
                })

    return render(request, 'portal/register.html', {
        'error_msg': error_msg,
        'CURRENT_LANG': lang,
    })


@admin_required
def payment_create_view(request):
    lang = getattr(request, 'LANGUAGE_CODE', DEFAULT_LANGUAGE)
    security_code_expected = getattr(settings, 'ADMIN_FINANCIAL_SECURITY_CODE', '6565')
    error_msg = None

    if request.method == 'POST':
        form = PaymentForm(request.POST)
        entered_code = request.POST.get('security_code', '').strip()
        if entered_code != security_code_expected:
            error_msg = (
                "Code spécial de sécurité incorrect ! Opération non autorisée."
                if lang == 'fr' else
                "الرمز السري المالي الخاص غير صحيح ! العملية غير مسموح بها."
            )
        else:
            if form.is_valid():
                p = form.save(commit=False)
                count = Payment.objects.count() + 1
                rec_no = f"REC-2026-{count:04d}"
                while Payment.objects.filter(receipt_number=rec_no).exists():
                    count += 1
                    rec_no = f"REC-2026-{count:04d}"
                p.receipt_number = rec_no
                p.created_by = request.user
                p.save()

                msg = get_translation('crud.created_success', lang=lang)
                messages.success(request, f"✓ {msg} (#{rec_no})")
                return redirect('portal:payments')
    else:
        import datetime
        initial_data = {'payment_date': datetime.date.today(), 'security_code': ''}
        if request.GET.get('student'):
            initial_data['student'] = request.GET.get('student')
        if request.GET.get('invoice'):
            initial_data['invoice'] = request.GET.get('invoice')
        if request.GET.get('amount'):
            initial_data['amount'] = request.GET.get('amount')
        form = PaymentForm(initial=initial_data)

    context = {
        'form': form,
        'error_msg': error_msg,
        'is_edit': False,
        'title': "Enregistrer un Paiement / تسجيل أداء جديد",
    }
    return render(request, 'portal/payment_form.html', context)


@admin_required
def payment_edit_view(request, payment_id):
    lang = getattr(request, 'LANGUAGE_CODE', DEFAULT_LANGUAGE)
    payment = get_object_or_404(Payment.objects.select_related('student', 'invoice'), id=payment_id)
    security_code_expected = getattr(settings, 'ADMIN_FINANCIAL_SECURITY_CODE', '6565')
    error_msg = None

    if request.method == 'POST':
        form = PaymentForm(request.POST, instance=payment)
        entered_code = request.POST.get('security_code', '').strip()
        if entered_code != security_code_expected:
            error_msg = (
                "Code spécial de sécurité incorrect ! Modification non autorisée."
                if lang == 'fr' else
                "الرمز السري المالي الخاص غير صحيح ! لا يمكن تعديل الأداء."
            )
        else:
            if form.is_valid():
                updated_payment = form.save()
                
                # Mise à jour de la facture associée si présente
                if updated_payment.invoice:
                    inv = updated_payment.invoice
                    total_paid = inv.payments.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
                    inv.amount_paid = total_paid
                    if inv.amount_paid >= inv.amount_due:
                        inv.status = 'paid'
                    elif inv.amount_paid > Decimal('0.00'):
                        inv.status = 'partial'
                    else:
                        inv.status = 'unpaid'
                    inv.save()

                msg = (
                    f"✓ Reçu #{updated_payment.receipt_number} modifié avec succès (Code Spécial Validé)."
                    if lang == 'fr' else
                    f"✓ تم تعديل الوصل #{updated_payment.receipt_number} بنجاح (تم تأكيد الرمز السري)."
                )
                messages.success(request, msg)
                return redirect('portal:payments')
    else:
        form = PaymentForm(instance=payment, initial={'security_code': ''})

    context = {
        'form': form,
        'payment': payment,
        'error_msg': error_msg,
        'is_edit': True,
        'title': f"Modifier Reçu #{payment.receipt_number}",
    }
    return render(request, 'portal/payment_form.html', context)


@admin_required
def payment_delete_view(request, payment_id):
    lang = getattr(request, 'LANGUAGE_CODE', DEFAULT_LANGUAGE)
    payment = get_object_or_404(Payment.objects.select_related('student', 'invoice'), id=payment_id)
    security_code_expected = getattr(settings, 'ADMIN_FINANCIAL_SECURITY_CODE', '6565')
    error_msg = None

    if request.method == 'POST':
        entered_code = request.POST.get('security_code', '').strip()
        if entered_code != security_code_expected:
            error_msg = (
                "Code spécial de sécurité incorrect ! Suppression non autorisée."
                if lang == 'fr' else
                "الرمز السري المالي الخاص غير صحيح ! لا يمكن حذف الأداء."
            )
        else:
            invoice = payment.invoice
            rec_no = payment.receipt_number
            payment.delete()

            if invoice:
                total_paid = invoice.payments.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
                invoice.amount_paid = total_paid
                if invoice.amount_paid >= invoice.amount_due:
                    invoice.status = 'paid'
                elif invoice.amount_paid > Decimal('0.00'):
                    invoice.status = 'partial'
                else:
                    invoice.status = 'unpaid'
                invoice.save()

            msg = (
                f"✓ Le paiement #{rec_no} a été supprimé/annulé avec succès."
                if lang == 'fr' else
                f"✓ تم إلغاء وحذف الأداء #{rec_no} بنجاح."
            )
            messages.success(request, msg)
            return redirect('portal:payments')

    context = {
        'payment': payment,
        'error_msg': error_msg,
        'cancel_url': '/payments/',
    }
    return render(request, 'portal/payment_confirm_delete.html', context)


@admin_required
def whatsapp_reminders_view(request):
    lang = getattr(request, 'LANGUAGE_CODE', DEFAULT_LANGUAGE)
    from datetime import date, datetime
    from academy.whatsapp_reminders import get_daily_sessions_reminders, dispatch_daily_whatsapp_reminders
    from core.i18n import FRENCH_DAYS, ARABIC_DAYS

    date_param = request.GET.get('date')
    if date_param:
        try:
            target_date = datetime.strptime(date_param, '%Y-%m-%d').date()
        except ValueError:
            target_date = date.today()
    else:
        target_date = date.today()

    if request.method == 'POST' and request.POST.get('action') == 'dispatch_all':
        res = dispatch_daily_whatsapp_reminders(target_date)
        msg = (
            f"✓ {res['notifications_created']} notification(s) de rappel envoyée(s) aux parents pour le {target_date.strftime('%d/%m/%Y')}."
            if lang == 'fr' else
            f"✓ تم إرسال {res['notifications_created']} تذكير(ات) لأولياء الأمور بنجاح ليوم {target_date.strftime('%d/%m/%Y')}."
        )
        messages.success(request, msg)
        return redirect(f"{request.path}?date={target_date.strftime('%Y-%m-%d')}")

    reminders = get_daily_sessions_reminders(target_date)
    day_name = ARABIC_DAYS.get(target_date.weekday(), '') if lang == 'ar' else FRENCH_DAYS.get(target_date.weekday(), '')

    context = {
        'target_date': target_date,
        'day_name': day_name,
        'reminders': reminders,
        'total_count': len(reminders),
        'is_today': target_date == date.today(),
    }
    return render(request, 'portal/whatsapp_reminders.html', context)



