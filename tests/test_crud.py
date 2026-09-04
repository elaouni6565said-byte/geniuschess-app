import pytest
from datetime import date, time
from decimal import Decimal
from django.test import Client
from academy.models import Student, Parent, Group, Subject, Room, Level, SessionSchedule, User

@pytest.mark.django_db
def test_crud_student_multi_activities():
    """Validates student registration with multiple activities simultaneously, edit and delete."""
    client = Client()
    # Login as admin
    admin = User.objects.get(username='admin')
    admin.set_password('CGAESA65')
    admin.save()
    client.login(username='admin', password='CGAESA65')

    parent = Parent.objects.first()
    groups = list(Group.objects.all()[:2])
    assert len(groups) >= 2

    # Clean up any leftover test data
    Student.objects.filter(first_name_fr='Yassine').delete()

    # 1. Inscribe student with MULTIPLE activities (ManyToMany groups)
    data = {
        'registration_number': '', # test auto-generation
        'first_name_fr': 'Yassine',
        'last_name_fr': 'Tazi',
        'first_name_ar': 'ياسين',
        'last_name_ar': 'التازي',
        'birth_date': '2016-04-12',
        'parent': parent.id,
        'groups': [g.id for g in groups], # Multiple groups selected!
        'active': True,
    }
    resp_create = client.post('/students/add/', data)
    assert resp_create.status_code == 302 # Redirects to /students/

    # Verify student was created
    new_student = Student.objects.filter(first_name_fr='Yassine').first()
    assert new_student is not None
    assert new_student.registration_number.startswith('GCA-2026-')
    assert new_student.groups.count() == 2 # Multi-activities verified!
    assert set(new_student.groups.all()) == set(groups)

    # 2. Edit student: add a third group
    all_groups = list(Group.objects.all()[:3])
    edit_data = {
        'registration_number': new_student.registration_number,
        'first_name_fr': 'Yassine',
        'last_name_fr': 'Tazi',
        'first_name_ar': 'ياسين',
        'last_name_ar': 'التازي',
        'birth_date': '2016-04-12',
        'parent': parent.id,
        'groups': [g.id for g in all_groups],
        'active': True,
    }
    resp_edit = client.post(f'/students/{new_student.id}/edit/', edit_data)
    assert resp_edit.status_code == 302
    new_student.refresh_from_db()
    assert new_student.groups.count() == len(all_groups)

    # 3. Delete student
    resp_del_get = client.get(f'/students/{new_student.id}/delete/?lang=fr')
    assert resp_del_get.status_code == 200
    assert 'Confirmer la suppression' in resp_del_get.content.decode('utf-8')

    resp_del_post = client.post(f'/students/{new_student.id}/delete/')
    assert resp_del_post.status_code == 302
    assert not Student.objects.filter(id=new_student.id).exists()


@pytest.mark.django_db
def test_crud_parent_with_user_account():
    """Validates creating, modifying and deleting parents with user portal accounts."""
    client = Client()
    admin = User.objects.get(username='admin')
    admin.set_password('CGAESA65')
    admin.save()
    client.login(username='admin', password='CGAESA65')

    # 1. Create new parent
    parent_data = {
        'full_name_fr': 'Rachid Tazi',
        'full_name_ar': 'رشيد التازي',
        'cin': 'AB998877',
        'phone': '0665544332',
        'email': 'rachid.tazi@example.com',
        'preferred_language': 'ar',
    }
    resp_p_create = client.post('/parents/add/', parent_data)
    assert resp_p_create.status_code == 302

    created_parent = Parent.objects.filter(full_name_fr='Rachid Tazi').first()
    assert created_parent is not None
    assert created_parent.user is not None
    assert created_parent.user.role == 'parent'
    assert created_parent.preferred_language == 'ar'

    # 2. Modify parent
    parent_data['phone'] = '0669998877'
    resp_p_edit = client.post(f'/parents/{created_parent.id}/edit/', parent_data)
    assert resp_p_edit.status_code == 302
    created_parent.refresh_from_db()
    assert created_parent.phone == '0669998877'

    # 3. Delete parent
    resp_p_del = client.post(f'/parents/{created_parent.id}/delete/')
    assert resp_p_del.status_code == 302
    assert not Parent.objects.filter(id=created_parent.id).exists()


