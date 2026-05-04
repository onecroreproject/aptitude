"""
Online Examination System — Complete Views Layer
=================================================
Covers both the student-facing interface and the custom admin dashboard.
All admin views are gated by SuperuserRequiredMixin (is_superuser=True).
All student views are gated by StudentRequiredMixin.
"""

import json
from django.contrib import messages
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.mail import send_mail
from django.conf import settings
from django.db.models import Avg, Count, Sum, Q, F
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views import View
from django.views.generic import TemplateView, ListView, DetailView

from .forms import (
    StudentRegistrationForm,
    CustomLoginForm,
    StudentProfileForm,
    CategoryForm,
    QuestionForm,
    ExamRequestForm,
    ExcelImportForm,
    ExamRequestReviewForm,
    ForgotPasswordForm,
    OTPVerificationForm,
    ResetPasswordForm,
)
from .mixins import SuperuserRequiredMixin, StudentRequiredMixin
from .models import (
    CustomUser,
    Category,
    Question,
    ExamPaper,
    ExamPaperQuestion,
    StudentExamResult,
    StudentAnswer,
    ExamRequest,
    Notification,
    OTP,
)
from .utils import import_questions_from_excel, generate_exam_paper, submit_and_evaluate


# ════════════════════════════════════════════════
#  AUTHENTICATION VIEWS
# ════════════════════════════════════════════════

class RegisterView(View):
    """Student registration — creates user with role=Student."""

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('student_dashboard' if not request.user.is_superuser else 'admin_dashboard')
        response = super().dispatch(request, *args, **kwargs)
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        return response

    def get(self, request):
        form = StudentRegistrationForm()
        return render(request, 'exams/register.html', {'form': form})

    def post(self, request):
        form = StudentRegistrationForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Registration successful! Welcome aboard.')
            return redirect('student_dashboard')
        return render(request, 'exams/register.html', {'form': form})


class LoginView(View):
    """Login view — routes to appropriate dashboard based on role."""

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('student_dashboard' if not request.user.is_superuser else 'admin_dashboard')
        response = super().dispatch(request, *args, **kwargs)
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        return response

    def get(self, request):
        form = CustomLoginForm()
        return render(request, 'exams/login.html', {'form': form})

    def post(self, request):
        form = CustomLoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f'Welcome back, {user.username}!')
            if user.is_superuser:
                return redirect('admin_dashboard')
            return redirect('student_dashboard')
        return render(request, 'exams/login.html', {'form': form})


class LogoutView(View):
    """Logout and redirect to login."""
    def get(self, request):
        logout(request)
        messages.info(request, 'You have been logged out.')
        return redirect('login')

    def post(self, request):
        logout(request)
        return redirect('login')


class ForgotPasswordView(View):
    """Initial step: user enters email to receive an OTP."""
    def get(self, request):
        form = ForgotPasswordForm()
        return render(request, 'exams/forgot_password.html', {'form': form})

    def post(self, request):
        form = ForgotPasswordForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            user = CustomUser.objects.get(email=email)
            
            # Generate 6-digit random OTP
            import random
            otp_code = ''.join([str(random.randint(0, 9)) for _ in range(6)])
            
            # Save OTP to DB
            OTP.objects.create(user=user, code=otp_code)
            
            # Send Email
            subject = f"Your {settings.DEFAULT_FROM_EMAIL.split('@')[0]} Password Reset OTP"
            # Actually use 'Aptipro' here as requested
            subject = "Aptipro Password Reset OTP"
            message = f"Hello {user.username},\n\nYour OTP for resetting your password is: {otp_code}\n\nThis OTP is valid for 10 minutes.\n\nRegards,\nAptipro Team"
            
            try:
                send_mail(
                    subject,
                    message,
                    settings.DEFAULT_FROM_EMAIL,
                    [email],
                    fail_silently=False,
                )
                messages.success(request, f"An OTP has been sent to {email}.")
                request.session['reset_email'] = email
                return redirect('verify_otp')
            except Exception as e:
                messages.error(request, f"Failed to send email. Please check your SMTP settings. Error: {str(e)}")
                
        return render(request, 'exams/forgot_password.html', {'form': form})


class VerifyOTPView(View):
    """Step 2: user enters the OTP they received."""
    def get(self, request):
        if 'reset_email' not in request.session:
            return redirect('forgot_password')
        form = OTPVerificationForm()
        return render(request, 'exams/verify_otp.html', {'form': form})

    def post(self, request):
        if 'reset_email' not in request.session:
            return redirect('forgot_password')
        
        email = request.session['reset_email']
        user = get_object_or_404(CustomUser, email=email)
        form = OTPVerificationForm(request.POST)
        
        if form.is_valid():
            code = form.cleaned_data['code']
            otp_obj = OTP.objects.filter(user=user, code=code, is_verified=False).last()
            
            if otp_obj and not otp_obj.is_expired():
                otp_obj.is_verified = True
                otp_obj.save()
                messages.success(request, "OTP verified successfully. You can now reset your password.")
                return redirect('reset_password')
            else:
                messages.error(request, "Invalid or expired OTP.")
                
        return render(request, 'exams/verify_otp.html', {'form': form})


