import os
from decimal import Decimal
from portal.forms import StudentForm, ParentForm, SubjectForm, GroupForm, SessionScheduleForm, PaymentForm, GroupMessageForm
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
    Attendance, Notification, User, ParentVisitLog, GroupMessage
)
from finance.models import Payment, Invoice
from finance.receipt_pdf import generate_receipt_pdf
from finance.reminders import generate_monthly_reminders
from portal.excel_export import export_students_to_excel, export_paid_payments_to_excel, export_unpaid_invoices_to_excel
from portal.planning_pdf import generate_master_planning_pdf
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from portal.decorators import admin_required, trainer_or_admin_required


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


def sync_invoices_with_actual_attendances():
    """
    Garantit une synchronisation 100% automatique et continue entre les présences, conventions et impayés :
    1. Si un élève a au moins une présence 'present' ce mois-ci et n'a pas encore de facture, elle est créée automatiquement
       en appliquant ses réductions de convention ou son statut d'exonération mensuelle.
    2. Si un élève sans aucun paiement n'a plus aucune présence 'present', sa facture impayée est automatiquement retirée
       (sauf si elle a été expressément marquée comme exonérée).
    3. Les paiements orphelins sont automatiquement rattachés.
    """
    import datetime
    from decimal import Decimal
    today = datetime.date.today()
    month = today.month
    year = today.year
    due_date = datetime.date(year, month, 15)

    # 1. Rattachement des paiements orphelins
    for p in Payment.objects.filter(invoice__isnull=True).select_related('student'):
        p.save()

    # 2. Pour les élèves ayant assisté à au moins une séance, créer ou synchroniser la facture
    attended_students = Student.objects.filter(
        active=True,
        attendances__status='present',
        attendances__date__year=year,
        attendances__date__month=month
    ).distinct()

    for st in attended_students:
        is_exempt, ex_reason = st.is_exempt_for_period(month, year)
        base_fee, discount, final_fee = st.calculate_monthly_fee()
        inv = Invoice.objects.filter(student=st, period_month=month, period_year=year).first()
        
        if not inv:
            groups = st.groups.all()
            if groups.exists():
                first_grp = groups.first()
                if is_exempt:
                    Invoice.objects.create(
                        student=st,
                        group=first_grp,
                        period_month=month,
                        period_year=year,
                        original_amount=base_fee,
                        discount_amount=base_fee,
                        amount_due=Decimal('0.00'),
                        amount_paid=Decimal('0.00'),
                        status='exempt',
                        is_exempt=True,
                        exemption_reason=ex_reason or "Exonération accordée",
                        due_date=due_date
                    )
                else:
                    new_inv = Invoice.objects.create(
                        student=st,
                        group=first_grp,
                        period_month=month,
                        period_year=year,
                        original_amount=base_fee,
                        discount_amount=discount,
                        amount_due=final_fee,
                        amount_paid=Decimal('0.00'),
                        status='unpaid',
                        is_exempt=False,
                        exemption_reason='',
                        due_date=due_date
                    )
                    new_inv.update_totals()
        else:
            # Synchroniser si l'élève est devenu exonéré ou a changé de convention
            if is_exempt and not inv.is_exempt and inv.amount_paid == Decimal('0.00'):
                inv.is_exempt = True
                inv.status = 'exempt'
                inv.original_amount = base_fee
                inv.discount_amount = base_fee
                inv.amount_due = Decimal('0.00')
                inv.exemption_reason = ex_reason or "Exonération accordée"
                inv.save()
            elif not is_exempt and inv.is_exempt and inv.amount_paid == Decimal('0.00'):
                inv.is_exempt = False
                inv.original_amount = base_fee
                inv.discount_amount = discount
                inv.amount_due = final_fee
                inv.exemption_reason = ''
                inv.update_totals()
            elif not inv.is_exempt and inv.status == 'unpaid' and inv.amount_paid == Decimal('0.00'):
                if inv.amount_due != final_fee:
                    inv.original_amount = base_fee
                    inv.discount_amount = discount
                    inv.amount_due = final_fee
                    inv.save()

    # 3. Supprimer les factures impayées (sans aucun paiement versé) des élèves n'ayant AUCUNE présence
    for inv in Invoice.objects.filter(status='unpaid', is_exempt=False, period_month=month, period_year=year, amount_paid=Decimal('0.00')):
        has_pres = Attendance.objects.filter(student=inv.student, status='present').exists()
        if not has_pres:
            inv.delete()


def get_billable_unpaid_invoices_qs():
    """
    Retourne uniquement les factures impayées ou partielles des élèves ayant
    effectivement assisté à au moins une séance de cours (status='present').
    Exclut rigoureusement les factures exonérées et les élèves n'ayant pas commencé.
    """
    sync_invoices_with_actual_attendances()
    return Invoice.objects.filter(
        status__in=['unpaid', 'partial'],
        is_exempt=False,
        student__attendances__status='present'
    ).distinct()

@admin_required
def dashboard_view(request):
    lang = getattr(request, 'LANGUAGE_CODE', DEFAULT_LANGUAGE)
    sync_invoices_with_actual_attendances()
    total_students = Student.objects.filter(active=True).count()
    active_groups = Group.objects.count()
    
    # Financial KPIs
    total_revenue = Payment.objects.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    invoices = get_billable_unpaid_invoices_qs()
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
    lang = request.GET.get('lang')
    if not lang:
        if request.user.is_authenticated and getattr(request.user, 'preferred_language', None):
            lang = request.user.preferred_language
        else:
            lang = request.session.get('gca_language') or getattr(request, 'LANGUAGE_CODE', DEFAULT_LANGUAGE)
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
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response


@admin_required
def export_paid_payments_excel_view(request):
    """Export the consolidated payments & unpaid statement to an official Excel workbook."""
    lang = getattr(request, 'LANGUAGE_CODE', DEFAULT_LANGUAGE)
    payments = Payment.objects.select_related('student', 'student__parent', 'invoice', 'invoice__group', 'invoice__group__subject').prefetch_related('student__groups__subject').order_by('-payment_date', '-id')
    unpaid_invoices = get_billable_unpaid_invoices_qs().select_related('student', 'student__parent', 'group', 'group__subject').prefetch_related('student__groups__subject').order_by('-period_year', '-period_month', 'student__last_name_fr')
    excel_data = export_paid_payments_to_excel(payments, unpaid_invoices_queryset=unpaid_invoices, lang=lang)

    filename = f"GCA_Etat_Paiements_Consolide_{lang}.xlsx"
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
    unpaid_invoices = get_billable_unpaid_invoices_qs().select_related('student', 'student__parent', 'group', 'group__subject').order_by('-period_year', '-period_month', 'student__last_name_fr')
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

    # Today dynamic
    today = date.today()
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
    sync_invoices_with_actual_attendances()
    payments = Payment.objects.select_related('student', 'invoice', 'invoice__group').prefetch_related('student__groups__subject').order_by('-payment_date', '-id')
    unpaid_invoices = get_billable_unpaid_invoices_qs().select_related('student', 'group')
    exempted_invoices = Invoice.objects.filter(
        Q(is_exempt=True) | Q(status='exempt')
    ).select_related('student', 'group', 'student__parent').order_by('-period_year', '-period_month', 'student__last_name_fr')
    
    context = {
        'payments': payments,
        'unpaid_invoices': unpaid_invoices,
        'exempted_invoices': exempted_invoices,
    }
    return render(request, 'portal/payments.html', context)


@admin_required
def invoice_exempt_view(request, invoice_id):
    """
    Exonère une facture spécifique pour un élève (Mois offert, Bourse d'excellence, cas social, etc.).
    Enregistre automatiquement l'exonération mensuelle dans PaymentExemption.
    """
    lang = getattr(request, 'LANGUAGE_CODE', DEFAULT_LANGUAGE)
    inv = get_object_or_404(Invoice.objects.select_related('student'), id=invoice_id)
    if request.method == 'POST':
        reason = request.POST.get('reason', '').strip() or "Exonération accordée par la direction"
        from finance.models import PaymentExemption
        PaymentExemption.objects.update_or_create(
            student=inv.student,
            period_month=inv.period_month,
            period_year=inv.period_year,
            defaults={'reason': reason}
        )
        base_fee, discount, _ = inv.student.calculate_monthly_fee()
        inv.is_exempt = True
        inv.status = 'exempt'
        inv.original_amount = base_fee
        inv.discount_amount = base_fee
        inv.amount_due = Decimal('0.00')
        inv.exemption_reason = reason
        inv.save()
        
        msg = (
            f"✓ L'élève {inv.student.get_full_name('fr')} a été exonéré(e) de paiement pour {inv.get_period_label('fr')} (Motif: {reason})."
            if lang == 'fr' else
            f"✓ تم إعفاء التلميذ(ة) {inv.student.get_full_name('ar')} من أداء شهر {inv.get_period_label('ar')} (السبب: {reason})."
        )
        messages.success(request, msg)
    return redirect('portal:payments')


@admin_required
def invoice_unexempt_view(request, invoice_id):
    """
    Annule l'exonération d'une facture et rétablit le montant dû selon les tarifs et conventions applicables.
    """
    lang = getattr(request, 'LANGUAGE_CODE', DEFAULT_LANGUAGE)
    inv = get_object_or_404(Invoice.objects.select_related('student'), id=invoice_id)
    if request.method == 'POST':
        from finance.models import PaymentExemption
        PaymentExemption.objects.filter(
            student=inv.student,
            period_month=inv.period_month,
            period_year=inv.period_year
        ).delete()
        
        base_fee, discount, final_fee = inv.student.calculate_monthly_fee()
        inv.is_exempt = False
        inv.original_amount = base_fee
        inv.discount_amount = discount
        inv.amount_due = final_fee
        inv.exemption_reason = ''
        inv.update_totals()
        
        msg = (
            f"✓ L'exonération a été annulée. La facture de {inv.student.get_full_name('fr')} pour {inv.get_period_label('fr')} a été rétablie ({final_fee} DH)."
            if lang == 'fr' else
            f"✓ تم إلغاء الإعفاء واسترجاع مستحقات التلميذ(ة) {inv.student.get_full_name('ar')} لشهر {inv.get_period_label('ar')} ({final_fee} درهم)."
        )
        messages.success(request, msg)
    return redirect('portal:payments')



