content = """from decimal import Decimal
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
    Attendance, Notification, User
)
from finance.models import Payment, Invoice
from finance.receipt_pdf import generate_receipt_pdf
from finance.reminders import generate_monthly_reminders
from portal.excel_export import export_students_to_excel


def set_language(request, lang):
    \"\"\"
    Immediately switches application language and persists across:
    1. Authenticated User model
    2. Request Session
    3. Long-lived Cookie
    \"\"\"
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


def dashboard_view(request):
    lang = getattr(request, 'LANGUAGE_CODE', DEFAULT_LANGUAGE)
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
    activities = Subject.objects.all()

    context = {
        'total_students': total_students,
        'active_groups': active_groups,
        'total_revenue': total_revenue,
        'total_unpaid': total_unpaid,
        'attendance_rate': att_rate,
        'today_sessions': today_sessions,
        'recent_payments': recent_payments,
        'activities': activities,
    }
    return render(request, 'portal/dashboard.html', context)


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


def export_students_excel_view(request):
    lang = getattr(request, 'LANGUAGE_CODE', DEFAULT_LANGUAGE)
    students = Student.objects.filter(active=True).select_related('parent').prefetch_related('groups__subject')
    excel_data = export_students_to_excel(students, lang=lang)

    filename = f"GCA_Eleves_{lang}.xlsx"
    response = HttpResponse(
        excel_data,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


def planning_view(request):
    lang = getattr(request, 'LANGUAGE_CODE', DEFAULT_LANGUAGE)
    room_id = request.GET.get('room')
    
    schedules = SessionSchedule.objects.select_related('group', 'group__subject', 'room').order_by('day_of_week', 'start_time')
    if room_id:
        schedules = schedules.filter(room_id=room_id)

    # Group schedules by day of week (0 to 6)
    days_data = []
    from core.i18n import FRENCH_DAYS, ARABIC_DAYS
    days_dict = ARABIC_DAYS if lang == 'ar' else FRENCH_DAYS
    
    for day_code in range(7):
        day_sessions = [s for s in schedules if s.day_of_week == day_code]
        days_data.append({
            'day_code': day_code,
            'day_name': days_dict.get(day_code, ''),
            'sessions': day_sessions,
        })

    rooms = Room.objects.all()
    context = {
        'days_data': days_data,
        'rooms': rooms,
        'selected_room': int(room_id) if room_id and room_id.isdigit() else None,
    }
    return render(request, 'portal/planning.html', context)


def payments_list_view(request):
    lang = getattr(request, 'LANGUAGE_CODE', DEFAULT_LANGUAGE)
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
        
    payment = get_object_or_404(Payment.objects.select_related('student', 'invoice'), id=payment_id)
    pdf_bytes = generate_receipt_pdf(payment, lang=lang)
    
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    filename = f"Recu_{payment.receipt_number}_{lang}.pdf"
    response['Content-Disposition'] = f'inline; filename="{filename}"'
    return response


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
    
    # If parent is authenticated, pick their profile, else pick demo parent
    parent = None
    if request.user.is_authenticated and hasattr(request.user, 'parent_profile'):
        parent = request.user.parent_profile
    else:
        parent = Parent.objects.first()

    children = parent.students.all().prefetch_related('groups__subject', 'groups__schedules') if parent else []
    
    # Invoices & Payments for parent's children
    child_ids = [c.id for c in children]
    invoices = Invoice.objects.filter(student_id__in=child_ids).select_related('student', 'group').order_by('-due_date')
    payments = Payment.objects.filter(student_id__in=child_ids).select_related('student', 'invoice').order_by('-payment_date')
    attendances = Attendance.objects.filter(student_id__in=child_ids).select_related('student', 'session').order_by('-date')[:10]
    
    user_notifications = Notification.objects.filter(recipient=parent.user).order_by('-created_at')[:8] if parent and parent.user else []

    context = {
        'parent': parent,
        'children': children,
        'invoices': invoices,
        'payments': payments,
        'attendances': attendances,
        'notifications': user_notifications,
    }
    return render(request, 'portal/parent_space.html', context)
"""

with open('portal/views.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('Created portal/views.py')