class ResetPasswordView(View):
    """Step 3: user sets a new password."""
    def get(self, request):
        if 'reset_email' not in request.session:
            return redirect('forgot_password')
        
        email = request.session['reset_email']
        user = get_object_or_404(CustomUser, email=email)
        # Ensure latest OTP is verified
        otp_obj = OTP.objects.filter(user=user, is_verified=True).last()
        if not otp_obj:
            messages.error(request, "Please verify your OTP first.")
            return redirect('verify_otp')

        form = ResetPasswordForm()
        return render(request, 'exams/reset_password.html', {'form': form})

    def post(self, request):
        if 'reset_email' not in request.session:
            return redirect('forgot_password')
        
        email = request.session['reset_email']
        user = get_object_or_404(CustomUser, email=email)
        otp_obj = OTP.objects.filter(user=user, is_verified=True).last()
        if not otp_obj:
            return redirect('verify_otp')

        form = ResetPasswordForm(request.POST)
        if form.is_valid():
            new_password = form.cleaned_data['password']
            user.set_password(new_password)
            user.save()
            
            # For security, invalidate the session and session hash
            update_session_auth_hash(request, user)
            
            # Clean up session
            del request.session['reset_email']
            
            messages.success(request, "Your password has been reset successfully. You can now log in.")
            return redirect('login')
            
        return render(request, 'exams/reset_password.html', {'form': form})


@login_required
def dashboard_redirect(request):
    """Route /dashboard/ to the correct interface based on role."""
    if request.user.is_superuser:
        return redirect('admin_dashboard')
    return redirect('student_dashboard')


# ════════════════════════════════════════════════
#  STUDENT VIEWS
# ════════════════════════════════════════════════

class StudentDashboardView(StudentRequiredMixin, TemplateView):
    """Student home page — shows exam status, notifications, request CTA."""
    template_name = 'exams/student/dashboard.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user

        # Exam requests
        ctx['pending_requests'] = ExamRequest.objects.filter(
            student=user, status='Pending'
        ).count()
        ctx['approved_requests'] = ExamRequest.objects.filter(
            student=user, status='Approved'
        )
        ctx['recent_requests'] = ExamRequest.objects.filter(
            student=user
        ).order_by('-requested_at')[:5]

        # Active exams (approved but not yet taken)
        taken_paper_ids = StudentExamResult.objects.filter(
            student=user
        ).values_list('exam_paper_id', flat=True)
        ctx['available_exams'] = ExamPaper.objects.filter(
            student=user,
            category__is_active=True
        ).exclude(id__in=taken_paper_ids)

        # Completed exams count (students see only "Test Completed")
        ctx['completed_exams'] = StudentExamResult.objects.filter(
            student=user, status__in=['Submitted', 'Evaluated']
        ).count()

        # Unread notifications
        ctx['unread_count'] = Notification.unread_count(user) or 0
        ctx['notifications'] = Notification.objects.filter(
            recipient=user
        ).order_by('-created_at')[:10]

        # Active categories for the request modal
        ctx['active_categories'] = Category.objects.filter(is_active=True).order_by('name')

        return ctx


class StudentProfileView(StudentRequiredMixin, View):
    """View and update student profile."""

    def get(self, request):
        form = StudentProfileForm(instance=request.user)
        return render(request, 'exams/student/profile.html', {'form': form})

    def post(self, request):
        form = StudentProfileForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully.')
            return redirect('student_profile')
        return render(request, 'exams/student/profile.html', {'form': form})


class RequestExamView(StudentRequiredMixin, View):
    """Student submits an exam access request for a specific category."""

    def post(self, request):
        form = ExamRequestForm(request.POST)
        if form.is_valid():
            category = form.cleaned_data['category']
            user = request.user
            
            # 1. Block if there is already a Pending request for this category
            if ExamRequest.objects.filter(student=user, category=category, status='Pending').exists():
                messages.warning(request, f'You already have a pending request for {category.name}.')
                return redirect('student_dashboard')

            # 2. If they have an Approved request but no result yet (Unattended)
            # We still allow a re-request if they feel they need a new approval/paper
            # per user requirement: "must again send a request"

            # 3. Check if they have already passed — per spec, re-exam is for those who "do not pass"
            # But the user also mentions "does not attend".
            last_result = StudentExamResult.objects.filter(
                student=user, exam_paper__category=category
            ).order_by('-submitted_at').first()
            
            if last_result and last_result.status == 'Evaluated' and last_result.is_passed():
                # They passed already. Still allow? User's "does not pass" implies failure.
                # I'll allow but show a specific info message.
                pass 
                
            ExamRequest.objects.create(
                student=user,
                category=category
            )
            messages.success(request, f'Request for {category.name} submitted! Please wait for admin approval.')
        else:
            messages.error(request, 'Please select a valid category.')
            
        return redirect('student_dashboard')


