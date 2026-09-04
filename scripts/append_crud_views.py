with open('portal/views.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Add import if not present
if "from portal.forms import" not in content:
    content = "from portal.forms import StudentForm, ParentForm, SubjectForm, GroupForm, SessionScheduleForm\n" + content

crud_views = '''

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
'''

content += crud_views
with open('portal/views.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('Successfully appended CRUD views to portal/views.py!')