def download_receipt_pdf_view(request, payment_id):
    lang = request.GET.get('lang')
    if not lang:
        if request.user.is_authenticated and getattr(request.user, 'preferred_language', None):
            lang = request.user.preferred_language
        else:
            lang = request.session.get('gca_language') or getattr(request, 'LANGUAGE_CODE', DEFAULT_LANGUAGE)
        
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
        if request.user.is_authenticated and getattr(request.user, 'preferred_language', None):
            lang = request.user.preferred_language
        else:
            lang = request.session.get('gca_language') or getattr(request, 'LANGUAGE_CODE', DEFAULT_LANGUAGE)
        
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
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response


@admin_required
def run_reminders_view(request):
    lang = getattr(request, 'LANGUAGE_CODE', DEFAULT_LANGUAGE)
    return redirect('portal:unpaid_reminders')


@admin_required
def unpaid_reminders_console_view(request):
    """
    Console d'autorisation des relances WhatsApp d'impayés :
    Permet à l'administrateur de prévisualiser, sélectionner les parents (cocher/décocher)
    et autoriser l'envoi WhatsApp en respectant l'échéance du 15 du mois max.
    """
    from datetime import date
    from finance.models import Invoice
    from finance.whatsapp_payment_reminders import (
        build_unpaid_reminder_message,
        get_unpaid_reminder_chat_url,
        get_last_reminder_info
    )
    from core.i18n import format_currency

    lang = getattr(request, 'LANGUAGE_CODE', DEFAULT_LANGUAGE)
    today = date.today()

    # Règle du 15 de chaque mois
    current_day = today.day
    if current_day <= 9:
        period_15_status = 'normal'
    elif current_day <= 15:
        period_15_status = 'due_soon'
    else:
        period_15_status = 'overdue'

    try:
        selected_month = int(request.GET.get('month', today.month))
        selected_year = int(request.GET.get('year', today.year))
    except (ValueError, TypeError):
        selected_month = today.month
        selected_year = today.year

    filter_all_periods = request.GET.get('all_periods') == '1'
    q = request.GET.get('q', '').strip()

    qs = get_billable_unpaid_invoices_qs().select_related(
        'student',
        'student__parent',
        'student__parent__user',
        'group',
        'group__subject'
    ).order_by('student__last_name_fr', 'student__first_name_fr')

    if not filter_all_periods:
        qs = qs.filter(period_month=selected_month, period_year=selected_year)

    if q:
        qs = qs.filter(
            Q(student__first_name_fr__icontains=q) |
            Q(student__last_name_fr__icontains=q) |
            Q(student__first_name_ar__icontains=q) |
            Q(student__last_name_ar__icontains=q) |
            Q(student__registration_number__icontains=q) |
            Q(student__parent__full_name_fr__icontains=q) |
            Q(student__parent__full_name_ar__icontains=q)
        )

    invoices_list = []
    total_due_sum = Decimal('0.00')
    unnotified_count = 0
    already_notified_count = 0

    for inv in qs:
        bal = inv.get_balance()
        if bal <= Decimal('0.00'):
            continue
        total_due_sum += bal

        parent = inv.student.parent
        parent_lang = getattr(parent, 'preferred_language', 'fr') or 'fr'
        already_sent, sent_date = get_last_reminder_info(inv)
        if already_sent:
            already_notified_count += 1
        else:
            unnotified_count += 1

        msg_preview = build_unpaid_reminder_message(inv, lang=parent_lang)
        chat_url = get_unpaid_reminder_chat_url(inv, lang=parent_lang)

        invoices_list.append({
            'invoice': inv,
            'balance': bal,
            'balance_formatted': format_currency(bal, lang=lang),
            'parent': parent,
            'parent_lang': parent_lang,
            'phone': parent.phone if parent else '',
            'already_sent': already_sent,
            'sent_date': sent_date,
            'msg_preview': msg_preview,
            'chat_url': chat_url,
        })

    context = {
        'invoices_list': invoices_list,
        'total_due_sum': total_due_sum,
        'total_due_formatted': format_currency(total_due_sum, lang=lang),
        'total_count': len(invoices_list),
        'unnotified_count': unnotified_count,
        'already_notified_count': already_notified_count,
        'selected_month': selected_month,
        'selected_year': selected_year,
        'filter_all_periods': filter_all_periods,
        'q': q,
        'today': today,
        'current_day': current_day,
        'period_15_status': period_15_status,
        'available_years': range(today.year - 1, today.year + 2),
    }
    return render(request, 'portal/unpaid_reminders.html', context)


@admin_required
@require_POST
def unpaid_reminders_send_bulk_view(request):
    """
    Exécute l'envoi groupé des relances WhatsApp autorisées par l'administrateur.
    """
    from finance.whatsapp_payment_reminders import send_bulk_authorized_reminders
    invoice_ids = request.POST.getlist('selected_invoices')
    lang = getattr(request, 'LANGUAGE_CODE', DEFAULT_LANGUAGE)

    if not invoice_ids:
        messages.warning(request, "Veuillez cocher au moins un parent à relancer." if lang == 'fr' else "يرجى تحديد ولي أمر واحد على الأقل لإرسال التذكير.")
        return redirect('portal:unpaid_reminders')

    res = send_bulk_authorized_reminders(invoice_ids)
    sent_cnt = res['sent_count']

    if sent_cnt > 0:
        msg = (
            f"✓ {sent_cnt} relance(s) WhatsApp autorisée(s) et envoyée(s) avec succès !"
            if lang == 'fr' else
            f"✓ تم إرسال {sent_cnt} تذكير عبر واتساب بنجاح بعد الموافقة !"
        )
        messages.success(request, msg)
    else:
        messages.error(request, "Échec de l'envoi des relances. Vérifiez la passerelle WhatsApp." if lang == 'fr' else "فشل إرسال التذكيرات. يرجى التحقق من بوابة واتساب.")

    redirect_url = request.POST.get('next_url', '/payments/unpaid-reminders/')
    return redirect(redirect_url)


@admin_required
@require_POST
def unpaid_reminders_send_single_view(request, invoice_id):
    """
    Envoie la relance WhatsApp autorisée pour une seule facture spécifique.
    """
    from finance.models import Invoice
    from finance.whatsapp_payment_reminders import send_single_unpaid_whatsapp_reminder

    invoice = get_object_or_404(Invoice, id=invoice_id)
    lang = getattr(request, 'LANGUAGE_CODE', DEFAULT_LANGUAGE)

    res = send_single_unpaid_whatsapp_reminder(invoice, force=True)
    if res.get('success'):
        msg = (
            f"✓ Relance WhatsApp envoyée avec succès pour l'élève {invoice.student.get_full_name('fr')} !"
            if lang == 'fr' else
            f"✓ تم إرسال التذكير عبر واتساب بنجاح للتلميذ(ة) {invoice.student.get_full_name('ar')} !"
        )
        messages.success(request, msg)
    else:
        messages.error(request, f"Erreur : {res.get('error')}")

    redirect_url = request.POST.get('next_url', '/payments/unpaid-reminders/')
    return redirect(redirect_url)


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
        'groups__subject', 'groups__level', 'groups__schedules__room', 'groups__messages__author'
    ))

    # Process all children metrics
    for ch in all_children:
        child_schedules = []
        child_groups_info = []
        for g in ch.groups.all():
            for sch in g.schedules.all():
                child_schedules.append({
                    'group': g,
                    'subject': g.subject,
                    'room': sch.room,
                    'schedule': sch,
                    'day_of_week': sch.day_of_week,
                    'day_name_fr': sch.get_day_name('fr'),
                    'day_name_ar': sch.get_day_name('ar'),
                    'start_time': sch.start_time,
                    'end_time': sch.end_time,
                    'trainer_fr': sch.get_trainer_name('fr'),
                    'trainer_ar': sch.get_trainer_name('ar'),
                })
            g_messages = list(g.messages.select_related('author').order_by('-created_at')[:8])
            child_groups_info.append({
                'group': g,
                'subject': g.subject,
                'level': g.level,
                'messages': g_messages,
                'messages_count': len(g_messages),
            })
        child_schedules.sort(key=lambda x: (x['day_of_week'], x['start_time']))
        ch.child_schedules = child_schedules
        ch.child_groups_info = child_groups_info

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