class StudentCategoriesView(StudentRequiredMixin, ListView):
    """List all categories for students with contextual actions (Request/Retest/Start)."""
    template_name = 'exams/student/categories.html'
    context_object_name = 'categories'
    
    def get_queryset(self):
        return Category.objects.filter(is_active=True).annotate(
            q_count=Count('questions', filter=Q(questions__is_active=True))
        ).order_by('name')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Pending requests
        ctx['pending_cat_ids'] = list(ExamRequest.objects.filter(
            student=user, status='Pending'
        ).values_list('category_id', flat=True))
        
        # Approved but not taken (Access Granted)
        # We define "not taken" as having an active paper without a submitted result
        untaken_papers = ExamPaper.objects.filter(
            student=user
        ).exclude(
            result__status__in=['Submitted', 'Evaluated']
        ).values('category_id', 'id')
        
        # Build a map for easy lookup
        paper_map = {p['category_id']: p['id'] for p in untaken_papers}

        # Inject paper_id into categories for the template
        for cat in ctx['categories']:
            cat.paper_id = paper_map.get(cat.id)
        
        # Categories already attempted (to show "Retest" vs "Request")
        completed_cat_ids = StudentExamResult.objects.filter(
            student=user,
            status__in=['Submitted', 'Evaluated']
        ).values_list('exam_paper__category_id', flat=True).distinct()
        ctx['completed_cat_ids'] = list(completed_cat_ids)
        
        # Identify failed categories explicitly
        # This is a bit complex in one line, so we do it in a loop or filtered list
        results = StudentExamResult.objects.filter(student=user, status='Evaluated')
        failed_cat_ids = []
        for r in results:
            if not r.is_passed():
                failed_cat_ids.append(r.exam_paper.category_id)
        ctx['failed_cat_ids'] = list(set(failed_cat_ids))

        return ctx


class TakeExamView(StudentRequiredMixin, View):
    """Student takes an exam — shows question paper."""

    def get(self, request, paper_id):
        paper = get_object_or_404(ExamPaper, id=paper_id, student=request.user)

        # Check if already submitted or evaluated
        if StudentExamResult.objects.filter(
            exam_paper=paper, 
            status__in=[StudentExamResult.Status.SUBMITTED, StudentExamResult.Status.EVALUATED]
        ).exists():
            messages.warning(request, 'You have already completed this exam.')
            return redirect('student_dashboard')

        # Create result record (In Progress)
        result, created = StudentExamResult.objects.get_or_create(
            student=request.user,
            exam_paper=paper,
            defaults={
                'total_marks_possible': paper.total_marks,
                'status': StudentExamResult.Status.IN_PROGRESS,
            }
        )

        questions = paper.paper_questions.select_related('question').order_by('order')
        response = render(request, 'exams/student/take_exam.html', {
            'paper': paper,
            'questions': questions,
            'result': result,
        })
        # Prevent caching test questions
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        return response

    def post(self, request, paper_id):
        paper = get_object_or_404(ExamPaper, id=paper_id, student=request.user)
        result = get_object_or_404(
            StudentExamResult,
            exam_paper=paper,
            student=request.user,
            status=StudentExamResult.Status.IN_PROGRESS,
        )

        # Save all answers
        questions = paper.paper_questions.select_related('question').order_by('order')
        answers_to_create = []
        for pq in questions:
            answer_text = request.POST.get(f'answer_{pq.question.id}', '').strip()
            answers_to_create.append(
                StudentAnswer(
                    result=result,
                    question=pq.question,
                    student_answer=answer_text,
                )
            )

        if answers_to_create:
            StudentAnswer.objects.bulk_create(answers_to_create, ignore_conflicts=True)

        # Submit and auto-evaluate
        result.submitted_at = timezone.now()
        result.status = StudentExamResult.Status.SUBMITTED
        result.save(update_fields=['submitted_at', 'status'])
        result.auto_evaluate()

        messages.success(request, 'Test Completed! Your responses have been submitted.')
        return redirect('exam_complete')


class ExamCompleteView(StudentRequiredMixin, TemplateView):
    """Shows "Test Completed" message — no scores visible to students."""
    template_name = 'exams/student/exam_complete.html'

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        # Prevent back-navigation to the test from here
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        return response


class StudentHistoryView(StudentRequiredMixin, ListView):
    """Student's past exam attempts & performance."""
    template_name = 'exams/student/history.html'
    context_object_name = 'results'

    def get_queryset(self):
        return StudentExamResult.objects.filter(
            student=self.request.user,
            status__in=['Submitted', 'Evaluated']
        ).select_related('exam_paper__category').order_by('-submitted_at')


class StudentNotificationsView(StudentRequiredMixin, ListView):
    """Student notification list."""
    template_name = 'exams/student/notifications.html'
    context_object_name = 'notifications'
    paginate_by = 20

    def get_queryset(self):
        return Notification.objects.filter(
            recipient=self.request.user
        ).order_by('-created_at')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['unread_count'] = Notification.unread_count(self.request.user)
        return ctx


class MarkNotificationReadView(LoginRequiredMixin, View):
    """AJAX endpoint to mark a notification as read."""

    def post(self, request, notification_id):
        notif = get_object_or_404(
            Notification, id=notification_id, recipient=request.user
        )
        notif.mark_as_read()
        return JsonResponse({'status': 'ok'})


class MarkAllNotificationsReadView(LoginRequiredMixin, View):
    """Mark all notifications read for the current user."""

    def post(self, request):
        Notification.mark_all_read(request.user)
        messages.success(request, 'All notifications marked as read.')
        if request.user.is_superuser:
            return redirect('admin_notifications')
        return redirect('student_notifications')


