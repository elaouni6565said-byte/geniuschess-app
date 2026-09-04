from django.urls import path
from portal import views

app_name = 'portal'

urlpatterns = [
    path('', views.dashboard_view, name='dashboard'),
    path('set-language/<str:lang>/', views.set_language, name='set_language'),
    path('students/', views.students_list_view, name='students'),
    path('students/export-excel/', views.export_students_excel_view, name='export_students_excel'),
    path('planning/', views.planning_view, name='planning'),
    path('payments/', views.payments_list_view, name='payments'),
    path('payments/add/', views.payment_create_view, name='payment_add'),
    path('payments/<int:payment_id>/edit/', views.payment_edit_view, name='payment_edit'),
    path('payments/<int:payment_id>/delete/', views.payment_delete_view, name='payment_delete'),
    path('payments/<int:payment_id>/pdf/', views.download_receipt_pdf_view, name='receipt_pdf'),
    path('reminders/run/', views.run_reminders_view, name='run_reminders'),
    path('parent/', views.parent_space_view, name='parent_space'),
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # Élèves CRUD
    path('students/add/', views.student_create_view, name='student_add'),
    path('students/<int:student_id>/edit/', views.student_edit_view, name='student_edit'),
    path('students/<int:student_id>/delete/', views.student_delete_view, name='student_delete'),

    # Parents CRUD
    path('parents/', views.parents_list_view, name='parents_list'),
    path('parents/add/', views.parent_create_view, name='parent_add'),
    path('parents/<int:parent_id>/edit/', views.parent_edit_view, name='parent_edit'),
    path('parents/<int:parent_id>/delete/', views.parent_delete_view, name='parent_delete'),

    # Activités & Groupes CRUD
    path('activities/', views.activities_list_view, name='activities_list'),
    path('activities/add/', views.activity_create_view, name='activity_add'),
    path('activities/<int:subject_id>/delete/', views.activity_delete_view, name='activity_delete'),
    path('groups/add/', views.group_create_view, name='group_add'),
    path('groups/<int:group_id>/delete/', views.group_delete_view, name='group_delete'),

    # Planning CRUD
    path('planning/add/', views.session_create_view, name='session_add'),
    path('planning/<int:session_id>/edit/', views.session_edit_view, name='session_edit'),
    path('planning/<int:session_id>/delete/', views.session_delete_view, name='session_delete'),
]