def trainer_space_view(request):
    """
    Espace Formateur dédié :
    - Consultation du planning hebdomadaire de cours
    - Séances du jour avec bouton direct vers la feuille d'appel numérique
    - Liste des groupes et élèves (coordonnées parents pour urgence pédagogique)
    - Strictement aucun accès aux finances, factures ou salaires.
    - Prévisualisation pour les administrateurs avec sélecteur de formateur.
    """
    from datetime import date
    lang = getattr(request, 'LANGUAGE_CODE', DEFAULT_LANGUAGE)

    # 1. Vérification de l'authentification
    if not request.user.is_authenticated:
        return redirect('/login/?next=/trainer/')

    # 2. Vérification des droits (Formateur ou Administrateur)
    is_admin = request.user.is_admin_role() or request.user.is_superuser
    if not (is_admin or request.user.is_trainer_role()):
        msg = get_translation('errors.permission_denied', lang=lang)
        messages.error(request, msg)
        return redirect('portal:parent_space' if request.user.is_parent_role() else 'portal:login')

    # 3. Liste de tous les formateurs enregistrés dans les plannings
    trainers_qs = (
        SessionSchedule.objects.values('trainer_name_fr', 'trainer_name_ar')
        .distinct()
        .order_by('trainer_name_fr')
    )
    all_trainers = list(trainers_qs)

    # Si aucun formateur n'est encore configuré dans le planning
    if not all_trainers:
        all_trainers = [{'trainer_name_fr': 'Formateur GCA', 'trainer_name_ar': 'مدرب الأكاديمية'}]

    selected_trainer = None

    if is_admin:
        trainer_req = request.GET.get('trainer')
        if trainer_req:
            for t in all_trainers:
                if t['trainer_name_fr'] == trainer_req or t['trainer_name_ar'] == trainer_req:
                    selected_trainer = t
                    break
        if not selected_trainer and all_trainers:
            selected_trainer = all_trainers[0]
    else:
        # Formateur connecté : détection intelligente basée sur prénom, nom ou username
        user_fn = (request.user.first_name or '').strip().lower()
        user_ln = (request.user.last_name or '').strip().lower()
        user_un = (request.user.username or '').replace('trainer_', '').replace('coach_', '').strip().lower()

        for t in all_trainers:
            t_fr = t['trainer_name_fr'].lower()
            t_ar = t['trainer_name_ar'].lower()
            if (user_fn and (user_fn in t_fr or user_fn in t_ar)) or \
               (user_ln and (user_ln in t_fr or user_ln in t_ar)) or \
               (user_un and (user_un in t_fr or user_un in t_ar)):
                selected_trainer = t
                break

        if not selected_trainer and all_trainers:
            selected_trainer = all_trainers[0]

    current_trainer_fr = selected_trainer['trainer_name_fr']
    current_trainer_ar = selected_trainer['trainer_name_ar']
    current_trainer_display = current_trainer_ar if lang == 'ar' and current_trainer_ar else current_trainer_fr

    # 4. Séances du formateur
    schedules = (
        SessionSchedule.objects.filter(
            Q(trainer_name_fr=current_trainer_fr) | Q(trainer_name_ar=current_trainer_ar)
        )
        .select_related('group', 'group__subject', 'group__level', 'room')
        .order_by('day_of_week', 'start_time')
    )

    # Attacher day_name pour chaque séance pour l'affichage template sans filtre supplémentaire
    for s in schedules:
        s.day_name = s.get_day_name(lang)

    # 5. Séances du jour
    today = date.today()
    today_weekday = today.weekday()  # 0: Lundi, 6: Dimanche
    today_sessions_info = []

    for s in schedules:
        if s.day_of_week == today_weekday:
            att_qs = Attendance.objects.filter(session=s, date=today)
            total_students_group = s.group.students.filter(active=True).count()
            present_count = att_qs.filter(status='present').count()
            absent_count = att_qs.filter(status='absent').count()
            late_count = att_qs.filter(status='late').count()
            justified_count = att_qs.filter(status='justified').count()
            marked_count = att_qs.count()

            today_sessions_info.append({
                'schedule': s,
                'total_students': total_students_group,
                'marked_count': marked_count,
                'present_count': present_count,
                'absent_count': absent_count,
                'late_count': late_count,
                'justified_count': justified_count,
                'is_completed': marked_count >= total_students_group and total_students_group > 0,
            })

    # 6. Groupes et élèves
    group_ids = schedules.values_list('group_id', flat=True).distinct()
    groups = Group.objects.filter(id__in=group_ids).select_related('subject', 'level')

    students = (
        Student.objects.filter(groups__in=groups, active=True)
        .distinct()
        .prefetch_related('groups')
        .select_related('parent')
        .order_by('last_name_fr', 'first_name_fr')
    )

    # 7. Données pour chaque groupe (avec ses élèves rattachés)
    groups_data = []
    for g in groups:
        g_students = [st for st in students if g in st.groups.all()]
        groups_data.append({
            'group': g,
            'students': g_students,
            'students_count': len(g_students),
        })

    # Notifications pour le formateur
    trainer_notifications = Notification.objects.filter(
        recipient=request.user
    ).order_by('-created_at')[:5]

    context = {
        'all_trainers': all_trainers,
        'selected_trainer': selected_trainer,
        'current_trainer_fr': current_trainer_fr,
        'current_trainer_ar': current_trainer_ar,
        'current_trainer_display': current_trainer_display,
        'schedules': schedules,
        'today_sessions_info': today_sessions_info,
        'today_date': today,
        'today_weekday': today_weekday,
        'groups_data': groups_data,
        'total_sessions_week': schedules.count(),
        'total_sessions_today': len(today_sessions_info),
        'total_students': students.count(),
        'total_groups': groups.count(),
        'notifications': trainer_notifications,
        'is_admin': is_admin,
    }
    return render(request, 'portal/trainer_space.html', context)