class FetchNotificationsView(LoginRequiredMixin, View):
    """JSON API to fetch latest unread notifications for the dropdown."""
    def get(self, request):
        count = Notification.unread_count(request.user)
        latest = Notification.objects.filter(
            recipient=request.user, 
            is_read=False
        ).order_by('-created_at')[:5]
        
        data = {
            'count': count,
            'notifications': [
                {
                    'id': str(n.id),
                    'title': n.title,
                    'message': n.message,
                    'created_at': n.created_at.strftime('%I:%M %p'),
                    'type': n.notification_type
                } for n in latest
            ]
        }
        return JsonResponse(data)


class DeleteNotificationView(LoginRequiredMixin, View):
    """Delete a specific notification."""
    def post(self, request, notification_id):
        notif = get_object_or_404(
            Notification, id=notification_id, recipient=request.user
        )
        notif.delete()
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'status': 'ok'})
            
        messages.success(request, 'Notification deleted.')
        if request.user.is_superuser:
            return redirect('admin_notifications')
        return redirect('student_notifications')


# ════════════════════════════════════════════════
#  ADMIN DASHBOARD VIEWS (SUPERUSER ONLY)
# ════════════════════════════════════════════════

class AdminDashboardView(SuperuserRequiredMixin, TemplateView):
    """Admin dashboard home — overview analytics."""
    template_name = 'exams/admin/dashboard.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        # Counts
        ctx['total_students'] = CustomUser.objects.filter(role='Student').count()
        ctx['total_questions'] = Question.objects.filter(is_active=True).count()
        ctx['total_exams'] = StudentExamResult.objects.count()
        ctx['pending_requests'] = ExamRequest.objects.filter(status='Pending').count()

        # Recent requests
        ctx['recent_requests'] = ExamRequest.objects.select_related(
            'student'
        ).order_by('-requested_at')[:5]

        # Recent results
        ctx['recent_results'] = StudentExamResult.objects.select_related(
            'student', 'exam_paper'
        ).filter(status='Evaluated').order_by('-completed_at')[:5]

        # Pass/fail stats
        evaluated = StudentExamResult.objects.filter(status='Evaluated')
        total_evaluated = evaluated.count()
        if total_evaluated > 0:
            passed = sum(1 for r in evaluated.only(
                'total_marks_obtained', 'total_marks_possible'
            ) if r.is_passed())
            ctx['pass_rate'] = round((passed / total_evaluated) * 100, 1)
            ctx['fail_rate'] = round(100 - ctx['pass_rate'], 1)
        else:
            ctx['pass_rate'] = 0
            ctx['fail_rate'] = 0

        # Average score
        avg = evaluated.aggregate(avg_score=Avg('total_marks_obtained'))
        ctx['avg_score'] = round(avg['avg_score'] or 0, 1)

        # Unread notifications
        ctx['unread_count'] = Notification.unread_count(self.request.user)

        # Question categories for chart
        categories = Question.objects.filter(is_active=True).values(
            'category__name'
        ).annotate(count=Count('id')).order_by('-count')[:10]
        ctx['category_labels'] = json.dumps([c['category__name'] for c in categories])
        ctx['category_data'] = json.dumps([c['count'] for c in categories])

        # Difficulty distribution
        difficulties = Question.objects.filter(is_active=True).values(
            'difficulty'
        ).annotate(count=Count('id'))
        diff_dict = {d['difficulty']: d['count'] for d in difficulties}
        ctx['difficulty_data'] = json.dumps([
            diff_dict.get('Easy', 0),
            diff_dict.get('Medium', 0),
            diff_dict.get('Hard', 0),
        ])

        return ctx


class AdminStudentsView(SuperuserRequiredMixin, ListView):
    """View all students with full profile details."""
    template_name = 'exams/admin/students.html'
    context_object_name = 'students'
    paginate_by = 20

    def get_queryset(self):
        qs = CustomUser.objects.filter(role='Student').order_by('-date_joined')
        search = self.request.GET.get('search', '').strip()
        min_pct = self.request.GET.get('min_percentage', '').strip()

        if search:
            qs = qs.filter(
                Q(username__icontains=search) |
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search) |
                Q(email__icontains=search) |
                Q(institution__icontains=search)
            )

        if min_pct:
            try:
                val = float(min_pct)
                from django.db.models.functions import Cast
                from django.db.models import FloatField
                valid_student_ids = StudentExamResult.objects.filter(
                    total_marks_possible__gt=0
                ).annotate(
                    calc_pct=Cast(F('total_marks_obtained'), FloatField()) * 100 / Cast(F('total_marks_possible'), FloatField())
                ).filter(calc_pct__gte=val).values_list('student_id', flat=True)
                qs = qs.filter(id__in=valid_student_ids)
            except ValueError:
                pass

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['search'] = self.request.GET.get('search', '')
        ctx['min_percentage'] = self.request.GET.get('min_percentage', '')
        ctx['total_students'] = self.get_queryset().count()
        return ctx


class AdminStudentDetailView(SuperuserRequiredMixin, DetailView):
    """Full student profile visible to admin."""
    template_name = 'exams/admin/student_detail.html'
    context_object_name = 'student'

    def get_queryset(self):
        return CustomUser.objects.filter(role='Student')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        student = self.object

        # Exam history with results
        ctx['exam_results'] = StudentExamResult.objects.filter(
            student=student
        ).select_related('exam_paper').order_by('-started_at')

        # Request history
        ctx['exam_requests'] = ExamRequest.objects.filter(
            student=student
        ).order_by('-requested_at')

        return ctx


