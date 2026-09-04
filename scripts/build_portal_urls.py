content = """from django.urls import path
from portal import views

app_name = 'portal'

urlpatterns = [
    path('', views.dashboard_view, name='dashboard'),
    path('set-language/<str:lang>/', views.set_language, name='set_language'),
    path('students/', views.students_list_view, name='students'),
    path('students/export-excel/', views.export_students_excel_view, name='export_students_excel'),
    path('planning/', views.planning_view, name='planning'),
    path('payments/', views.payments_list_view, name='payments'),
    path('payments/<int:payment_id>/pdf/', views.download_receipt_pdf_view, name='receipt_pdf'),
    path('reminders/run/', views.run_reminders_view, name='run_reminders'),
    path('parent/', views.parent_space_view, name='parent_space'),
]
"""

with open('portal/urls.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('Created portal/urls.py')
