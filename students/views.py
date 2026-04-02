from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from .models import CustomUser, OTP, Course, Question, Result, Certificate
from .utils import send_otp_email
import random

def register_view(request):
    if request.method == 'POST':
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        username = request.POST.get('username')
        email = request.POST.get('email')
        mobile = request.POST.get('mobile')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')

        if password != confirm_password:
            messages.error(request, 'Passwords do not match!')
            return render(request, 'students/auth/register.html')

        if CustomUser.objects.filter(email=email).exists() or CustomUser.objects.filter(username=username).exists():
            messages.error(request, 'Email/Username already registered!')
            return render(request, 'students/auth/register.html')

        # Store in session
        otp_code = OTP.generate_otp()
        request.session['reg_data'] = {
            'first_name': first_name,
            'last_name': last_name,
            'username': username,
            'email': email,
            'mobile': mobile,
            'password': password,
        }
        
        # Save OTP to DB
        OTP.objects.create(user_email=email, otp_code=otp_code)
        
        # Send Email
        try:
            send_otp_email(email, otp_code)
            messages.success(request, 'Verification OTP sent to your email!')
            return redirect('verify_otp')
        except Exception as e:
            messages.error(request, f'Error sending email: {str(e)}')
            return render(request, 'students/auth/register.html')

    return render(request, 'students/auth/register.html')

def verify_otp_view(request):
    reg_data = request.session.get('reg_data')
    if not reg_data:
        messages.error(request, 'No registration data found!')
        return redirect('register')

    if request.method == 'POST':
        otp_entered = request.POST.get('otp')
        try:
            otp_obj = OTP.objects.filter(user_email=reg_data['email'], otp_code=otp_entered).last()
            if otp_obj and not otp_obj.is_expired():
                # Create user
                user = CustomUser.objects.create_user(
                    username=reg_data['username'],
                    email=reg_data['email'],
                    password=reg_data['password'],
                    first_name=reg_data['first_name'],
                    last_name=reg_data['last_name'],
                    mobile=reg_data['mobile']
                )
                otp_obj.is_verified = True
                otp_obj.save()
                
                # Send Registration Confirmed Email
                from django.core.mail import send_mail
                from django.conf import settings
                subject = 'Welcome to AptiPro - Registration Confirmed'
                message = f'Hi {user.first_name},\n\nYour registration on AptiPro is confirmed. You can now log in and start taking exams.\n\nBest regards,\nAptiPro Team'
                send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email])
                
                del request.session['reg_data']
                messages.success(request, 'Account created successfully! You can now log in.')
                return redirect('login')
            else:
                messages.error(request, 'Invalid or expired OTP!')
        except Exception as e:
            messages.error(request, f'Error: {str(e)}')

    return render(request, 'students/auth/verify_otp.html')

def login_view(request):
    if request.method == 'POST':
        identifier = request.POST.get('identifier') # email or username
        password = request.POST.get('password')
        
        # Try email first
        user = authenticate(request, email=identifier, password=password)
        if not user:
            # Try username
            try:
                username_user = CustomUser.objects.get(username=identifier)
                user = authenticate(request, email=username_user.email, password=password)
            except CustomUser.DoesNotExist:
                pass

        if user:
            login(request, user)
            if user.is_superuser or user.is_staff:
                return redirect('admin_dashboard')
            return redirect('student_dashboard')
        else:
            messages.error(request, 'Invalid credentials!')

    return render(request, 'students/auth/login.html')

def logout_view(request):
    logout(request)
    return redirect('login')

@login_required
def student_dashboard(request):
    if request.user.is_superuser or request.user.is_staff:
        return redirect('admin_dashboard')
    
    attempts = Result.objects.filter(user=request.user)
    certificates = Certificate.objects.filter(result__user=request.user)
    available_exams = Course.objects.all().count()
    
    context = {
        'total_exams': attempts.count(),
        'available_count': available_exams,
        'certificates_count': certificates.count(),
        'recent_attempts': attempts.order_by('-attempt_date')[:5]
    }
    return render(request, 'students/dashboard.html', context)

@login_required
def available_exams(request):
    courses = Course.objects.all().order_by('-created_at')
    return render(request, 'students/exams/available.html', {'courses': courses})

@login_required
def take_exam(request, course_id):
    course = get_object_or_404(Course, id=course_id)
    questions = Question.objects.filter(course=course).order_by('?')[:course.num_questions]
    
    if request.method == 'POST':
        # Submit logic
        score = 0
        total_marks = 0
        for q in questions:
            ans = request.POST.get(f'q_{q.id}')
            if ans and int(ans) == q.correct_answer:
                score += q.marks
            total_marks += q.marks
        
        percentage = (score / total_marks) * 100 if total_marks > 0 else 0
        pass_status = percentage >= 60
        
        result = Result.objects.create(
            user=request.user,
            course=course,
            score=score,
            total_marks=total_marks,
            percentage=percentage,
            pass_status=pass_status
        )
        
        # Auto-generate certificate if passed
        if pass_status:
            import uuid
            from .utils import generate_qr_code
            cert_id = f"CERT-{uuid.uuid4().hex[:8].upper()}"
            qr_content = f"Name: {request.user.get_full_name()}\nCourse: {course.name}\nScore: {percentage:.1f}%"
            qr_file = generate_qr_code(qr_content)
            
            cert = Certificate.objects.create(result=result, certificate_id=cert_id)
            cert.qr_code.save(f"{cert_id}.png", qr_file)
            
            # Send Email
            from django.core.mail import send_mail
            from django.conf import settings
            subject = f'Congratulations! You passed the {course.name} exam'
            message = f'Hi {request.user.first_name}, you passed the {course.name} exam with {percentage:.1f}%. Your certificate ID is {cert_id}.'
            send_mail(subject, message, settings.EMAIL_BACKEND, [request.user.email])

        messages.success(request, 'Exam submitted successfully!')
        return redirect('view_result', result_id=result.id)

    return render(request, 'students/exams/take_exam.html', {'course': course, 'questions': questions})

@login_required
def view_result(request, result_id):
    result = get_object_or_404(Result, id=result_id, user=request.user)
    return render(request, 'students/exams/result_detail.html', {'result': result})

@login_required
def student_results(request):
    results = Result.objects.filter(user=request.user).order_by('-attempt_date')
    return render(request, 'students/exams/history.html', {'results': results})

@login_required
def student_certificates(request):
    certificates = Certificate.objects.filter(result__user=request.user).order_by('-issued_at')
    return render(request, 'students/exams/certificates.html', {'certificates': certificates})

@login_required
def profile_view(request):
    if request.method == 'POST':
        request.user.mobile = request.POST.get('mobile')
        if 'profile_pic' in request.FILES:
            request.user.profile_pic = request.FILES['profile_pic']
        request.user.save()
        messages.success(request, 'Profile updated!')
        return redirect('profile')
    return render(request, 'students/profile.html')