class AdminDeleteStudentView(SuperuserRequiredMixin, View):
    """Safely delete a student and all related records (cascade handled by DB)."""
    def post(self, request, pk):
        student = get_object_or_404(CustomUser, pk=pk, role='Student')
        username = student.username
        student.delete()
        messages.success(request, f'Student "{username}" has been removed from the platform.')
        return redirect('admin_students')


class AdminQuestionsView(SuperuserRequiredMixin, ListView):
    """Question bank management."""
    template_name = 'exams/admin/questions.html'
    context_object_name = 'questions'
    paginate_by = 25

    def get_queryset(self):
        qs = Question.objects.filter(is_active=True).order_by('-created_at')
        category = self.request.GET.get('category', '').strip()
        difficulty = self.request.GET.get('difficulty', '').strip()
        q_type = self.request.GET.get('type', '').strip()
        search = self.request.GET.get('search', '').strip()

        if category:
            qs = qs.filter(category=category)
        if difficulty:
            qs = qs.filter(difficulty=difficulty)
        if q_type:
            qs = qs.filter(question_type=q_type)
        if search:
            qs = qs.filter(question_text__icontains=search)

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['categories'] = Category.objects.all().order_by('name')
        ctx['difficulties'] = Question.Difficulty.choices
        ctx['question_types'] = Question.QuestionType.choices
        ctx['current_category'] = self.request.GET.get('category', '')
        ctx['current_difficulty'] = self.request.GET.get('difficulty', '')
        ctx['current_type'] = self.request.GET.get('type', '')
        ctx['search'] = self.request.GET.get('search', '')
        ctx['total_questions'] = Question.objects.filter(is_active=True).count()
        return ctx


class AdminCategoryDetailView(SuperuserRequiredMixin, ListView):
    """View all questions within a specific category."""
    template_name = 'exams/admin/category_detail.html'
    context_object_name = 'questions'
    paginate_by = 25

    def get_queryset(self):
        self.category = get_object_or_404(Category, pk=self.kwargs['pk'])
        qs = Question.objects.filter(category=self.category, is_active=True).order_by('-created_at')
        
        # Simple search within category
        search = self.request.GET.get('search', '').strip()
        if search:
            qs = qs.filter(question_text__icontains=search)
            
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['category'] = self.category
        ctx['search'] = self.request.GET.get('search', '')
        return ctx


class AdminAddQuestionView(SuperuserRequiredMixin, View):
    """Add individual question, optionally pre-selecting a category."""

    def get(self, request, category_id=None):
        initial = {}
        if category_id:
            category = get_object_or_404(Category, pk=category_id)
            initial['category'] = category
            
        form = QuestionForm(initial=initial)
        return render(request, 'exams/admin/add_question.html', {
            'form': form,
            'category_id': category_id
        })

    def post(self, request, category_id=None):
        form = QuestionForm(request.POST)
        if form.is_valid():
            q = form.save(commit=False)
            q.created_by = request.user
            q.save()
            messages.success(request, 'Question added successfully.')
            
            # If we came from a category detail page, go back there
            if category_id:
                return redirect('admin_category_detail', pk=category_id)
            return redirect('admin_questions')
            
        return render(request, 'exams/admin/add_question.html', {
            'form': form,
            'category_id': category_id
        })


class AdminImportQuestionsView(SuperuserRequiredMixin, View):
    """Bulk import questions, optionally forcing a specific category."""

    def get(self, request, category_id=None):
        category = None
        if category_id:
            category = get_object_or_404(Category, pk=category_id)
            
        form = ExcelImportForm()
        return render(request, 'exams/admin/import_questions.html', {
            'form': form,
            'category': category
        })

    def post(self, request, category_id=None):
        category = None
        if category_id:
            category = get_object_or_404(Category, pk=category_id)
            
        form = ExcelImportForm(request.POST, request.FILES)
        if form.is_valid():
            result = import_questions_from_excel(
                request.FILES['excel_file'],
                created_by=request.user,
                forced_category=category
            )
            
            if result['created_count'] > 0:
                messages.success(
                    request,
                    f"Successfully imported {result['created_count']} questions."
                )
            if result['error_count'] > 0:
                messages.warning(
                    request,
                    f"{result['error_count']} rows had errors and were skipped."
                )
                
            return render(request, 'exams/admin/import_questions.html', {
                'form': ExcelImportForm(),
                'result': result,
                'category': category
            })
        return render(request, 'exams/admin/import_questions.html', {
            'form': form,
            'category': category
        })


class AdminQuestionDetailView(SuperuserRequiredMixin, DetailView):
    """View a single question detail."""
    model = Question
    template_name = 'exams/admin/question_detail.html'
    context_object_name = 'question'


class AdminEditQuestionView(SuperuserRequiredMixin, View):
    """Update an existing question."""

    def get(self, request, pk):
        question = get_object_or_404(Question, pk=pk)
        form = QuestionForm(instance=question)
        return render(request, 'exams/admin/add_question.html', {
            'form': form,
            'edit': True,
            'question': question
        })

    def post(self, request, pk):
        question = get_object_or_404(Question, pk=pk)
        form = QuestionForm(request.POST, instance=question)
        if form.is_valid():
            form.save()
            messages.success(request, 'Question updated successfully.')
            return redirect('admin_category_detail', pk=question.category.pk)
        return render(request, 'exams/admin/add_question.html', {
            'form': form,
            'edit': True,
            'question': question
        })


