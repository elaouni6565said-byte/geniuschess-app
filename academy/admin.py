from django.contrib import admin
from academy.models import (
    User, Subject, Level, Room, Group, Parent, Student,
    SessionSchedule, Attendance, Notification, ParentVisitLog, Trainer
)

@admin.register(ParentVisitLog)
class ParentVisitLogAdmin(admin.ModelAdmin):
    list_display = ('parent', 'student', 'timestamp', 'ip_address')
    list_filter = ('timestamp', 'parent')
    search_fields = ('parent__full_name_fr', 'parent__full_name_ar', 'student__first_name_fr', 'student__last_name_fr')
    date_hierarchy = 'timestamp'

@admin.register(Trainer)
class TrainerAdmin(admin.ModelAdmin):
    list_display = ('first_name_fr', 'last_name_fr', 'specialty', 'compensation_type', 'default_rate', 'phone', 'cin', 'active')
    list_filter = ('active', 'compensation_type', 'specialty')
    search_fields = ('first_name_fr', 'last_name_fr', 'first_name_ar', 'last_name_ar', 'cin', 'phone')

admin.site.register(User)
admin.site.register(Subject)
admin.site.register(Level)
admin.site.register(Room)
admin.site.register(Group)
admin.site.register(Parent)
admin.site.register(Student)
admin.site.register(SessionSchedule)
admin.site.register(Attendance)
admin.site.register(Notification)


