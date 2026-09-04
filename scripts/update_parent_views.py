with open('portal/views.py', 'r', encoding='utf-8') as f:
    code = f.read()

start_marker = '@admin_required\ndef download_receipt_pdf_view(request, payment_id):'
end_marker = 'def logout_view(request):'

start_idx = code.find(start_marker)
end_idx = code.find(end_marker)

new_chunk = '''def download_receipt_pdf_view(request, payment_id):
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
    all_parents = []
    parent = None
    
    # If parent is authenticated, pick their own profile strictly
    if request.user.is_authenticated and hasattr(request.user, 'parent_profile'):
        parent = request.user.parent_profile
    elif request.user.is_authenticated and (request.user.is_admin_role() or request.user.is_superuser):
        all_parents = list(Parent.objects.all().order_by('id'))
        family_id = request.GET.get('family_id')
        if family_id:
            parent = Parent.objects.filter(id=family_id).first()
        if not parent:
            parent = all_parents[0] if all_parents else None
    else:
        # Anonymous demo preview
        all_parents = list(Parent.objects.all().order_by('id'))
        parent = all_parents[0] if all_parents else None

    children = []
    if parent:
        children = list(parent.students.all().prefetch_related(
            'groups__subject', 'groups__room', 'groups__schedules'
        ))
        for ch in children:
            # Collect and sort schedules for this child
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

            # Collect attendances for this child
            child_att = list(Attendance.objects.filter(student=ch).select_related('session__group__subject').order_by('-date'))
            ch.child_attendances = child_att
            ch.total_sessions = len(child_att)
            ch.present_count = len([a for a in child_att if a.status == 'present'])
            ch.justified_count = len([a for a in child_att if a.status == 'justified'])
            ch.absent_count = len([a for a in child_att if a.status == 'absent'])
            ch.late_count = len([a for a in child_att if a.status == 'late'])
            ch.attendance_rate = round((ch.present_count / ch.total_sessions) * 100) if ch.total_sessions > 0 else 100
    
    # Invoices & Payments for parent's children
    child_ids = [c.id for c in children]
    invoices = Invoice.objects.filter(student_id__in=child_ids).select_related('student', 'group').order_by('-due_date')
    payments = Payment.objects.filter(student_id__in=child_ids).select_related('student', 'invoice').order_by('-payment_date')
    
    user_notifications = Notification.objects.filter(recipient=parent.user).order_by('-created_at')[:8] if parent and parent.user else []

    context = {
        'parent': parent,
        'all_parents': all_parents,
        'children': children,
        'invoices': invoices,
        'payments': payments,
        'notifications': user_notifications,
    }
    return render(request, 'portal/parent_space.html', context)


def login_view(request):
    lang = getattr(request, 'LANGUAGE_CODE', DEFAULT_LANGUAGE)
    next_url = request.GET.get('next') or request.POST.get('next') or '/'

    if request.user.is_authenticated:
        if request.user.is_parent_role():
            return redirect('portal:parent_space')
        elif request.user.is_admin_role() or request.user.is_superuser:
            return redirect(next_url if next_url != '/login/' else '/')

    error_msg = None
    if request.method == 'POST':
        username = request.POST.get('username', '').strip() or 'admin'
        password = request.POST.get('password', '').strip()

        user = authenticate(request, username=username, password=password)
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
    }
    return render(request, 'portal/login.html', context)

'''

if start_idx != -1 and end_idx != -1:
    updated_code = code[:start_idx] + new_chunk + code[end_idx:]
    with open('portal/views.py', 'w', encoding='utf-8') as f:
        f.write(updated_code)
    print('Successfully updated parent_space_view and login_view!')
else:
    print('Indices not found:', start_idx, end_idx)