class AdminDeleteQuestionView(SuperuserRequiredMixin, View):
    """Soft-delete a question."""

    def post(self, request, pk):
        question = get_object_or_404(Question, pk=pk)
        category_id = question.category.pk
        question.is_active = False
        question.save()
        messages.success(request, 'Question removed from question bank.')
        return redirect('admin_category_detail', pk=category_id)


class AdminExamRequestsView(SuperuserRequiredMixin, ListView):
    """Manage exam access requests — filter, approve, reject."""
    template_name = 'exams/admin/exam_requests.html'
    context_object_name = 'requests'
    paginate_by = 20

    def get_queryset(self):
        qs = ExamRequest.objects.select_related('student').order_by('-requested_at')
        status = self.request.GET.get('status', '').strip()
        if status:
            qs = qs.filter(status=status)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['current_status'] = self.request.GET.get('status', '')
        ctx['status_choices'] = ExamRequest.Status.choices
        ctx['pending_count'] = ExamRequest.objects.filter(status='Pending').count()
        return ctx


class AdminApproveRequestView(SuperuserRequiredMixin, View):
    """Approve a single exam request and generate paper."""

    def post(self, request, request_id):
        exam_req = get_object_or_404(ExamRequest, id=request_id, status='Pending')
        exam_req.approve(request.user)

        # Generate randomized paper for the student for the specific category
        try:
            paper = generate_exam_paper(
                student=exam_req.student, 
                category=exam_req.category
            )
            messages.success(
                request,
                f'Request approved and {exam_req.category.name} paper generated for {exam_req.student.username}.'
            )
        except ValueError as e:
            messages.warning(
                request,
                f'Request approved but paper generation failed: {e}. '
                'Please ensure enough questions exist in the selected category.'
            )

        return redirect('admin_exam_requests')


class AdminRejectRequestView(SuperuserRequiredMixin, View):
    """Reject a single exam request with reason."""

    def post(self, request, request_id):
        exam_req = get_object_or_404(ExamRequest, id=request_id, status='Pending')
        reason = request.POST.get('rejection_reason', 'Rejected by admin').strip()
        exam_req.reject(request.user, reason=reason)
        messages.success(request, f'Request from {exam_req.student.username} rejected.')
        return redirect('admin_exam_requests')


class AdminBulkRequestActionView(SuperuserRequiredMixin, View):
    """Bulk approve or reject multiple requests."""

    def post(self, request):
        action = request.POST.get('action', '')
        selected_ids = request.POST.getlist('selected_requests')

        if not selected_ids:
            messages.warning(request, 'No requests selected.')
            return redirect('admin_exam_requests')

        if action == 'approve':
            approved = ExamRequest.bulk_approve(selected_ids, request.user)
            # Generate papers for each approved student
            for req in approved:
                try:
                    generate_exam_paper(student=req.student, category=req.category)
                except ValueError:
                    pass
            messages.success(request, f'{len(approved)} requests approved.')

        elif action == 'reject':
            reason = request.POST.get('bulk_reason', 'Bulk rejection by admin')
            rejected = ExamRequest.bulk_reject(selected_ids, request.user, reason=reason)
            messages.success(request, f'{len(rejected)} requests rejected.')

        return redirect('admin_exam_requests')


class AdminResultsView(SuperuserRequiredMixin, ListView):
    """View all exam results with analytics."""
    template_name = 'exams/admin/results.html'
    context_object_name = 'results'
    paginate_by = 20

    def get_queryset(self):
        qs = StudentExamResult.objects.select_related(
            'student', 'exam_paper'
        ).order_by('-started_at')

        status = self.request.GET.get('status', '').strip()
        search = self.request.GET.get('search', '').strip()
        min_pct = self.request.GET.get('min_percentage', '').strip()

        if status:
            qs = qs.filter(status=status)
        if search:
            qs = qs.filter(
                Q(student__username__icontains=search) |
                Q(student__first_name__icontains=search) |
                Q(student__last_name__icontains=search)
            )
        if min_pct:
            try:
                val = float(min_pct)
                from django.db.models.functions import Cast
                from django.db.models import FloatField
                qs = qs.filter(total_marks_possible__gt=0).annotate(
                    calc_pct=Cast(F('total_marks_obtained'), FloatField()) * 100 / Cast(F('total_marks_possible'), FloatField())
                ).filter(calc_pct__gte=val)
            except ValueError:
                pass
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['status_choices'] = StudentExamResult.Status.choices
        ctx['current_status'] = self.request.GET.get('status', '')
        ctx['search'] = self.request.GET.get('search', '')
        ctx['min_percentage'] = self.request.GET.get('min_percentage', '')

        # Summary stats based on filtered queryset
        qs = self.get_queryset()
        evaluated = qs.filter(status='Evaluated')
        ctx['total_evaluated'] = evaluated.count()
        avg = evaluated.aggregate(avg=Avg('total_marks_obtained'))
        ctx['avg_marks'] = round(avg['avg'] or 0, 1)

        return ctx


