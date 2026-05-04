"""
URL configuration for the exams app.
"""

from django.urls import path
from . import views

urlpatterns = [
    # ── Authentication ───────────────────────────
    path('', views.LoginView.as_view(), name='home'),
    path('register/', views.RegisterView.as_view(), name='register'),
    path('login/', views.LoginView.as_view(), name='login'),
    path('logout/', views.LogoutView.as_view(), name='logout'),
    path('forgot-password/', views.ForgotPasswordView.as_view(), name='forgot_password'),
    path('verify-otp/', views.VerifyOTPView.as_view(), name='verify_otp'),
    path('reset-password/', views.ResetPasswordView.as_view(), name='reset_password'),
    path('dashboard/', views.dashboard_redirect, name='dashboard'),

    # ── Student Interface ────────────────────────
    path('student/', views.StudentDashboardView.as_view(), name='student_dashboard'),
    path('student/profile/', views.StudentProfileView.as_view(), name='student_profile'),
    path('student/categories/', views.StudentCategoriesView.as_view(), name='student_categories'),
    path('student/request-exam/', views.RequestExamView.as_view(), name='request_exam'),
    path('student/exam/<uuid:paper_id>/', views.TakeExamView.as_view(), name='take_exam'),
    path('student/exam-complete/', views.ExamCompleteView.as_view(), name='exam_complete'),
    path('student/history/', views.StudentHistoryView.as_view(), name='student_history'),
    path('student/notifications/', views.StudentNotificationsView.as_view(), name='student_notifications'),

    # ── Notification actions (shared) ────────────
    path('notifications/fetch/', views.FetchNotificationsView.as_view(), name='fetch_notifications'),
    path('notifications/<uuid:notification_id>/read/', views.MarkNotificationReadView.as_view(), name='mark_notification_read'),
    path('notifications/<uuid:notification_id>/delete/', views.DeleteNotificationView.as_view(), name='delete_notification'),
    path('notifications/mark-all-read/', views.MarkAllNotificationsReadView.as_view(), name='mark_all_read'),

    # ── Admin Dashboard ──────────────────────────
    path('admin-panel/', views.AdminDashboardView.as_view(), name='admin_dashboard'),
    path('admin-panel/categories/', views.AdminCategoriesView.as_view(), name='admin_categories'),
    path('admin-panel/categories/add/', views.AdminAddCategoryView.as_view(), name='admin_add_category'),
    path('admin-panel/categories/<int:pk>/', views.AdminCategoryDetailView.as_view(), name='admin_category_detail'),
    path('admin-panel/categories/<int:pk>/edit/', views.AdminEditCategoryView.as_view(), name='admin_edit_category'),
    path('admin-panel/categories/<int:pk>/delete/', views.AdminDeleteCategoryView.as_view(), name='admin_delete_category'),
    path('admin-panel/categories/<int:pk>/toggle/', views.AdminToggleCategoryStatusView.as_view(), name='admin_toggle_category'),
    path('admin-panel/students/', views.AdminStudentsView.as_view(), name='admin_students'),
    path('admin-panel/students/<int:pk>/', views.AdminStudentDetailView.as_view(), name='admin_student_detail'),
    path('admin-panel/students/<int:pk>/delete/', views.AdminDeleteStudentView.as_view(), name='admin_delete_student'),
    path('admin-panel/questions/', views.AdminQuestionsView.as_view(), name='admin_questions'),
    path('admin-panel/questions/add/', views.AdminAddQuestionView.as_view(), name='admin_add_question'),
    path('admin-panel/questions/add/<int:category_id>/', views.AdminAddQuestionView.as_view(), name='admin_add_question_to_category'),
    path('admin-panel/questions/import/', views.AdminImportQuestionsView.as_view(), name='admin_import_questions'),
    path('admin-panel/questions/import/<int:category_id>/', views.AdminImportQuestionsView.as_view(), name='admin_import_questions_to_category'),
    path('admin-panel/questions/<uuid:pk>/view/', views.AdminQuestionDetailView.as_view(), name='admin_view_question'),
    path('admin-panel/questions/<uuid:pk>/edit/', views.AdminEditQuestionView.as_view(), name='admin_edit_question'),
    path('admin-panel/questions/<uuid:pk>/delete/', views.AdminDeleteQuestionView.as_view(), name='admin_delete_question'),
    path('admin-panel/requests/', views.AdminExamRequestsView.as_view(), name='admin_exam_requests'),
    path('admin-panel/requests/<uuid:request_id>/approve/', views.AdminApproveRequestView.as_view(), name='admin_approve_request'),
    path('admin-panel/requests/<uuid:request_id>/reject/', views.AdminRejectRequestView.as_view(), name='admin_reject_request'),
    path('admin-panel/requests/bulk-action/', views.AdminBulkRequestActionView.as_view(), name='admin_bulk_request_action'),
    path('admin-panel/results/', views.AdminResultsView.as_view(), name='admin_results'),
    path('admin-panel/results/<uuid:pk>/', views.AdminResultDetailView.as_view(), name='admin_result_detail'),
    path('admin-panel/notifications/', views.AdminNotificationsView.as_view(), name='admin_notifications'),
    path('preview-certificate/', views.PreviewCertificateView.as_view(), name='preview_certificate'),
]