@pytest.mark.django_db
def test_crud_activity_and_group():
    """Validates creating and deleting subjects and groups."""
    client = Client()
    admin = User.objects.get(username='admin')
    admin.set_password('CGAESA65')
    admin.save()
    client.login(username='admin', password='CGAESA65')

    # 1. Create Subject
    subj_data = {
        'name_fr': 'Programmation Python',
        'name_ar': 'برمجة بايثون',
        'color': '#10B981',
        'icon': 'code',
        'description_fr': 'Apprentissage du code Python pour enfants',
        'description_ar': 'تعليم بايثون للأطفال',
    }
    resp_s_create = client.post('/activities/add/', subj_data)
    assert resp_s_create.status_code == 302

    new_subj = Subject.objects.filter(name_fr='Programmation Python').first()
    assert new_subj is not None

    # 2. Create Group within this Subject
    grp_data = {
        'name_fr': 'Groupe Python Jeunes',
        'name_ar': 'مجموعة بايثون للناشئين',
        'subject': new_subj.id,
        'level': '',
        'monthly_fee': '350.00',
    }
    resp_g_create = client.post('/groups/add/', grp_data)
    assert resp_g_create.status_code == 302

    new_grp = Group.objects.filter(name_fr='Groupe Python Jeunes').first()
    assert new_grp is not None
    assert new_grp.monthly_fee == Decimal('350.00')

    # 3. Delete Group
    resp_g_del = client.post(f'/groups/{new_grp.id}/delete/')
    assert resp_g_del.status_code == 302
    assert not Group.objects.filter(id=new_grp.id).exists()

    # 4. Delete Subject
    resp_s_del = client.post(f'/activities/{new_subj.id}/delete/')
    assert resp_s_del.status_code == 302
    assert not Subject.objects.filter(id=new_subj.id).exists()


@pytest.mark.django_db
def test_crud_planning_session():
    """Validates creating, editing and deleting weekly planning sessions."""
    client = Client()
    admin = User.objects.get(username='admin')
    admin.set_password('CGAESA65')
    admin.save()
    client.login(username='admin', password='CGAESA65')

    group = Group.objects.first()
    room = Room.objects.first()

    session_data = {
        'group': group.id,
        'room': room.id,
        'day_of_week': 1, # Mardi
        'start_time': '16:00',
        'end_time': '18:00',
        'trainer_name_fr': 'Mehdi Ben',
        'trainer_name_ar': 'مهدي بن',
    }
    resp_sess_create = client.post('/planning/add/', session_data)
    assert resp_sess_create.status_code == 302

    new_sess = SessionSchedule.objects.filter(day_of_week=1, start_time='16:00').first()
    assert new_sess is not None

    # Edit session
    session_data['start_time'] = '16:30'
    resp_sess_edit = client.post(f'/planning/{new_sess.id}/edit/', session_data)
    assert resp_sess_edit.status_code == 302
    new_sess.refresh_from_db()
    assert str(new_sess.start_time) == '16:30:00'

    # Delete session
    resp_sess_del = client.post(f'/planning/{new_sess.id}/delete/')
    assert resp_sess_del.status_code == 302
    assert not SessionSchedule.objects.filter(id=new_sess.id).exists()


@pytest.mark.django_db
def test_crud_security_access_control():
    """Validates that unauthenticated users or non-admin cannot access CRUD operations."""
    client = Client()
    
    # 1. Anonymous access redirected to login
    resp_anon = client.get('/students/add/')
    assert resp_anon.status_code == 302
    assert '/login/' in resp_anon.url

    # 2. Parent login cannot access admin CRUD
    client.login(username='karim_alaoui', password='Parent@2026')
    resp_parent_forbidden = client.get('/students/add/')
    assert resp_parent_forbidden.status_code == 302 # Redirected because permission denied