class AdminResultDetailView(SuperuserRequiredMixin, DetailView):
    """Detailed result view — question-wise breakdown (admin only)."""
    template_name = 'exams/admin/result_detail.html'
    context_object_name = 'result'

    def get_queryset(self):
        return StudentExamResult.objects.select_related('student', 'exam_paper')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        result = self.object
        ctx['answers'] = result.answers.select_related('question').order_by('question')
        ctx['percentage'] = result.percentage()
        ctx['passed'] = result.is_passed()
        return ctx


class AdminNotificationsView(SuperuserRequiredMixin, ListView):
    """Admin notification management."""
    template_name = 'exams/admin/notifications.html'
    context_object_name = 'notifications'
    paginate_by = 20

    def get_queryset(self):
        return Notification.objects.filter(
            recipient=self.request.user
        ).order_by('-created_at')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['unread_count'] = Notification.unread_count(self.request.user)
        return ctx


# ════════════════════════════════════════════════
#  ADMIN CATEGORY VIEWS
# ════════════════════════════════════════════════

class AdminCategoriesView(SuperuserRequiredMixin, ListView):
    """List all exam categories."""
    template_name = 'exams/admin/categories.html'
    context_object_name = 'categories'
    
    def get_queryset(self):
        return Category.objects.annotate(
            q_count=Count('questions')
        ).order_by('name')


class AdminAddCategoryView(SuperuserRequiredMixin, View):
    """Create a new exam category."""
    
    def get(self, request):
        form = CategoryForm()
        return render(request, 'exams/admin/add_category.html', {'form': form})
        
    def post(self, request):
        form = CategoryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Category created successfully.')
            return redirect('admin_categories')
        return render(request, 'exams/admin/add_category.html', {'form': form})


class AdminEditCategoryView(SuperuserRequiredMixin, View):
    """Update an existing category."""
    
    def get(self, request, pk):
        cat = get_object_or_404(Category, pk=pk)
        form = CategoryForm(instance=cat)
        return render(request, 'exams/admin/add_category.html', {'form': form, 'edit': True})
        
    def post(self, request, pk):
        cat = get_object_or_404(Category, pk=pk)
        form = CategoryForm(request.POST, instance=cat)
        if form.is_valid():
            form.save()
            messages.success(request, 'Category updated successfully.')
            return redirect('admin_categories')
        return render(request, 'exams/admin/add_category.html', {'form': form, 'edit': True})


class AdminDeleteCategoryView(SuperuserRequiredMixin, View):
    """Delete a category (only if no questions linked, else soft error)."""
    
    def post(self, request, pk):
        cat = get_object_or_404(Category, pk=pk)
        if cat.questions.exists() or cat.exam_papers.exists():
            messages.error(request, 'Cannot delete category that has questions or exam papers linked.')
        else:
            cat.delete()
            messages.success(request, 'Category deleted successfully.')
        return redirect('admin_categories')


class AdminToggleCategoryStatusView(SuperuserRequiredMixin, View):
    """Toggle is_active status of a category."""
    
    def post(self, request, pk):
        cat = get_object_or_404(Category, pk=pk)
        cat.is_active = not cat.is_active
        cat.save(update_fields=['is_active'])
        status = 'Activated' if cat.is_active else 'Deactivated'
        messages.success(request, f'Category {cat.name} {status} successfully.')
        return redirect('admin_categories')


