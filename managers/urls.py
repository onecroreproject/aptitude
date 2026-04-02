from django.urls import path
from . import views

urlpatterns = [
    path('', views.admin_dashboard, name='admin_dashboard'),
    path('students/', views.student_management, name='student_management'),
    path('students/delete/<int:user_id>/', views.reject_user, name='reject_user'),
    path('courses/', views.course_management, name='course_management'),
    path('courses/edit/<int:course_id>/', views.edit_course, name='edit_course'),
    path('courses/delete/<int:course_id>/', views.delete_course, name='delete_course'),
    path('courses/questions/<int:course_id>/', views.view_course_questions, name='view_course_questions'),
    path('questions/edit/<int:q_id>/', views.edit_question, name='edit_question'),
    path('questions/delete/<int:q_id>/', views.delete_question, name='delete_question'),
    path('questions/bulk-delete/', views.bulk_delete_questions, name='bulk_delete_questions'),
    path('results/', views.admin_results, name='admin_results'),
    path('certificates/', views.certificate_management, name='certificate_management'),
]
