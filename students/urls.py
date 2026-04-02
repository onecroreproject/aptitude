from django.urls import path
from . import views

urlpatterns = [
    path('register/', views.register_view, name='register'),
    path('verify-otp/', views.verify_otp_view, name='verify_otp'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    
    path('', views.student_dashboard, name='student_dashboard'),
    path('exams/', views.available_exams, name='available_exams'),
    path('exams/take/<int:course_id>/', views.take_exam, name='take_exam'),
    path('exams/result/<int:result_id>/', views.view_result, name='view_result'),
    path('results/', views.student_results, name='student_results'),
    path('certificates/', views.student_certificates, name='student_certificates'),
    path('profile/', views.profile_view, name='profile'),
]