class PreviewCertificateView(View):
    """Generates and serves the certificate preview elegantly in HTML or directly as a PNG in the browser."""
    def get(self, request):
        from django.http import HttpResponse

        if request.GET.get('raw') != '1':
            html_content = """
            <!DOCTYPE html>
            <html>
            <head>
                <title>Certificate Preview</title>
                <style>
                    body, html {
                        margin: 0;
                        padding: 0;
                        width: 100%;
                        height: 100%;
                        background-color: #f4f4f4;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        overflow: hidden;
                    }
                    img {
                        max-width: 100vw;
                        max-height: 100vh;
                        object-fit: contain;
                        box-shadow: 0 4px 15px rgba(0,0,0,0.15);
                        background-color: #fff;
                    }
                </style>
            </head>
            <body>
                <img src="?raw=1" alt="Certificate Preview">
            </body>
            </html>
            """
            return HttpResponse(html_content)

        from .models import StudentExamResult, Category, ExamPaper, CustomUser
        import os
        from PIL import Image, ImageDraw, ImageFont
        from django.conf import settings
        from django.utils import timezone

        # Try to get the latest available exam result or create a dummy object
        result = StudentExamResult.objects.first()
        if not result:
            class MockCategory:
                name = "Python Programming"

            class MockExamPaper:
                category = MockCategory()

            class MockStudent:
                first_name = "Harish"
                last_name = "Subramanian"
                username = "harish"
                email = "test@example.com"
                profile_photo = None

            class MockResult:
                id = timezone.now()
                student = MockStudent()
                exam_paper = MockExamPaper()
                def percentage(self):
                    return 100.0

            result = MockResult()

        student = result.student
        student_name = f"{student.first_name} {student.last_name}".strip() or student.username
        course_name = result.exam_paper.category.name if result.exam_paper and result.exam_paper.category else "Aptitude Course"
        score = float(result.percentage()) if hasattr(result, 'percentage') else 100.0
        date_str = timezone.now().strftime("%B %Y")

        # Create a blank white canvas exactly A4 Landscape size (1414 x 1000)
        img = Image.new("RGB", (1414, 1000), color="#FFFFFF")
        draw = ImageDraw.Draw(img)

        # Thin blue/orange bottom bar
        draw.rectangle([(0, 976), (1414, 1000)], fill="#0B4A8F")
        draw.rectangle([(1131, 976), (1414, 1000)], fill="#FF9900")

        # Draw ribbon on the right
        draw.rectangle([(1131, 0), (1261, 888)], fill="#0B4A8F")
        draw.polygon([(1131, 888), (1196, 941), (1261, 888)], fill="#0B4A8F")
        draw.polygon([(1131, 894), (1196, 947), (1261, 894)], fill="#FF9900")

        def get_font(font_name, size):
            try:
                return ImageFont.truetype(font_name, size)
            except OSError:
                try:
                    return ImageFont.truetype("arial.ttf", size)
                except OSError:
                    return ImageFont.load_default()

        # Logo
        logo_path = os.path.join(settings.BASE_DIR, 'static', 'images', 'dlklogo.png')
        if not os.path.exists(logo_path):
            logo_path = os.path.join(settings.BASE_DIR, 'static', 'images', 'dlklogo.jpg')
        if not os.path.exists(logo_path):
            logo_path = os.path.join(settings.BASE_DIR, 'static', 'images', 'Logo.png')

        if os.path.exists(logo_path):
            try:
                logo = Image.open(logo_path).convert("RGBA")
                logo = logo.resize((212, 82), Image.Resampling.LANCZOS)
                img.paste(logo, (82, 76), logo)
            except Exception:
                try:
                    logo = Image.open(logo_path).convert("RGB")
                    logo = logo.resize((212, 82), Image.Resampling.LANCZOS)
                    img.paste(logo, (82, 76))
                except Exception:
                    pass

        # Text
        font_title = get_font("times.ttf", 52)
        font_small = get_font("arial.ttf", 24)
        font_name = get_font("times.ttf", 54)
        font_course = get_font("times.ttf", 42)

        draw.text((82, 247), "CERTIFICATE OF COMPLETION", font=font_title, fill="#1A1A1A")
        draw.text((82, 335), "Presented to", font=font_small, fill="#555555")
        draw.text((82, 382), student_name, font=font_name, fill="#0B4A8F")
        draw.text((82, 488), "For successfully completing an online course", font=font_small, fill="#555555")
        draw.text((82, 535), course_name, font=font_course, fill="#1A1A1A")
        draw.text((82, 606), f"Course completed on {date_str}", font=font_small, fill="#555555")

        # Skill India.png on the right above profile
        skill_path = os.path.join(settings.BASE_DIR, 'static', 'images', 'Skill India.png')
        if os.path.exists(skill_path):
            try:
                skill_img = Image.open(skill_path).convert("RGBA")
                skill_img = skill_img.resize((120, 120), Image.Resampling.LANCZOS)
                img.paste(skill_img, (952, 76), skill_img)
            except Exception:
                pass

        # Profile Image right
        draw.text((930, 222), "STUDENT PROFILE", font=get_font("arial.ttf", 16), fill="#555555")
        profile_drawn = False
        if student.profile_photo and hasattr(student.profile_photo, 'path') and os.path.exists(student.profile_photo.path):
            try:
                p_img = Image.open(student.profile_photo.path).convert("RGB")
                p_img = p_img.resize((165, 165), Image.Resampling.LANCZOS)
                img.paste(p_img, (930, 250))
                profile_drawn = True
            except Exception:
                pass

        if not profile_drawn:
            draw.rectangle([(930, 250), (1095, 415)], outline="#D0D0D0", width=1, fill="#EFEFEF")
            draw.text((971, 321), "No Photo", fill="#7F8C8D", font=get_font("arial.ttf", 18))

        draw.rectangle([(928, 248), (1097, 417)], outline="#D0D0D0", width=1)

        # Seal
        seal_path = os.path.join(settings.BASE_DIR, 'static', 'images', 'Seal Image.png')
        seal_drawn = False
        if os.path.exists(seal_path):
            try:
                seal_img = Image.open(seal_path).convert("RGBA")
                seal_img = seal_img.resize((165, 165), Image.Resampling.LANCZOS)
                img.paste(seal_img, (1114, 435), seal_img)
                seal_drawn = True
            except Exception:
                pass

        if not seal_drawn:
            draw.ellipse([(1114, 435), (1279, 600)], outline="#0B4A8F", fill="#FFFFFF", width=4)
            draw.text((1155, 494), "G", font=get_font("times.ttf", 61), fill="#0B4A8F")

        # Signature
        draw.line([(82, 759), (318, 759)], fill="#D0D0D0", width=1)
        draw.text((82, 771), "Harish Subramanian", fill="#1A1A1A", font=get_font("arial.ttf", 19))
        draw.text((82, 794), "Academic Director, Great Learning", fill="#555555", font=get_font("arial.ttf", 16))

        sig_path = os.path.join(settings.BASE_DIR, 'static', 'images', 'Signature.png')
        if os.path.exists(sig_path):
            try:
                sig_img = Image.open(sig_path).convert("RGBA")
                sig_img = sig_img.resize((188, 70), Image.Resampling.LANCZOS)
                img.paste(sig_img, (82, 682), sig_img)
            except Exception:
                pass

        # Return as PNG direct response
        response = HttpResponse(content_type="image/png")
        img.save(response, "PNG")
        return response