def login_view(request):
    import re
    lang = getattr(request, 'LANGUAGE_CODE', DEFAULT_LANGUAGE)
    next_url = request.GET.get('next') or request.POST.get('next') or '/'

    if request.user.is_authenticated:
        if request.user.is_parent_role():
            return redirect('portal:parent_space')
        elif request.user.is_trainer_role():
            return redirect('portal:trainer_space')
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
            phone_queries = Q(phone__icontains=raw_identifier)
            if cleaned_phone:
                phone_queries |= Q(phone__icontains=cleaned_phone)
                if cleaned_phone.startswith('0'):
                    phone_queries |= Q(phone__icontains=cleaned_phone[1:])
                    phone_queries |= Q(phone__icontains='212' + cleaned_phone[1:])
                elif cleaned_phone.startswith('212'):
                    phone_queries |= Q(phone__icontains=cleaned_phone[3:])
            parent_contact = Parent.objects.filter(
                phone_queries |
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
            elif user.is_trainer_role():
                return redirect('portal:trainer_space')
            return redirect(next_url if next_url != '/login/' else '/')
        else:
            error_msg = get_translation('auth.invalid_credentials', lang=lang)

    context = {
        'error_msg': error_msg,
        'next_url': next_url,
        'entered_username': entered_username,
    }
    response = render(request, 'portal/login.html', context)
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response

def logout_view(request):
    lang = getattr(request, 'LANGUAGE_CODE', DEFAULT_LANGUAGE)
    auth_logout(request)
    try:
        request.session.flush()
    except Exception:
        pass
    msg = get_translation('auth.logged_out', lang=lang)
    messages.info(request, msg)
    response = redirect('portal:login')
    session_cookie_name = getattr(settings, 'SESSION_COOKIE_NAME', 'sessionid')
    response.delete_cookie(session_cookie_name, path='/')
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response


def csrf_failure_view(request, reason=""):
    """Graceful bilingual error page for expired CSRF tokens."""
    return render(request, 'portal/csrf_failure.html', status=403)


# ==========================================
# 1. ÉLÈVES CRUD (MULTI-ACTIVITÉS)
# ==========================================

@admin_required
def check_duplicate_student_ajax_view(request):
    """
    Contrôle automatique et instantané des risques de double inscription d'un élève (AJAX) :
    Vérifie en temps réel lors de la saisie si un élève existe déjà avec le même nom/prénom
    (français ou arabe), même parent, même date de naissance ou même matricule.
    Renvoie les données complètes pour l'affichage de l'infobulle interactive anti-doublon.
    """
    from datetime import datetime
    from django.urls import reverse

    lang = getattr(request, 'LANGUAGE_CODE', DEFAULT_LANGUAGE)
    fn_fr = (request.GET.get('first_name_fr') or '').strip()
    ln_fr = (request.GET.get('last_name_fr') or '').strip()
    fn_ar = (request.GET.get('first_name_ar') or '').strip()
    ln_ar = (request.GET.get('last_name_ar') or '').strip()
    bdate_str = (request.GET.get('birth_date') or '').strip()
    parent_id = (request.GET.get('parent') or '').strip()
    reg_num = (request.GET.get('registration_number') or '').strip()
    student_id = (request.GET.get('student_id') or '').strip()

    # Si rien de suffisant n'est saisi, retourner immédiatement
    has_fr = len(fn_fr) >= 2 and len(ln_fr) >= 2
    has_ar = len(fn_ar) >= 2 and len(ln_ar) >= 2
    has_reg = len(reg_num) >= 4

    if not has_fr and not has_ar and not has_reg:
        return JsonResponse({'is_duplicate': False, 'existing_students': []})

    qs = Student.objects.all().select_related('parent').prefetch_related('groups')
    if student_id and str(student_id).isdigit():
        qs = qs.exclude(id=int(student_id))

    target_bdate = None
    if bdate_str:
        try:
            target_bdate = datetime.strptime(bdate_str, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            pass

    target_parent_id = int(parent_id) if parent_id and str(parent_id).isdigit() else None

    exact_students = []
    similar_students = []

    # 1. Vérification par matricule
    if has_reg:
        reg_matches = qs.filter(registration_number__iexact=reg_num)
        for rm in reg_matches:
            exact_students.append(rm)

    # 2. Recherche par nom/prénom
    q_filter = Q()
    if has_fr:
        q_filter |= (Q(first_name_fr__iexact=fn_fr) & Q(last_name_fr__iexact=ln_fr))
    if has_ar:
        q_filter |= (Q(first_name_ar__iexact=fn_ar) & Q(last_name_ar__iexact=ln_ar))

    if q_filter:
        matches = list(qs.filter(q_filter).exclude(id__in=[s.id for s in exact_students])[:10])
        for st in matches:
            is_exact = False
            if target_parent_id and st.parent_id == target_parent_id:
                is_exact = True
            elif target_bdate and st.birth_date and st.birth_date == target_bdate:
                is_exact = True

            if is_exact:
                exact_students.append(st)
            else:
                similar_students.append(st)

    all_found = exact_students + similar_students
    if not all_found:
        return JsonResponse({'is_duplicate': False, 'existing_students': []})

    match_type = 'exact' if exact_students else 'similar'
    first_match = all_found[0]

    existing_students = []
    for s in all_found[:5]:
        groups_list = [g.get_name(lang) for g in s.groups.all()]
        existing_students.append({
            'id': s.id,
            'registration_number': s.registration_number,
            'full_name_fr': f"{s.first_name_fr} {s.last_name_fr}".strip(),
            'full_name_ar': f"{s.first_name_ar} {s.last_name_ar}".strip(),
            'birth_date': s.birth_date.strftime('%d/%m/%Y') if s.birth_date else '',
            'parent_name': s.parent.get_name(lang) if s.parent else '',
            'parent_phone': s.parent.phone if s.parent else '',
            'groups': groups_list,
            'active': s.active,
            'edit_url': reverse('portal:student_edit', args=[s.id]),
            'is_exact': s in exact_students,
        })

    if match_type == 'exact':
        status_badge_fr = "Doublon Détecté (Élève déjà inscrit)"
        status_badge_ar = "تلميذ مسجل مسبقاً (احتمال تكرار التسجيل)"
        warning_title_fr = "🛑 Attention : Cet élève est déjà inscrit !"
        warning_title_ar = "🛑 تنبيه : هذا التلميذ مسجل بالفعل مسبقاً !"
        parent_name = first_match.parent.get_name('fr') if first_match.parent else "Parent"
        warning_msg_fr = (
            f"Un élève avec la même identité ({first_match.get_bilingual_full_name()}) est DÉJÀ inscrit "
            f"sous le matricule [{first_match.registration_number}] (Parent : {parent_name}). "
            "Pour éviter de créer une double inscription inutile, vous pouvez ouvrir et modifier directement sa fiche existante."
        )
        parent_name_ar = first_match.parent.get_name('ar') if first_match.parent else "ولي الأمر"
        warning_msg_ar = (
            f"تلميذ بنفس البيانات ({first_match.get_bilingual_full_name()}) مسجل بالفعل "
            f"برقم التسجيل [{first_match.registration_number}] (ولي الأمر : {parent_name_ar}). "
            "لتفادي تكرار التسجيل بدون قصد، يمكنك فتح وتعديل ملفه الحالي مباشرة."
        )
    else:
        status_badge_fr = f"Homonyme Détecté ({len(similar_students)} élève(s))"
        status_badge_ar = f"تشابه في الأسماء ({len(similar_students)} تلميذ)"
        warning_title_fr = "⚠️ Information : Homonyme(s) existant(s)"
        warning_title_ar = "⚠️ معلومة : تم العثور على تلميذ بنفس الاسم"
        warning_msg_fr = (
            f"Il existe déjà un ou plusieurs élèves portant le nom '{first_match.get_bilingual_full_name()}' au sein de l'académie. "
            "Veuillez vérifier les fiches existantes ci-dessous pour confirmer s'il s'agit d'un doublon ou d'un homonyme distinct."
        )
        warning_msg_ar = (
            f"يوجد تلميذ أو أكثر بنفس الاسم '{first_match.get_bilingual_full_name()}' في الأكاديمية. "
            "يرجى مراجعة الملفات أدناه للتأكد مما إذا كان نفس التلميذ أو حالة تشابه أسماء."
        )

    return JsonResponse({
        'is_duplicate': True,
        'match_type': match_type,
        'warning_title_fr': warning_title_fr,
        'warning_title_ar': warning_title_ar,
        'status_badge_fr': status_badge_fr,
        'status_badge_ar': status_badge_ar,
        'warning_msg_fr': warning_msg_fr,
        'warning_msg_ar': warning_msg_ar,
        'existing_students': existing_students,
    })


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


@admin_required
def group_messages_view(request, group_id):
    """
    Espace Messages et Annonces d'un Groupe (selon l'activité et le niveau) :
    Permet à l'administrateur de consulter l'historique et de rédiger des messages
    diffusés aux parents d'élèves de ce groupe.
    """
    lang = getattr(request, 'LANGUAGE_CODE', DEFAULT_LANGUAGE)
    group = get_object_or_404(
        Group.objects.select_related('subject', 'level').prefetch_related('students__parent__user'),
        id=group_id
    )

    if request.method == 'POST':
        form = GroupMessageForm(request.POST)
        if form.is_valid():
            msg_obj = form.save(commit=False)
            msg_obj.group = group
            msg_obj.author = request.user
            msg_obj.save()

            notify_parents = form.cleaned_data.get('notify_parents', False)
            if notify_parents:
                parent_users = set()
                for st in group.students.filter(active=True):
                    if st.parent and st.parent.user:
                        parent_users.add(st.parent.user)

                type_label = dict(GroupMessage.MESSAGE_TYPES).get(msg_obj.message_type, 'Annonce')
                for p_user in parent_users:
                    Notification.objects.create(
                        recipient=p_user,
                        title_fr=f"[{group.name_fr}] {msg_obj.title or type_label}",
                        title_ar=f"[{group.name_ar}] {msg_obj.title or type_label}",
                        message_fr=msg_obj.content,
                        message_ar=msg_obj.content,
                        notification_type=msg_obj.message_type
                    )

            messages.success(
                request,
                f"✓ Message publié avec succès dans le groupe « {group.name_fr} »."
                if lang == 'fr' else
                f"✓ تم نشر الإعلان بنجاح في مجموعة « {group.name_ar} »."
            )
            return redirect('portal:group_messages', group_id=group.id)
    else:
        form = GroupMessageForm()

    group_messages = group.messages.select_related('author').order_by('-created_at')
    enrolled_students = group.students.filter(active=True).select_related('parent').order_by('last_name_fr', 'first_name_fr')

    context = {
        'group': group,
        'form': form,
        'group_messages': group_messages,
        'enrolled_students': enrolled_students,
        'students_count': enrolled_students.count(),
    }
    return render(request, 'portal/group_messages.html', context)


@admin_required
@require_POST
def group_message_delete_view(request, group_id, message_id):
    """
    Supprime une annonce / un message d'un groupe.
    """
    lang = getattr(request, 'LANGUAGE_CODE', DEFAULT_LANGUAGE)
    group = get_object_or_404(Group, id=group_id)
    msg_obj = get_object_or_404(GroupMessage, id=message_id, group=group)
    msg_obj.delete()

    messages.info(
        request,
        "✓ Message supprimé avec succès." if lang == 'fr' else "✓ تم حذف الرسالة بنجاح."
    )
    return redirect('portal:group_messages', group_id=group.id)



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
        clean_phone_digits = re.sub(r'[^0-9]', '', parent_phone)
        if not parent_name_fr or not parent_name_ar or not parent_phone:
            error_msg = (
                "Veuillez renseigner le nom complet du tuteur (FR et AR) ainsi que le numéro de téléphone."
                if lang == 'fr' else
                "يرجى ملء الاسم الكامل لولي الأمر (بالعربية والفرنسية) ورقم الهاتف الإلزامي."
            )
        elif len(clean_phone_digits) < 9:
            error_msg = (
                "Le numéro de téléphone WhatsApp doit comporter au moins 9 à 10 chiffres valides (ex: 06 61 23 45 67)."
                if lang == 'fr' else
                "يرجى إدخال رقم هاتف واتساب صحيح مكون من 9 إلى 10 أرقام على الأقل (مثال: 0661112233)."
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

                    # Contrôle anti-doublon d'inscription pour l'enfant
                    existing_st = Student.objects.filter(
                        parent=parent,
                        first_name_fr__iexact=first_name_fr,
                        last_name_fr__iexact=last_name_fr
                    ).first()
                    if not existing_st and bdate:
                        existing_st = Student.objects.filter(
                            parent=parent,
                            birth_date=bdate
                        ).filter(
                            Q(first_name_fr__iexact=first_name_fr) | Q(first_name_ar__iexact=first_name_ar)
                        ).first()

                    if existing_st:
                        # Élève déjà inscrit : mise à jour des informations si nécessaire (pas de doublon)
                        updated = False
                        if ch.get('school') and not existing_st.school:
                            existing_st.school = ch['school']
                            updated = True
                        if ch.get('grade_level') and not existing_st.grade_level:
                            existing_st.grade_level = ch['grade_level']
                            updated = True
                        if updated:
                            existing_st.save()
                        created_students.append(existing_st)
                    else:
                        count = Student.objects.count() + 1
                        reg = f"GCA-2026-{count:03d}"
                        while Student.objects.filter(registration_number=reg).exists():
                            count += 1
                            reg = f"GCA-2026-{count:03d}"

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
def check_duplicate_payment_ajax_view(request):
    """
    Contrôle automatique et instantané des risques de paiements doublons (AJAX) :
    Vérifie en temps réel lors de la saisie si l'élève a déjà un versement pour la même période,
    ou si la facture est déjà entièrement réglée, ou s'il est exonéré de paiement.
    Renvoie les données complètes pour l'affichage de l'infobulle interactive.
    """
    from datetime import datetime, date
    from django.http import JsonResponse
    from core.i18n import FRENCH_MONTHS, ARABIC_MONTHS

    lang = getattr(request, 'LANGUAGE_CODE', DEFAULT_LANGUAGE)
    student_id = request.GET.get('student')
    invoice_id = request.GET.get('invoice')
    date_str = request.GET.get('date')

    if not student_id or not str(student_id).isdigit():
        return JsonResponse({'is_duplicate_risk': False, 'existing_payments': []})

    student = Student.objects.filter(id=int(student_id)).first()
    if not student:
        return JsonResponse({'is_duplicate_risk': False, 'existing_payments': []})

    target_date = date.today()
    if date_str:
        try:
            target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            pass

    target_month = target_date.month
    target_year = target_date.year

    # 1. Vérifier si l'élève est officiellement exonéré pour ce mois
    is_exempt, ex_reason = student.is_exempt_for_period(target_month, target_year)

    # 2. Chercher les paiements existants pour ce même mois / facture
    payments_qs = Payment.objects.filter(student=student).select_related('invoice')

    if invoice_id and str(invoice_id).isdigit():
        inv = Invoice.objects.filter(id=int(invoice_id)).first()
        if inv:
            target_month = inv.period_month
            target_year = inv.period_year
            month_payments = payments_qs.filter(
                Q(invoice=inv) |
                Q(invoice__period_month=target_month, invoice__period_year=target_year) |
                Q(payment_date__year=target_year, payment_date__month=target_month)
            ).distinct()
        else:
            month_payments = payments_qs.filter(
                Q(invoice__period_month=target_month, invoice__period_year=target_year) |
                Q(payment_date__year=target_year, payment_date__month=target_month)
            ).distinct()
    else:
        month_payments = payments_qs.filter(
            Q(invoice__period_month=target_month, invoice__period_year=target_year) |
            Q(payment_date__year=target_year, payment_date__month=target_month)
        ).distinct()

    existing_payments = []
    total_already_paid = Decimal('0.00')

    for p in month_payments.order_by('-payment_date', '-id'):
        total_already_paid += p.amount
        existing_payments.append({
            'id': p.id,
            'receipt_number': p.receipt_number,
            'amount': f"{p.amount:.2f}",
            'payment_date': p.payment_date.strftime('%d/%m/%Y'),
            'payment_method': p.get_method_label(lang),
            'invoice_status': p.invoice.get_status_label(lang) if p.invoice else None,
        })

    month_name_fr = FRENCH_MONTHS.get(target_month, str(target_month)).capitalize()
    month_name_ar = ARABIC_MONTHS.get(target_month, str(target_month))
    period_label_fr = f"{month_name_fr} {target_year}"
    period_label_ar = f"{month_name_ar} {target_year}"

    # Récupérer la facture pour comparer le montant dû
    inv = Invoice.objects.filter(student=student, period_month=target_month, period_year=target_year).first()
    base_fee, discount, final_fee = student.calculate_monthly_fee()
    amount_due = inv.amount_due if inv else final_fee
    balance = max(Decimal('0.00'), amount_due - total_already_paid)

    is_duplicate_risk = (len(existing_payments) > 0) or is_exempt

    # Construction des libellés bilingues
    warning_title_fr = "⚠️ Attention : Risque de Paiement Doublé !"
    warning_title_ar = "⚠️ تنبيه : احتمال تكرار الأداء !"

    if is_exempt:
        status_badge_fr = "Élève Exonéré (0 DH)"
        status_badge_ar = "تلميذ معفى (0 درهم)"
        warning_msg_fr = f"L'élève {student.get_full_name('fr')} est officiellement exonéré(e) de paiement pour {period_label_fr} (Motif : {ex_reason or 'Exonération accordée'}). Aucun montant n'est dû."
        warning_msg_ar = f"التلميذ(ة) {student.get_full_name('ar')} معفى رسمياً من الأداء لشهر {period_label_ar} (السبب : {ex_reason or 'إعفاء رسمي'}). لا يوجد أي مبلغ مستحق."
    elif existing_payments:
        last_pay = existing_payments[0]
        if balance == Decimal('0.00'):
            status_badge_fr = "Cotisation Déjà Réglée à 100%"
            status_badge_ar = "المستحقات مؤداة بالكامل 100%"
            warning_msg_fr = f"Attention : Cet élève a DÉJÀ réglé la totalité de sa cotisation pour {period_label_fr} ({total_already_paid:.2f} DH versés via le reçu #{last_pay['receipt_number']} le {last_pay['payment_date']}). Risque de double encaissement !"
            warning_msg_ar = f"تنبيه : هذا التلميذ أدى بالفعل كامل مستحقات شهر {period_label_ar} ({total_already_paid:.2f} درهم عبر الوصل #{last_pay['receipt_number']} بتاريخ {last_pay['payment_date']}). احتمال تكرار القبض !"
        else:
            status_badge_fr = f"Paiement Partiel Existant (Reste : {balance:.2f} DH)"
            status_badge_ar = f"أداء جزئي سابق (المتبقي : {balance:.2f} درهم)"
            warning_msg_fr = f"Cet élève a déjà un versement partiel enregistré pour {period_label_fr} ({total_already_paid:.2f} DH déjà versés via le reçu #{last_pay['receipt_number']}). Le reliquat restant dû est de {balance:.2f} DH."
            warning_msg_ar = f"هذا التلميذ لديه بالفعل دفعة مسجلة لشهر {period_label_ar} (تم دفع {total_already_paid:.2f} درهم عبر الوصل #{last_pay['receipt_number']}). المبلغ المتبقي المستحق هو {balance:.2f} درهم."
    else:
        status_badge_fr = ""
        status_badge_ar = ""
        warning_msg_fr = ""
        warning_msg_ar = ""

    return JsonResponse({
        'is_duplicate_risk': is_duplicate_risk,
        'is_exempt': is_exempt,
        'exemption_reason': ex_reason if is_exempt else '',
        'period_label_fr': period_label_fr,
        'period_label_ar': period_label_ar,
        'total_already_paid': f"{total_already_paid:.2f}",
        'amount_due': f"{amount_due:.2f}",
        'balance_remaining': f"{balance:.2f}",
        'existing_payments': existing_payments,
        'warning_title_fr': warning_title_fr,
        'warning_title_ar': warning_title_ar,
        'status_badge_fr': status_badge_fr,
        'status_badge_ar': status_badge_ar,
        'warning_msg_fr': warning_msg_fr,
        'warning_msg_ar': warning_msg_ar,
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
                is_exemption = form.cleaned_data.get('is_exemption')
                ex_reason = form.cleaned_data.get('exemption_reason', '').strip() or "Exonération accordée"
                apply_discount = form.cleaned_data.get('apply_discount')
                disc_amount = form.cleaned_data.get('discount_amount') or Decimal('0.00')
                conv_name = form.cleaned_data.get('convention_name', '').strip()

                if is_exemption:
                    from finance.models import PaymentExemption
                    inv = p.invoice or Invoice.objects.filter(student=p.student, status__in=['unpaid', 'partial']).first()
                    month = inv.period_month if inv else p.payment_date.month
                    year = inv.period_year if inv else p.payment_date.year

                    PaymentExemption.objects.update_or_create(
                        student=p.student,
                        period_month=month,
                        period_year=year,
                        defaults={'reason': ex_reason}
                    )

                    base_fee, _, _ = p.student.calculate_monthly_fee()
                    if inv:
                        inv.is_exempt = True
                        inv.status = 'exempt'
                        inv.original_amount = base_fee
                        inv.discount_amount = base_fee
                        inv.amount_due = Decimal('0.00')
                        inv.exemption_reason = ex_reason
                        inv.save()

                    msg = (
                        f"✓ L'élève {p.student.get_full_name('fr')} a été enregistré(e) comme exonéré(e) de paiement pour {month}/{year} (0 DH dû)."
                        if lang == 'fr' else
                        f"✓ تم إعفاء التلميذ(ة) {p.student.get_full_name('ar')} من أداء شهر {month}/{year} (0 درهم مستحق)."
                    )
                    messages.success(request, msg)
                    return redirect('portal:payments')

                # Si une réduction manuelle / convention a été demandée sur ce paiement
                if apply_discount and disc_amount > Decimal('0.00'):
                    inv = p.invoice or Invoice.objects.filter(student=p.student, status__in=['unpaid', 'partial']).first()
                    if inv:
                        inv.discount_amount = disc_amount
                        inv.amount_due = max(Decimal('0.00'), inv.original_amount - disc_amount)
                        inv.save()
                        p.invoice = inv
                    if conv_name and not p.student.has_convention:
                        p.student.has_convention = True
                        p.student.convention_name = conv_name
                        p.student.discount_type = 'fixed_discount'
                        p.student.discount_value = disc_amount
                        p.student.save()

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
        st_id = request.GET.get('student')
        if st_id:
            initial_data['student'] = st_id
            try:
                st_obj = Student.objects.get(id=st_id)
                if st_obj.has_convention:
                    base_fee, discount, final_fee = st_obj.calculate_monthly_fee()
                    initial_data['apply_discount'] = True
                    initial_data['convention_name'] = st_obj.convention_name
                    initial_data['discount_amount'] = discount
                    if not request.GET.get('amount'):
                        initial_data['amount'] = final_fee
            except (Student.DoesNotExist, ValueError):
                pass

        if request.GET.get('invoice'):
            initial_data['invoice'] = request.GET.get('invoice')
        if request.GET.get('amount') and 'amount' not in initial_data:
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
    from academy.whatsapp_reminders import (
        get_daily_sessions_reminders, dispatch_daily_whatsapp_reminders,
        is_day_cancelled, is_schedule_cancelled, cancel_day, restore_day,
        cancel_schedule, restore_schedule, send_whatsapp_via_gateway
    )
    from academy.models import SessionSchedule
    from core.i18n import FRENCH_DAYS, ARABIC_DAYS

    date_param = request.GET.get('date')
    if date_param:
        try:
            target_date = datetime.strptime(date_param, '%Y-%m-%d').date()
        except ValueError:
            target_date = date.today()
    else:
        target_date = date.today()

    has_gateway = bool(getattr(settings, 'WHATSAPP_GATEWAY_URL', '') or getattr(settings, 'WHATSAPP_TOKEN', ''))

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'dispatch_all':
            res = dispatch_daily_whatsapp_reminders(target_date)
            if res.get('day_cancelled'):
                messages.warning(
                    request,
                    "⚠️ Cette journée a été marquée comme annulée. Aucun rappel n'a été envoyé."
                    if lang == 'fr' else
                    "⚠️ تم تحديد هذا اليوم كملغى. لم يتم إرسال أي تذكيرات."
                )
            elif res.get('whatsapp_sent_via_api', 0) > 0:
                msg = (
                    f"✓ {res['whatsapp_sent_via_api']} message(s) WhatsApp envoyé(s) directement via l'API pour le {target_date.strftime('%d/%m/%Y')}."
                    if lang == 'fr' else
                    f"✓ تم إرسال {res['whatsapp_sent_via_api']} رسالة واتساب بنجاح عبر بوابة API ليوم {target_date.strftime('%d/%m/%Y')}."
                )
                messages.success(request, msg)
            else:
                msg = (
                    f"✓ {res['notifications_created']} notification(s) de rappel enregistrée(s) pour le {target_date.strftime('%d/%m/%Y')}."
                    if lang == 'fr' else
                    f"✓ تم تسجيل {res['notifications_created']} إشعار تذكير بنجاح ليوم {target_date.strftime('%d/%m/%Y')}."
                )
                messages.success(request, msg)
            return redirect(f"{request.path}?date={target_date.strftime('%Y-%m-%d')}")

        elif action == 'cancel_day':
            cancel_day(target_date)
            messages.warning(
                request,
                f"⛔ Toutes les séances du {target_date.strftime('%d/%m/%Y')} sont désormais ANNULÉES. Aucun rappel automatique ne partira ce jour-là."
                if lang == 'fr' else
                f"⛔ تم إلغاء جميع حصص يوم {target_date.strftime('%d/%m/%Y')}. لن يتم إرسال أي تذكير تلقائي في هذا اليوم."
            )
            return redirect(f"{request.path}?date={target_date.strftime('%Y-%m-%d')}")

        elif action == 'restore_day':
            restore_day(target_date)
            messages.success(
                request,
                f"✅ La journée du {target_date.strftime('%d/%m/%Y')} est RÉACTIVÉE. Les rappels partiront normalement à 13h00."
                if lang == 'fr' else
                f"✅ تم إعادة تفعيل يوم {target_date.strftime('%d/%m/%Y')}. سيتم إرسال التذكيرات بشكل طبيعي في الساعة 13:00."
            )
            return redirect(f"{request.path}?date={target_date.strftime('%Y-%m-%d')}")

        elif action == 'cancel_schedule':
            sch_id = request.POST.get('schedule_id')
            if sch_id:
                try:
                    sch = SessionSchedule.objects.get(id=sch_id)
                    cancel_schedule(sch, target_date)
                    messages.warning(
                        request,
                        f"⛔ La séance « {sch.group.name_fr} » ({sch.start_time.strftime('%H:%M')}) est ANNULÉE pour le {target_date.strftime('%d/%m/%Y')}."
                        if lang == 'fr' else
                        f"⛔ تم إلغاء حصة « {sch.group.name_ar} » ليوم {target_date.strftime('%d/%m/%Y')}."
                    )
                except SessionSchedule.DoesNotExist:
                    pass
            return redirect(f"{request.path}?date={target_date.strftime('%Y-%m-%d')}")

        elif action == 'restore_schedule':
            sch_id = request.POST.get('schedule_id')
            if sch_id:
                try:
                    sch = SessionSchedule.objects.get(id=sch_id)
                    restore_schedule(sch, target_date)
                    messages.success(
                        request,
                        f"✅ La séance « {sch.group.name_fr} » est RÉTABLIE pour le {target_date.strftime('%d/%m/%Y')}."
                        if lang == 'fr' else
                        f"✅ تمت استعادة حصة « {sch.group.name_ar} » ليوم {target_date.strftime('%d/%m/%Y')}."
                    )
                except SessionSchedule.DoesNotExist:
                    pass
            return redirect(f"{request.path}?date={target_date.strftime('%Y-%m-%d')}")

        elif action == 'notify_cancellation_all':
            # Send cancellation notification to all parents of cancelled sessions for this day via Gateway
            reminders = get_daily_sessions_reminders(target_date)
            cancelled_items = [r for r in reminders if r.get('is_cancelled')]
            sent_count = 0
            for item in cancelled_items:
                res = send_whatsapp_via_gateway(item['whatsapp_phone'], item['cancellation_text'])
                if res.get('success'):
                    sent_count += 1
            messages.info(
                request,
                f"📢 Avis d'annulation WhatsApp expédié à {sent_count} parent(s)."
                if lang == 'fr' else
                f"📢 تم إرسال إشعار الإلغاء عبر واتساب إلى {sent_count} من أولياء الأمور."
            )
            return redirect(f"{request.path}?date={target_date.strftime('%Y-%m-%d')}")

    reminders = get_daily_sessions_reminders(target_date)
    day_name = ARABIC_DAYS.get(target_date.weekday(), '') if lang == 'ar' else FRENCH_DAYS.get(target_date.weekday(), '')
    day_cancelled = is_day_cancelled(target_date)

    context = {
        'target_date': target_date,
        'day_name': day_name,
        'reminders': reminders,
        'total_count': len(reminders),
        'active_count': len([r for r in reminders if not r.get('is_cancelled')]),
        'cancelled_count': len([r for r in reminders if r.get('is_cancelled')]),
        'is_today': target_date == date.today(),
        'has_gateway': has_gateway,
        'day_cancelled': day_cancelled,
    }
    return render(request, 'portal/whatsapp_reminders.html', context)


# ==============================================================================
# GESTION INTELLIGENTE DES PRÉSENCES & BADGES QR CODE
# ==============================================================================

@admin_required
def attendance_list_view(request):
    """
    Vue principale de gestion des présences : liste des séances du jour sélectionné
    avec indicateurs d'émargement et accès à la feuille d'appel interactive.
    """
    from datetime import date, datetime
    from academy.whatsapp_reminders import is_day_cancelled, is_schedule_cancelled
    from core.i18n import FRENCH_DAYS, ARABIC_DAYS

    lang = getattr(request, 'LANGUAGE_CODE', DEFAULT_LANGUAGE)
    date_param = request.GET.get('date')
    if date_param:
        try:
            target_date = datetime.strptime(date_param, '%Y-%m-%d').date()
        except ValueError:
            target_date = date.today()
    else:
        target_date = date.today()

    day_of_week = target_date.weekday()
    schedules = SessionSchedule.objects.filter(day_of_week=day_of_week).select_related(
        'group', 'group__subject', 'room'
    ).order_by('start_time')

    day_cancelled = is_day_cancelled(target_date)
    sessions_data = []

    for sch in schedules:
        total_enrolled = sch.group.students.filter(active=True).count()
        attendances = Attendance.objects.filter(session=sch, date=target_date)
        present_count = attendances.filter(status='present').count()
        absent_count = attendances.filter(status='absent').count()
        late_count = attendances.filter(status='late').count()
        justified_count = attendances.filter(status='justified').count()
        total_marked = attendances.count()

        sch_cancelled = day_cancelled or is_schedule_cancelled(sch, target_date)

        sessions_data.append({
            'schedule': sch,
            'total_enrolled': total_enrolled,
            'present_count': present_count,
            'absent_count': absent_count,
            'late_count': late_count,
            'justified_count': justified_count,
            'total_marked': total_marked,
            'is_completed': total_enrolled > 0 and total_marked >= total_enrolled,
            'is_cancelled': sch_cancelled,
        })

    day_name = ARABIC_DAYS.get(target_date.weekday(), '') if lang == 'ar' else FRENCH_DAYS.get(target_date.weekday(), '')

    context = {
        'target_date': target_date,
        'day_name': day_name,
        'is_today': target_date == date.today(),
        'sessions_data': sessions_data,
        'day_cancelled': day_cancelled,
        'groups': Group.objects.select_related('subject').all(),
    }
    return render(request, 'portal/attendance_list.html', context)


@trainer_or_admin_required
def attendance_sheet_view(request, session_id):
    """
    Feuille d'appel numérique pour une séance et date précises :
    supporte le scan caméra QR Code et le pointage / correction manuelle par clic.
    """
    from datetime import date, datetime
    from academy.whatsapp_reminders import is_day_cancelled, is_schedule_cancelled
    from core.i18n import FRENCH_DAYS, ARABIC_DAYS

    lang = getattr(request, 'LANGUAGE_CODE', DEFAULT_LANGUAGE)
    schedule = get_object_or_404(
        SessionSchedule.objects.select_related('group', 'group__subject', 'room'),
        id=session_id
    )

    date_param = request.GET.get('date')
    if date_param:
        try:
            target_date = datetime.strptime(date_param, '%Y-%m-%d').date()
        except ValueError:
            target_date = date.today()
    else:
        target_date = date.today()

    students = schedule.group.students.filter(active=True).select_related('parent', 'parent__user').order_by('last_name_fr', 'first_name_fr')

    # Traitement POST d'actions en masse (Tout marquer présent / Réinitialiser)
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'mark_all_present':
            for st in students:
                Attendance.objects.update_or_create(
                    student=st, session=schedule, date=target_date,
                    defaults={'status': 'present'}
                )
            messages.success(
                request,
                "✓ Tous les élèves de la séance ont été marqués Présents."
                if lang == 'fr' else
                "✓ تم تسجيل جميع تلاميذ الحصة كحاضرين بنجاح."
            )
            return redirect(f"{request.path}?date={target_date.strftime('%Y-%m-%d')}")
        elif action == 'reset_all':
            Attendance.objects.filter(session=schedule, date=target_date).delete()
            messages.info(
                request,
                "✓ La feuille de présence a été réinitialisée."
                if lang == 'fr' else
                "✓ تمت إعادة ضبط ورقة الحضور."
            )
            return redirect(f"{request.path}?date={target_date.strftime('%Y-%m-%d')}")

    # Récupérer les statuts existants
    att_map = {
        att.student_id: att
        for att in Attendance.objects.filter(session=schedule, date=target_date)
    }

    from academy.whatsapp_absence import get_whatsapp_absence_chat_url

    students_data = []
    present_cnt = 0
    absent_cnt = 0
    late_cnt = 0
    justified_cnt = 0
    unnotified_absents_count = 0

    for st in students:
        att = att_map.get(st.id)
        status = att.status if att else None
        if status == 'present':
            present_cnt += 1
        elif status == 'absent':
            absent_cnt += 1
        elif status == 'late':
            late_cnt += 1
        elif status == 'justified':
            justified_cnt += 1

        alert_sent = "Alerte WhatsApp envoyée" in (att.notes or "") if att else False
        if status == 'absent' and not alert_sent:
            unnotified_absents_count += 1

        parent_lang = st.parent.preferred_language if (st.parent and st.parent.preferred_language) else lang
        wa_url = get_whatsapp_absence_chat_url(schedule, st, target_date=target_date, lang=parent_lang) if status == 'absent' else ""

        students_data.append({
            'student': st,
            'attendance': att,
            'status': status,
            'notes': att.notes if att else '',
            'alert_sent': alert_sent,
            'whatsapp_url': wa_url,
        })

    day_name = ARABIC_DAYS.get(target_date.weekday(), '') if lang == 'ar' else FRENCH_DAYS.get(target_date.weekday(), '')
    is_cancelled = is_day_cancelled(target_date) or is_schedule_cancelled(schedule, target_date)

    context = {
        'schedule': schedule,
        'target_date': target_date,
        'day_name': day_name,
        'is_today': target_date == date.today(),
        'students_data': students_data,
        'total_enrolled': len(students),
        'present_cnt': present_cnt,
        'absent_cnt': absent_cnt,
        'late_cnt': late_cnt,
        'justified_cnt': justified_cnt,
        'unmarked_cnt': len(students) - (present_cnt + absent_cnt + late_cnt + justified_cnt),
        'unnotified_absents_count': unnotified_absents_count,
        'is_cancelled': is_cancelled,
    }
    return render(request, 'portal/attendance_sheet.html', context)


@trainer_or_admin_required
@require_POST
def attendance_scan_ajax_view(request, session_id):
    """
    API de pointage direct pour le scanner QR Code et le clic manuel :
    Reçoit un code QR, un matricule ou un ID d'élève, met à jour la présence et renvoie JSON.
    """
    import json
    from datetime import date, datetime

    lang = getattr(request, 'LANGUAGE_CODE', DEFAULT_LANGUAGE)
    schedule = get_object_or_404(SessionSchedule, id=session_id)

    # Récupérer les données depuis JSON ou POST
    try:
        data = json.loads(request.body.decode('utf-8'))
    except Exception:
        data = request.POST

    code = str(data.get('code', '')).strip()
    status = str(data.get('status', 'present')).strip()
    notes = str(data.get('notes', '')).strip()
    date_str = str(data.get('date', '')).strip()

    if date_str:
        try:
            target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            target_date = date.today()
    else:
        target_date = date.today()

    if not code:
        return JsonResponse({'success': False, 'error': 'Code manquant / رمز مفقود'}, status=400)

    # Normaliser le code (retirer préfixe éventuel GCA:STU:)
    clean_code = code
    if clean_code.upper().startswith('GCA:STU:'):
        clean_code = clean_code[8:].strip()

    # Trouver l'élève par matricule ou id
    student = None
    if clean_code.isdigit():
        student = Student.objects.filter(id=int(clean_code)).first()
    if not student:
        student = Student.objects.filter(registration_number__iexact=clean_code).first()

    if not student:
        return JsonResponse({
            'success': False,
            'error': f"Élève introuvable pour le code « {clean_code} »" if lang == 'fr' else f"لم يتم العثور على التلميذ للرمز « {clean_code} »"
        }, status=404)

    # Vérifier s'il est inscrit dans ce groupe
    in_group = schedule.group.students.filter(id=student.id).exists()

    att, created = Attendance.objects.update_or_create(
        student=student,
        session=schedule,
        date=target_date,
        defaults={
            'status': status,
            'notes': notes,
        }
    )

    now_time = datetime.now().strftime('%H:%M')
    status_label = att.get_status_label(lang)
    wa_result = None

    # Déclencher automatiquement la notification WhatsApp de présence au parent
    if status == 'present':
        from academy.whatsapp_absence import send_presence_notification_to_parent
        wa_result = send_presence_notification_to_parent(att)

    wa_sent = bool(wa_result and wa_result.get('success'))
    wa_tag = " (📲 WhatsApp envoyé)" if wa_sent else ""

    msg = (
        f"✓ {student.get_full_name('fr')} pointé : {status_label} à {now_time}{wa_tag}"
        if lang == 'fr' else
        f"✓ تم تسجيل {student.get_full_name('ar')} : {status_label} في {now_time}{wa_tag}"
    )

    return JsonResponse({
        'success': True,
        'student_id': student.id,
        'student_name': student.get_bilingual_full_name(),
        'registration_number': student.registration_number,
        'status': status,
        'status_label': status_label,
        'time': now_time,
        'in_group': in_group,
        'whatsapp_sent': wa_sent,
        'whatsapp_result': wa_result,
        'message': msg,
    })


@trainer_or_admin_required
@require_POST
def attendance_notify_absents_view(request, session_id):
    """
    Déclenche l'envoi groupé des alertes WhatsApp d'absence aux parents des élèves absents.
    """
    from datetime import datetime, date
    from academy.whatsapp_absence import send_bulk_absence_alerts_for_session
    schedule = get_object_or_404(SessionSchedule, id=session_id)

    date_str = request.POST.get('date', request.GET.get('date', ''))
    if date_str:
        try:
            target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            target_date = date.today()
    else:
        target_date = date.today()

    res = send_bulk_absence_alerts_for_session(schedule, target_date=target_date)
    sent_cnt = res['sent_count']
    lang = getattr(request, 'LANGUAGE_CODE', DEFAULT_LANGUAGE)

    if sent_cnt > 0:
        msg = (
            f"✓ {sent_cnt} alerte(s) WhatsApp d'absence envoyée(s) avec succès aux parents !"
            if lang == 'fr' else
            f"✓ تم إرسال {sent_cnt} إشعار غياب بنجاح إلى أولياء الأمور عبر واتساب !"
        )
        messages.success(request, msg)
    elif res['skipped_count'] > 0:
        msg = (
            "ℹ️ Tous les parents des élèves absents ont déjà reçu leur alerte pour cette séance."
            if lang == 'fr' else
            "ℹ️ تم إرسال الإشعارات مسبقاً لجميع أولياء أمور التلاميذ الغائبين في هذه الحصة."
        )
        messages.info(request, msg)
    else:
        msg = (
            "Aucun élève absent à notifier pour cette séance."
            if lang == 'fr' else
            "لا يوجد أي تلميذ غائب لإرسال إشعار له في هذه الحصة."
        )
        messages.warning(request, msg)

    return redirect(f"/attendance/{session_id}/?date={target_date.strftime('%Y-%m-%d')}")


@trainer_or_admin_required
@require_POST
def attendance_notify_single_absent_view(request, session_id, student_id):
    """
    Envoie l'alerte WhatsApp d'absence pour un élève spécifique.
    """
    from datetime import datetime, date
    from academy.whatsapp_absence import send_absence_alert_to_parent
    schedule = get_object_or_404(SessionSchedule, id=session_id)
    student = get_object_or_404(Student, id=student_id)

    date_str = request.POST.get('date', request.GET.get('date', ''))
    if date_str:
        try:
            target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            target_date = date.today()
    else:
        target_date = date.today()

    att = Attendance.objects.filter(session=schedule, student=student, date=target_date).first()
    lang = getattr(request, 'LANGUAGE_CODE', DEFAULT_LANGUAGE)

    if not att or att.status != 'absent':
        messages.error(request, "Cet élève n'est pas marqué absent." if lang == 'fr' else "التلميذ غير مسجل كغائب.")
        return redirect(f"/attendance/{session_id}/?date={target_date.strftime('%Y-%m-%d')}")

    res = send_absence_alert_to_parent(att, force=True)
    if res.get('success'):
        msg = (
            f"✓ Alerte d'absence envoyée avec succès au parent de {student.get_full_name('fr')} !"
            if lang == 'fr' else
            f"✓ تم إرسال إشعار الغياب بنجاح إلى ولي أمر {student.get_full_name('ar')} !"
        )
        messages.success(request, msg)
    else:
        messages.error(request, f"Erreur : {res.get('error')}")

    return redirect(f"/attendance/{session_id}/?date={target_date.strftime('%Y-%m-%d')}")


@admin_required
def student_card_pdf_view(request, student_id):
    """Téléchargement du badge individuel d'un élève avec son QR Code officiel."""
    from portal.student_card import generate_single_student_card_pdf

    student = get_object_or_404(Student, id=student_id)
    pdf_bytes = generate_single_student_card_pdf(student)

    filename = f"Carte_Etudiant_{student.registration_number}.pdf"
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="{filename}"'
    return response


@admin_required
def students_cards_sheet_pdf_view(request):
    """Téléchargement d'une planche A4 de badges d'élèves avec QR Codes (8 cartes par page)."""
    from portal.student_card import generate_student_cards_sheet_pdf

    group_id = request.GET.get('group')
    if group_id:
        group = get_object_or_404(Group, id=group_id)
        students = list(group.students.filter(active=True).order_by('last_name_fr', 'first_name_fr'))
        filename = f"Planche_Cartes_{group.name_fr.replace(' ', '_')}.pdf"
    else:
        students = list(Student.objects.filter(active=True).order_by('last_name_fr', 'first_name_fr'))
        filename = "Planche_Cartes_Tous_Eleves_GCA.pdf"

    if not students:
        messages.warning(request, "Aucun élève trouvé pour générer les cartes.")
        return redirect('portal:students')

    pdf_bytes = generate_student_cards_sheet_pdf(students)
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="{filename}"'
    return response


def _get_recap_data(request):
    import calendar
    from datetime import date, datetime, timedelta
    from collections import OrderedDict
    from core.i18n import FRENCH_DAYS, ARABIC_DAYS, FRENCH_MONTHS, ARABIC_MONTHS

    lang = getattr(request, 'LANGUAGE_CODE', DEFAULT_LANGUAGE)
    period = request.GET.get('period', 'week')
    today = date.today()

    # 1. Calcul des dates selon la granularité
    if period == 'day':
        date_str = request.GET.get('date', today.strftime('%Y-%m-%d'))
        try:
            target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            target_date = today
        start_date = target_date
        end_date = target_date
        day_n = ARABIC_DAYS.get(target_date.weekday(), '') if lang == 'ar' else FRENCH_DAYS.get(target_date.weekday(), '')
        period_label = f"{day_n} {target_date.strftime('%d/%m/%Y')}"
    elif period == 'week':
        date_str = request.GET.get('date', today.strftime('%Y-%m-%d'))
        try:
            target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            target_date = today
        start_date = target_date - timedelta(days=target_date.weekday())
        end_date = start_date + timedelta(days=6)
        period_label = (
            f"Semaine du {start_date.strftime('%d/%m')} au {end_date.strftime('%d/%m/%Y')}"
            if lang == 'fr' else
            f"أسبوع من {start_date.strftime('%d/%m')} إلى {end_date.strftime('%d/%m/%Y')}"
        )
    elif period == 'month':
        try:
            month = int(request.GET.get('month', today.month))
            year = int(request.GET.get('year', today.year))
        except (ValueError, TypeError):
            month = today.month
            year = today.year
        start_date = date(year, month, 1)
        last_day = calendar.monthrange(year, month)[1]
        end_date = date(year, month, last_day)
        m_name = ARABIC_MONTHS.get(month, '') if lang == 'ar' else FRENCH_MONTHS.get(month, '')
        period_label = f"{m_name} {year}"
    elif period == 'year':
        try:
            year = int(request.GET.get('year', today.year))
        except (ValueError, TypeError):
            year = today.year
        start_date = date(year, 1, 1)
        end_date = date(year, 12, 31)
        period_label = f"Année {year}" if lang == 'fr' else f"سنة {year}"
    else:
        period = 'week'
        start_date = today - timedelta(days=today.weekday())
        end_date = start_date + timedelta(days=6)
        period_label = f"Semaine du {start_date.strftime('%d/%m')} au {end_date.strftime('%d/%m/%Y')}"

    # 2. Filtres
    subject_id = request.GET.get('subject', '')
    group_id = request.GET.get('group', '')
    status_filter = request.GET.get('status', '')
    q = request.GET.get('q', '').strip()

    qs = Attendance.objects.filter(
        date__gte=start_date,
        date__lte=end_date
    ).select_related(
        'student',
        'student__parent',
        'session',
        'session__group',
        'session__group__subject',
        'session__room'
    ).order_by(
        'session__group__subject__name_fr',
        'session__group__name_fr',
        'date',
        'session__start_time',
        'student__last_name_fr',
        'student__first_name_fr'
    )

    if subject_id:
        qs = qs.filter(session__group__subject_id=subject_id)
    if group_id:
        qs = qs.filter(session__group_id=group_id)
    if status_filter:
        qs = qs.filter(status=status_filter)
    if q:
        qs = qs.filter(
            Q(student__first_name_fr__icontains=q) |
            Q(student__last_name_fr__icontains=q) |
            Q(student__first_name_ar__icontains=q) |
            Q(student__last_name_ar__icontains=q) |
            Q(student__registration_number__icontains=q)
        )

    attendances_list = list(qs)

    # 3. Calculs KPI
    total_records = len(attendances_list)
    present_cnt = sum(1 for a in attendances_list if a.status == 'present')
    absent_cnt = sum(1 for a in attendances_list if a.status == 'absent')
    late_cnt = sum(1 for a in attendances_list if a.status == 'late')
    justified_cnt = sum(1 for a in attendances_list if a.status == 'justified')
    global_rate = round((present_cnt + justified_cnt + late_cnt * 0.5) / total_records * 100, 1) if total_records > 0 else 0

    # 4. Groupement Hiérarchique : Activité > Groupe > Séance (date + horaire)
    subjects_tree = OrderedDict()
    for att in attendances_list:
        grp = att.session.group
        subj = grp.subject if grp else None
        subj_id = subj.id if subj else 0
        subj_name = subj.get_name(lang) if subj else ("Échecs" if lang == 'fr' else "شطرنج")

        if subj_id not in subjects_tree:
            subjects_tree[subj_id] = {
                'subject': subj,
                'name': subj_name,
                'groups': OrderedDict()
            }

        grp_id = grp.id if grp else 0
        grp_name = grp.get_name(lang) if grp else ("Groupe" if lang == 'fr' else "فوج")
        if grp_id not in subjects_tree[subj_id]['groups']:
            subjects_tree[subj_id]['groups'][grp_id] = {
                'group': grp,
                'name': grp_name,
                'color': grp.get_color() if grp else "#0A192F",
                'sessions': OrderedDict()
            }

        sess_key = (att.session_id, att.date)
        if sess_key not in subjects_tree[subj_id]['groups'][grp_id]['sessions']:
            d_name = ARABIC_DAYS.get(att.date.weekday(), '') if lang == 'ar' else FRENCH_DAYS.get(att.date.weekday(), '')
            subjects_tree[subj_id]['groups'][grp_id]['sessions'][sess_key] = {
                'session': att.session,
                'date': att.date,
                'day_name': d_name,
                'trainer_name': att.session.get_trainer_name(lang),
                'room_name': att.session.room.get_name(lang) if att.session.room else '',
                'attendances': [],
                'present': 0,
                'absent': 0,
                'late': 0,
                'justified': 0,
            }

        s_entry = subjects_tree[subj_id]['groups'][grp_id]['sessions'][sess_key]
        s_entry['attendances'].append(att)
        if att.status == 'present':
            s_entry['present'] += 1
        elif att.status == 'absent':
            s_entry['absent'] += 1
        elif att.status == 'late':
            s_entry['late'] += 1
        elif att.status == 'justified':
            s_entry['justified'] += 1

    # 5. Synthèse par élève
    student_stats = {}
    for att in attendances_list:
        st = att.student
        if st.id not in student_stats:
            student_stats[st.id] = {
                'student': st,
                'total': 0,
                'present': 0,
                'absent': 0,
                'late': 0,
                'justified': 0,
            }
        student_stats[st.id]['total'] += 1
        if att.status == 'present':
            student_stats[st.id]['present'] += 1
        elif att.status == 'absent':
            student_stats[st.id]['absent'] += 1
        elif att.status == 'late':
            student_stats[st.id]['late'] += 1
        elif att.status == 'justified':
            student_stats[st.id]['justified'] += 1

    student_summaries = []
    for st_id, s in student_stats.items():
        s_tot = s['total']
        s_rate = round((s['present'] + s['justified'] + s['late'] * 0.5) / s_tot * 100, 1) if s_tot > 0 else 0
        s['rate'] = s_rate
        student_summaries.append(s)
    student_summaries.sort(key=lambda x: (x['student'].last_name_fr, x['student'].first_name_fr))

    total_sessions_count = sum(len(g['sessions']) for subj in subjects_tree.values() for g in subj['groups'].values())

    return {
        'period': period,
        'period_label': period_label,
        'start_date': start_date,
        'end_date': end_date,
        'today': today,
        'subject_id': subject_id,
        'group_id': group_id,
        'status_filter': status_filter,
        'q': q,
        'attendances_list': attendances_list,
        'total_records': total_records,
        'total_sessions_count': total_sessions_count,
        'present_cnt': present_cnt,
        'absent_cnt': absent_cnt,
        'late_cnt': late_cnt,
        'justified_cnt': justified_cnt,
        'global_rate': global_rate,
        'subjects_tree': subjects_tree,
        'student_summaries': student_summaries,
        'all_subjects': Subject.objects.all(),
        'all_groups': Group.objects.select_related('subject').all(),
        'available_years': range(today.year - 2, today.year + 2),
    }


@admin_required
def attendance_recap_view(request):
    """
    Feuille et Registre Récapitulatif Global des Présences :
    Classé par Activité > Groupe > Date & Heure,
    Filtrable par Journée, Semaine, Mois, Année.
    """
    data = _get_recap_data(request)
    return render(request, 'portal/attendance_recap.html', data)


@admin_required
def attendance_recap_excel_view(request):
    """Exportation du registre complet des présences au format Excel (.xlsx)."""
    from portal.excel_attendance import generate_attendance_excel
    from datetime import datetime
    lang = getattr(request, 'LANGUAGE_CODE', DEFAULT_LANGUAGE)
    data = _get_recap_data(request)
    excel_bytes = generate_attendance_excel(
        data['attendances_list'],
        data['student_summaries'],
        data['period_label'],
        lang=lang
    )
    filename = f"Registre_Presences_{data['period']}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    response = HttpResponse(
        excel_bytes,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@admin_required
def financial_forecast_view(request):
    """
    Tableau de bord prévisionnel financier et taux de recouvrement du 15 du mois.
    """
    from finance.forecast import get_monthly_financial_forecast
    lang = getattr(request, 'LANGUAGE_CODE', DEFAULT_LANGUAGE)
    month = request.GET.get('month')
    year = request.GET.get('year')

    forecast_data = get_monthly_financial_forecast(month=month, year=year, lang=lang)
    return render(request, 'portal/financial_forecast.html', forecast_data)


def pwa_manifest_view(request):
    """Sert le fichier de configuration PWA Manifest officiel."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    manifest_path = os.path.join(base_dir, 'static', 'manifest.webmanifest')
    if not os.path.exists(manifest_path):
        manifest_path = os.path.join(base_dir, 'staticfiles', 'manifest.webmanifest')
    if os.path.exists(manifest_path):
        with open(manifest_path, 'r', encoding='utf-8') as f:
            content = f.read()
    else:
        content = '{}'
    response = HttpResponse(content, content_type='application/manifest+json; charset=utf-8')
    response['Access-Control-Allow-Origin'] = '*'
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return response


def pwa_service_worker_view(request):
    """Sert le service worker PWA avec l'autorisation de portée globale (Scope: /)."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sw_path = os.path.join(base_dir, 'static', 'js', 'service-worker.js')
    if not os.path.exists(sw_path):
        sw_path = os.path.join(base_dir, 'staticfiles', 'js', 'service-worker.js')
    if os.path.exists(sw_path):
        with open(sw_path, 'r', encoding='utf-8') as f:
            content = f.read()
    else:
        content = '/* Service Worker fallback */'
    response = HttpResponse(content, content_type='application/javascript; charset=utf-8')
    response['Service-Worker-Allowed'] = '/'
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return response
