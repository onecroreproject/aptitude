"""
Minimal admin registration — the actual admin interface is custom-built.
This file only registers models so they appear in Django's built-in admin
for emergency/debugging access by the superuser.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import (
    CustomUser,
    Question,
    ExamPaper,
    ExamPaperQuestion,
    StudentExamResult,
    StudentAnswer,
    ExamRequest,
    Notification,
)


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'name', 'role', 'is_superuser', 'is_active')
    list_filter = ('role', 'is_superuser', 'is_active')
    search_fields = ('username', 'email', 'name')
    fieldsets = UserAdmin.fieldsets + (
        ('Profile', {'fields': ('role', 'name', 'phone_number', 'profile_photo', 'date_of_birth', 'address', 'institution')}),
    )


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('question_text', 'category', 'difficulty', 'question_type', 'marks', 'time_limit_minutes', 'is_active')
    list_filter = ('category', 'difficulty', 'question_type', 'is_active')
    search_fields = ('question_text', 'category')


@admin.register(ExamPaper)
class ExamPaperAdmin(admin.ModelAdmin):
    list_display = ('id', 'student', 'total_marks', 'total_duration_minutes', 'created_at')
    list_filter = ('created_at',)


@admin.register(ExamRequest)
class ExamRequestAdmin(admin.ModelAdmin):
    list_display = ('id', 'student', 'status', 'requested_at', 'reviewed_at')
    list_filter = ('status',)


@admin.register(StudentExamResult)
class StudentExamResultAdmin(admin.ModelAdmin):
    list_display = ('id', 'student', 'status', 'total_marks_obtained', 'total_marks_possible', 'started_at')
    list_filter = ('status',)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('title', 'recipient', 'notification_type', 'is_read', 'created_at')
    list_filter = ('notification_type', 'is_read')


admin.site.register(ExamPaperQuestion)
admin.site.register(StudentAnswer)
