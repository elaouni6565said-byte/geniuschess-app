from django.urls import path
from portal import views

app_name = 'portal'

urlpatterns = [
    path('', views.dashboard_view, name='dashboard'),
    path('set-language/<str:lang>/', views.set_language, name='set_language'),
    path('set-device-mode/<str:mode>/', views.set_device_mode, name='set_device_mode'),
    path('students/', views.students_list_view, name='students'),
    path('students/export-excel/', views.export_students_excel_view, name='export_students_excel'),
    path('planning/', views.planning_view, name='planning'),
    path('planning/pdf/', views.download_planning_pdf_view, name='planning_pdf'),
    path('payments/', views.payments_list_view, name='payments'),
    path('payments/add/', views.payment_create_view, name='payment_add'),
    path('payments/export-paid-excel/', views.export_paid_payments_excel_view, name='export_paid_excel'),
    path('payments/export-unpaid-excel/', views.export_unpaid_invoices_excel_view, name='export_unpaid_excel'),
    path('payments/<int:payment_id>/edit/', views.payment_edit_view, name='payment_edit'),
    path('payments/<int:payment_id>/delete/', views.payment_delete_view, name='payment_delete'),
    path('payments/<int:payment_id>/pdf/', views.download_receipt_pdf_view, name='receipt_pdf'),
    path('reminders/run/', views.run_reminders_view, name='run_reminders'),
    path('reminders/whatsapp/', views.whatsapp_reminders_view, name='whatsapp_reminders'),
    path('parent/', views.parent_space_view, name='parent_space'),
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # Élèves CRUD
    path('students/add/', views.student_create_view, name='student_add'),
    path('students/<int:student_id>/edit/', views.student_edit_view, name='student_edit'),
    path('students/<int:student_id>/delete/', views.student_delete_view, name='student_delete'),
    path('students/<int:student_id>/timetable-pdf/', views.download_timetable_pdf_view, name='timetable_pdf'),

    # Parents CRUD
    path('parents/', views.parents_list_view, name='parents_list'),
    path('parents/add/', views.parent_create_view, name='parent_add'),
    path('parents/<int:parent_id>/edit/', views.parent_edit_view, name='parent_edit'),
    path('parents/<int:parent_id>/delete/', views.parent_delete_view, name='parent_delete'),

    # Activités & Groupes CRUD
    path('activities/', views.activities_list_view, name='activities_list'),
    path('activities/add/', views.activity_create_view, name='activity_add'),
    path('activities/<int:subject_id>/edit/', views.activity_edit_view, name='activity_edit'),
    path('activities/<int:subject_id>/delete/', views.activity_delete_view, name='activity_delete'),
    path('groups/add/', views.group_create_view, name='group_add'),
    path('groups/<int:group_id>/edit/', views.group_edit_view, name='group_edit'),
    path('groups/<int:group_id>/delete/', views.group_delete_view, name='group_delete'),

    # Planning CRUD
    path('planning/add/', views.session_create_view, name='session_add'),
    path('planning/<int:session_id>/edit/', views.session_edit_view, name='session_edit'),
    path('planning/<int:session_id>/delete/', views.session_delete_view, name='session_delete'),

    # Présences & Badges QR Code
    path('attendance/', views.attendance_list_view, name='attendance_list'),
    path('attendance/<int:session_id>/', views.attendance_sheet_view, name='attendance_sheet'),
    path('attendance/<int:session_id>/scan/', views.attendance_scan_ajax_view, name='attendance_scan_ajax'),
    path('students/<int:student_id>/card-pdf/', views.student_card_pdf_view, name='student_card_pdf'),
    path('students/cards-pdf/', views.students_cards_sheet_pdf_view, name='students_cards_sheet_pdf'),
]
