"""
Online Examination System — Complete Model Layer
=================================================
Models:
    1. CustomUser        — Extended AbstractUser with role-based access
    2. Question          — Question bank with category, difficulty, type, marks, time limit
    3. ExamPaper         — Uniquely randomized paper per student
    4. ExamPaperQuestion — Through model linking ExamPaper ↔ Question (preserves order)
    5. StudentExamResult — Full submission record with auto-evaluation
    6. StudentAnswer     — Per-question response within a result
    7. ExamRequest       — Student ↔ Admin approval workflow
    8. Notification      — Event-driven notifications for approvals/rejections

Design Principles:
    • Every ForeignKey uses PROTECT or CASCADE with explicit on_delete
    • All high-frequency query columns are indexed (db_index or Meta.indexes)
    • Business-rule validation lives in clean() / validators
    • Bulk-import helper on Question manager for Excel workflow
    • No dependency on django.contrib.admin for data access
"""

import uuid
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.core.validators import (
    MinValueValidator,
    MaxValueValidator,
    RegexValidator,
)
from django.db import models
from django.utils import timezone


# ──────────────────────────────────────────────
# 1. CUSTOM USER MODEL
# ──────────────────────────────────────────────

class CustomUser(AbstractUser):
    """
    Extended user model with role differentiation.

    Access control strategy:
        • Superuser status (is_superuser=True) gates admin dashboard access.
        • The `role` field is used for UI logic / queryset filtering only.
        • Students never have is_staff=True or is_superuser=True.
    """

    class Role(models.TextChoices):
        STUDENT = 'Student', 'Student'
        ADMIN = 'Admin', 'Admin'

    # ── Core role field ──────────────────────────
    role = models.CharField(
        max_length=10,
        choices=Role.choices,
        default=Role.STUDENT,
        db_index=True,
        help_text='Determines UI experience. Admin dashboard requires is_superuser.',
    )

    # ── Student profile fields ───────────────────
    whatsapp_number = models.CharField(
        max_length=15,
        blank=True,
        validators=[
            RegexValidator(
                regex=r'^\+?1?\d{9,15}$',
                message='WhatsApp number must be 9-15 digits, optionally starting with +.',
            )
        ],
        help_text='WhatsApp number for direct contact.',
    )
    phone_number = models.CharField(
        max_length=15,
        blank=True,
        validators=[
            RegexValidator(
                regex=r'^\+?1?\d{9,15}$',
                message='Phone number must be 9-15 digits, optionally starting with +.',
            )
        ],
        help_text='Primary contact number.',
    )
    profile_photo = models.ImageField(
        upload_to='profile_photos/%Y/%m/',
        blank=True,
        null=True,
        help_text='Student profile picture.',
    )
    date_of_birth = models.DateField(
        blank=True,
        null=True,
        help_text='Student date of birth.',
    )
    address = models.TextField(
        blank=True,
        help_text='Full postal address.',
    )
    institution = models.CharField(
        max_length=200,
        blank=True,
        help_text='School / college / university name.',
    )

    @property
    def name(self):
        """Compatibility property for legacy templates."""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.first_name or self.username

    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        ordering = ['-date_joined']
        indexes = [
            models.Index(fields=['role'], name='idx_user_role'),
            models.Index(fields=['-date_joined'], name='idx_user_joined'),
            models.Index(fields=['email'], name='idx_user_email'),
        ]

    def __str__(self):
        return f'{self.username} ({self.get_role_display()})'

    @property
    def is_student(self):
        """Quick check for template guards."""
        return self.role == self.Role.STUDENT

    @property
    def is_admin_user(self):
        """True only when user has admin role AND superuser privileges."""
        return self.role == self.Role.ADMIN and self.is_superuser

    def clean(self):
        super().clean()
        # Enforce: Admin role requires is_superuser
        if self.role == self.Role.ADMIN and not self.is_superuser:
            raise ValidationError(
                {'role': 'Admin role requires superuser status.'}
            )
        # Enforce: Students must never be superusers
        if self.role == self.Role.STUDENT and self.is_superuser:
            raise ValidationError(
                {'role': 'Students cannot have superuser privileges.'}
            )


class OTP(models.Model):
    """
    Temporary one-time password for password reset workflow.
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='otps')
    code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    is_verified = models.BooleanField(default=False)

    def is_expired(self):
        # 10 minutes expiration
        return timezone.now() > self.created_at + timezone.timedelta(minutes=10)

    def __str__(self):
        return f"OTP for {self.user.username} - {self.code}"


# ──────────────────────────────────────────────
# 2. CATEGORY MODEL
# ──────────────────────────────────────────────

class Category(models.Model):
    """
    Represents an exam category (e.g., Python, JavaScript, Data Structures).
    Admin manages these from the custom dashboard.
    Students browse these to submit exam requests.
    """
    name = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        help_text='Name of the exam category.'
    )
    description = models.TextField(
        blank=True,
        help_text='Brief overview of what this category covers.'
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text='Whether this category is visible to students.'
    )

    class Meta:
        verbose_name = 'Category'
        verbose_name_plural = 'Categories'
        ordering = ['name']
        indexes = [
            models.Index(fields=['name'], name='idx_cat_name'),
            models.Index(fields=['-created_at'], name='idx_cat_created'),
        ]

    def __str__(self):
        return self.name


# ──────────────────────────────────────────────
# 3. QUESTION MODEL + CUSTOM MANAGER
# ──────────────────────────────────────────────

class QuestionManager(models.Manager):
    """
    Custom manager providing bulk-import helper for Excel workflow.
    """

    def bulk_import_from_rows(self, rows, created_by=None, forced_category=None):
        """
        Accepts a list of dicts (one per Excel row) and performs
        an efficient bulk_create.

        Args:
            rows: List of dicts with question data
            created_by: User who performed the import
            forced_category: If provided, all questions will be assigned to this Category.
                            If None, category is resolved from row['category'].
        """
        from .models import Category
        objects_to_create = []
        errors = []

        # Cache categories if not forcing one
        category_cache = {}
        if not forced_category:
            category_cache = {c.name.lower(): c for c in Category.objects.all()}

        for idx, row in enumerate(rows, start=2):
            try:
                # Resolve Category
                if forced_category:
                    category = forced_category
                else:
                    cat_name = str(row.get('category', '')).strip()
                    if not cat_name:
                        raise ValueError("Category name is required.")
                    
                    category = category_cache.get(cat_name.lower())
                    if not category:
                        category = Category.objects.create(name=cat_name)
                        category_cache[cat_name.lower()] = category

                q = self.model(
                    category=category,
                    difficulty=str(row.get('difficulty', 'Medium')).strip(),
                    question_text=str(row.get('question_text', '')).strip(),
                    question_type=str(row.get('question_type', 'MCQ')).strip(),
                    option_a=str(row.get('option_a', '')).strip(),
                    option_b=str(row.get('option_b', '')).strip(),
                    option_c=str(row.get('option_c', '')).strip(),
                    option_d=str(row.get('option_d', '')).strip(),
                    correct_answer=str(row.get('correct_answer', '')).strip(),
                    marks=int(row.get('marks', 1)),
                    time_limit_minutes=int(row.get('time_limit_minutes', 2)),
                    created_by=created_by,
                )
                objects_to_create.append(q)
            except (ValidationError, ValueError, TypeError, Exception) as e:
                errors.append({'row': idx, 'error': str(e)})

        created = []
        if objects_to_create:
            created = self.bulk_create(objects_to_create, batch_size=500)

        return created, errors


class Question(models.Model):
    """
    Question bank entry.

    Questions are imported via Excel or created individually in the
    custom admin dashboard. Presented in "choose the best answer" format.
    """

    class Difficulty(models.TextChoices):
        EASY = 'Easy', 'Easy'
        MEDIUM = 'Medium', 'Medium'
        HARD = 'Hard', 'Hard'

    class QuestionType(models.TextChoices):
        MCQ = 'MCQ', 'Multiple Choice'
        SHORT_ANSWER = 'Short Answer', 'Short Answer'
        ESSAY = 'Essay', 'Essay'
        TRUE_FALSE = 'True/False', 'True / False'

    objects = QuestionManager()

    # ── Identification ───────────────────────────
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text='Unique question identifier.',
    )

    # ── Classification ───────────────────────────
    category = models.ForeignKey(
        'Category',
        on_delete=models.PROTECT,
        related_name='questions',
        db_index=True,
        null=True, # For existing records during migration
        help_text='Linked category for this question.'
    )
    difficulty = models.CharField(
        max_length=10,
        choices=Difficulty.choices,
        default=Difficulty.MEDIUM,
        db_index=True,
        help_text='Difficulty tier for balanced paper generation.',
    )
    question_type = models.CharField(
        max_length=20,
        choices=QuestionType.choices,
        default=QuestionType.MCQ,
        db_index=True,
        help_text='Determines answer input format on the student interface.',
    )

    # ── Content ──────────────────────────────────
    question_text = models.TextField(
        help_text='Full question statement displayed to the student.',
    )
    option_a = models.CharField(max_length=500, blank=True, help_text='Option A (MCQ / True-False).')
    option_b = models.CharField(max_length=500, blank=True, help_text='Option B (MCQ / True-False).')
    option_c = models.CharField(max_length=500, blank=True, help_text='Option C (MCQ).')
    option_d = models.CharField(max_length=500, blank=True, help_text='Option D (MCQ).')
    correct_answer = models.CharField(
        max_length=500,
        help_text='The correct answer. For MCQ, store the option letter (A/B/C/D).',
    )

    # ── Scoring & Timing ─────────────────────────
    marks = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(100)],
        help_text='Marks awarded for a correct answer (1-100).',
    )
    time_limit_minutes = models.PositiveIntegerField(
        default=2,
        validators=[MinValueValidator(1), MaxValueValidator(120)],
        help_text='Per-question time limit in minutes (1-120).',
    )

    # ── Metadata ─────────────────────────────────
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_questions',
        help_text='Admin who created or imported this question.',
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text='Soft-delete flag. Inactive questions are excluded from paper generation.',
    )

    objects = QuestionManager()

    class Meta:
        verbose_name = 'Question'
        verbose_name_plural = 'Questions'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['category', 'difficulty'], name='idx_q_cat_diff'),
            models.Index(fields=['category', 'difficulty', 'is_active'], name='idx_q_cat_diff_active'),
            models.Index(fields=['question_type', 'is_active'], name='idx_q_type_active'),
            models.Index(fields=['-created_at'], name='idx_q_created'),
        ]

    def __str__(self):
        return f'[{self.difficulty}] {self.question_text[:80]}'

    def clean(self):
        """
        Business-rule validation:
        - MCQ / True-False must have at least options A & B filled.
        - correct_answer must be one of A/B/C/D for MCQ type.
        - marks must be positive.
        """
        super().clean()
        errors = {}

        if self.question_type in (self.QuestionType.MCQ, self.QuestionType.TRUE_FALSE):
            if not self.option_a or not self.option_b:
                errors['option_a'] = 'MCQ and True/False questions require at least options A and B.'

        if self.question_type == self.QuestionType.MCQ:
            if self.correct_answer.upper() not in ('A', 'B', 'C', 'D'):
                errors['correct_answer'] = 'MCQ correct answer must be A, B, C, or D.'

        if self.question_type == self.QuestionType.TRUE_FALSE:
            if self.correct_answer.upper() not in ('A', 'B', 'TRUE', 'FALSE'):
                errors['correct_answer'] = 'True/False answer must be A, B, True, or False.'

        if errors:
            raise ValidationError(errors)

    @property
    def options_list(self):
        """Return non-empty options as a list for template rendering."""
        return [opt for opt in [self.option_a, self.option_b, self.option_c, self.option_d] if opt]


# ──────────────────────────────────────────────
# 3. EXAM PAPER MODEL + THROUGH MODEL
# ──────────────────────────────────────────────

class ExamPaper(models.Model):
    """
    Uniquely randomized paper generated per student upon approval.

    Total marks and duration are calculated from constituent questions.
    Questions are linked via ExamPaperQuestion through model to
    preserve presentation order.
    """

    # ── Identification ───────────────────────────
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='exam_papers',
        help_text='Student this paper was generated for.',
    )
    category = models.ForeignKey(
        'Category',
        on_delete=models.CASCADE,
        related_name='exam_papers',
        help_text='Category this exam belongs to.',
        null=True, # For existing records during migration
    )
    questions = models.ManyToManyField(
        Question,
        through='ExamPaperQuestion',
        related_name='exam_papers',
        help_text='Questions included in this paper (via through model).',
    )

    # ── Computed / cached aggregates ─────────────
    total_marks = models.PositiveIntegerField(
        default=0,
        help_text='Sum of marks for all included questions (cached on generation).',
    )
    total_duration_minutes = models.PositiveIntegerField(
        default=0,
        help_text='Sum of per-question time limits in minutes (cached on generation).',
    )

    # ── Timestamps ───────────────────────────────
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = 'Exam Paper'
        verbose_name_plural = 'Exam Papers'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['student', 'category', '-created_at'], name='idx_paper_stud_cat'),
            models.Index(fields=['student', '-created_at'], name='idx_paper_student'),
        ]

    def __str__(self):
        return f'Paper {self.id!s:.8} for {self.student.username}'

    def recalculate_totals(self):
        """
        Recompute total_marks and total_duration from linked questions.
        Call this after adding/removing questions.
        """
        aggregates = self.paper_questions.aggregate(
            total_m=models.Sum('question__marks'),
            total_d=models.Sum('question__time_limit_minutes'),
        )
        self.total_marks = aggregates['total_m'] or 0
        self.total_duration_minutes = aggregates['total_d'] or 0
        self.save(update_fields=['total_marks', 'total_duration_minutes'])

    def exam_duration_in_minutes(self):
        """Return total exam duration in minutes (custom method per spec)."""
        return self.total_duration_minutes

    @property
    def question_count(self):
        return self.paper_questions.count()


class ExamPaperQuestion(models.Model):
    """
    Through model for ExamPaper ↔ Question.
    Preserves question order within a paper and supports per-question
    overrides if needed in the future.
    """

    exam_paper = models.ForeignKey(
        ExamPaper,
        on_delete=models.CASCADE,
        related_name='paper_questions',
    )
    question = models.ForeignKey(
        Question,
        on_delete=models.PROTECT,  # Prevent question deletion if used in a paper
        related_name='paper_inclusions',
    )
    order = models.PositiveIntegerField(
        default=0,
        help_text='Presentation order of this question within the paper.',
    )

    class Meta:
        verbose_name = 'Exam Paper Question'
        verbose_name_plural = 'Exam Paper Questions'
        ordering = ['order']
        unique_together = [('exam_paper', 'question')]  # No duplicates in a paper
        indexes = [
            models.Index(fields=['exam_paper', 'order'], name='idx_epq_paper_order'),
        ]

    def __str__(self):
        return f'Paper {self.exam_paper_id!s:.8} — Q#{self.order}'


# ──────────────────────────────────────────────
# 4. STUDENT EXAM RESULT + STUDENT ANSWER
# ──────────────────────────────────────────────

class StudentExamResult(models.Model):
    """
    Persists the full submission for one exam attempt.

    Visibility:
        • Students see ONLY "Test Completed" — no scores.
        • Superuser/admin sees everything: per-question breakdown,
          total marks, analytics aggregations.
    """

    class Status(models.TextChoices):
        IN_PROGRESS = 'In Progress', 'In Progress'
        SUBMITTED = 'Submitted', 'Submitted'
        EVALUATED = 'Evaluated', 'Evaluated'

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='exam_results',
        help_text='Student who took this exam.',
    )
    exam_paper = models.OneToOneField(
        ExamPaper,
        on_delete=models.PROTECT,
        related_name='result',
        help_text='The specific paper this result corresponds to.',
    )

    # ── Scoring ──────────────────────────────────
    total_marks_obtained = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        default=0,
        help_text='Auto-calculated sum of marks from correct answers.',
    )
    total_marks_possible = models.PositiveIntegerField(
        default=0,
        help_text='Mirrors exam_paper.total_marks for quick access.',
    )

    # ── Status & Timestamps ──────────────────────
    status = models.CharField(
        max_length=15,
        choices=Status.choices,
        default=Status.IN_PROGRESS,
        db_index=True,
    )
    started_at = models.DateTimeField(
        auto_now_add=True,
        help_text='When the student started the exam.',
    )
    submitted_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='When the student submitted their answers.',
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='When auto-evaluation finished.',
    )

    class Meta:
        verbose_name = 'Student Exam Result'
        verbose_name_plural = 'Student Exam Results'
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['student', '-started_at'], name='idx_result_student'),
            models.Index(fields=['status'], name='idx_result_status'),
            models.Index(fields=['-completed_at'], name='idx_result_completed'),
        ]

    def __str__(self):
        return f'Result {self.id!s:.8} — {self.student.username}'

    # ── Custom methods per spec ──────────────────

    def marks_obtained(self):
        """Return total marks obtained (custom method per spec)."""
        return self.total_marks_obtained

    def percentage(self):
        """Calculate percentage score for admin analytics."""
        if self.total_marks_possible == 0:
            return 0
        return round(
            (float(self.total_marks_obtained) / self.total_marks_possible) * 100, 2
        )

    def is_passed(self, pass_percentage=85):
        """Check pass/fail against a configurable threshold."""
        return self.percentage() >= pass_percentage

    def status_display(self):
        """Human-readable status (custom method per spec)."""
        return self.get_status_display()

    def auto_evaluate(self):
        """
        Iterate over all StudentAnswer objects, compare with correct
        answers, assign marks, and update totals.

        Called after submission to auto-grade MCQ and True/False.
        Short Answer and Essay types are left with marks=0 for
        manual review.
        """
        total = 0
        answers = self.answers.select_related('question')

        for answer in answers:
            q = answer.question
            if q.question_type in (Question.QuestionType.MCQ, Question.QuestionType.TRUE_FALSE):
                if answer.student_answer.strip().upper() == q.correct_answer.strip().upper():
                    answer.marks_awarded = q.marks
                    answer.is_correct = True
                else:
                    answer.marks_awarded = 0
                    answer.is_correct = False
                answer.save(update_fields=['marks_awarded', 'is_correct'])

            total += answer.marks_awarded

        self.total_marks_obtained = total
        self.total_marks_possible = self.exam_paper.total_marks
        self.status = self.Status.EVALUATED
        self.completed_at = timezone.now()
        self.save(update_fields=[
            'total_marks_obtained', 'total_marks_possible',
            'status', 'completed_at',
        ])
        if self.percentage() >= 85:
            from .utils import generate_and_send_certificate
            try:
                generate_and_send_certificate(self)
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Error sending certificate: {e}")

    def clean(self):
        super().clean()
        # Student on result must match student on paper
        if self.student_id and self.exam_paper_id:
            if self.exam_paper.student_id != self.student_id:
                raise ValidationError(
                    'Result student must match the exam paper student.'
                )


class StudentAnswer(models.Model):
    """
    Individual question response within an exam result.

    One record per question per exam attempt. Supports admin
    question-wise performance analysis.
    """

    result = models.ForeignKey(
        StudentExamResult,
        on_delete=models.CASCADE,
        related_name='answers',
    )
    question = models.ForeignKey(
        Question,
        on_delete=models.PROTECT,
        related_name='student_answers',
    )
    student_answer = models.TextField(
        blank=True,
        help_text='The student\'s submitted answer text or option letter.',
    )
    is_correct = models.BooleanField(
        default=False,
        help_text='Set by auto_evaluate for MCQ/True-False.',
    )
    marks_awarded = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        help_text='Marks awarded for this answer.',
    )
    answered_at = models.DateTimeField(
        auto_now_add=True,
        help_text='Timestamp when this answer was submitted.',
    )

    class Meta:
        verbose_name = 'Student Answer'
        verbose_name_plural = 'Student Answers'
        ordering = ['result', 'question']
        unique_together = [('result', 'question')]  # One answer per question per attempt
        indexes = [
            models.Index(fields=['result', 'question'], name='idx_sa_result_q'),
            models.Index(fields=['is_correct'], name='idx_sa_correct'),
        ]

    def __str__(self):
        return f'Answer by {self.result.student.username} for Q#{self.question_id!s:.8}'


# ──────────────────────────────────────────────
# 5. EXAM REQUEST MODEL
# ──────────────────────────────────────────────

class ExamRequest(models.Model):
    """
    Tracks student requests for exam access.

    Workflow: Student creates request → Admin reviews →
    Approved → Paper generated → Student takes exam
    """

    class Status(models.TextChoices):
        PENDING = 'Pending', 'Pending'
        APPROVED = 'Approved', 'Approved'
        REJECTED = 'Rejected', 'Rejected'

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='exam_requests',
        help_text='Student requesting exam access.',
    )
    category = models.ForeignKey(
        'Category',
        on_delete=models.CASCADE,
        related_name='requests',
        help_text='Category the student wants to take an exam in.',
        null=True, # For existing records during migration
    )
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    rejection_reason = models.TextField(
        blank=True,
        help_text='Reason for rejection (filled by admin if rejected).',
    )

    # ── Timestamps ───────────────────────────────
    requested_at = models.DateTimeField(auto_now_add=True, db_index=True)
    reviewed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='When the admin reviewed this request.',
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_requests',
        help_text='Admin who reviewed this request.',
    )

    class Meta:
        verbose_name = 'Exam Request'
        verbose_name_plural = 'Exam Requests'
        ordering = ['-requested_at']
        indexes = [
            models.Index(fields=['status', 'student', 'category'], name='idx_req_stat_stud_cat'),
            models.Index(fields=['status', 'student'], name='idx_req_status_student'),
            models.Index(fields=['status', '-requested_at'], name='idx_req_status_date'),
            models.Index(fields=['student', '-requested_at'], name='idx_req_student_date'),
        ]

    def __str__(self):
        return f'Request {self.id!s:.8} — {self.student.username} [{self.status}]'

    def status_display(self):
        """Human-readable status (custom method per spec)."""
        return self.get_status_display()

    def approve(self, admin_user):
        """
        Mark request as approved and trigger notification.
        Paper generation should be handled by the calling view.
        """
        self.status = self.Status.APPROVED
        self.reviewed_at = timezone.now()
        self.reviewed_by = admin_user
        self.save(update_fields=['status', 'reviewed_at', 'reviewed_by'])

        # Create approval notification
        Notification.objects.create(
            recipient=self.student,
            notification_type=Notification.NotificationType.APPROVAL,
            title='Exam Request Approved',
            message=f'Your exam request has been approved. You may now take your exam.',
        )

    def reject(self, admin_user, reason=''):
        """
        Mark request as rejected with a reason and trigger notification.
        """
        self.status = self.Status.REJECTED
        self.rejection_reason = reason
        self.reviewed_at = timezone.now()
        self.reviewed_by = admin_user
        self.save(update_fields=['status', 'rejection_reason', 'reviewed_at', 'reviewed_by'])

        # Create rejection notification
        Notification.objects.create(
            recipient=self.student,
            notification_type=Notification.NotificationType.REJECTION,
            title='Exam Request Rejected',
            message=f'Better luck next time. Your request for {self.category.name} was rejected. Reason: {reason}' if reason else f'Better luck next time. Your request for {self.category.name} was rejected.',
        )

    def clean(self):
        super().clean()
        # Only students can create exam requests
        if self.student_id and hasattr(self.student, 'role'):
            if self.student.role != CustomUser.Role.STUDENT:
                raise ValidationError(
                    {'student': 'Only students can submit exam requests.'}
                )
        # Rejection reason required when rejected
        if self.status == self.Status.REJECTED and not self.rejection_reason:
            raise ValidationError(
                {'rejection_reason': 'A reason is required when rejecting a request.'}
            )

    @classmethod
    def bulk_approve(cls, request_ids, admin_user):
        """
        Bulk-approve multiple requests in a single operation.
        Returns list of approved ExamRequest objects.
        """
        requests = cls.objects.filter(
            id__in=request_ids,
            status=cls.Status.PENDING,
        ).select_related('student')

        approved = []
        notifications = []
        now = timezone.now()

        for req in requests:
            req.status = cls.Status.APPROVED
            req.reviewed_at = now
            req.reviewed_by = admin_user
            approved.append(req)
            notifications.append(
                Notification(
                    recipient=req.student,
                    notification_type=Notification.NotificationType.APPROVAL,
                    title='Exam Request Approved',
                    message='Your exam request has been approved. You may now take your exam.',
                )
            )

        if approved:
            cls.objects.bulk_update(approved, ['status', 'reviewed_at', 'reviewed_by'])
            Notification.objects.bulk_create(notifications, batch_size=500)

        return approved

    @classmethod
    def bulk_reject(cls, request_ids, admin_user, reason='Bulk rejection by admin'):
        """
        Bulk-reject multiple requests in a single operation.
        Returns list of rejected ExamRequest objects.
        """
        requests = cls.objects.filter(
            id__in=request_ids,
            status=cls.Status.PENDING,
        ).select_related('student')

        rejected = []
        notifications = []
        now = timezone.now()

        for req in requests:
            req.status = cls.Status.REJECTED
            req.rejection_reason = reason
            req.reviewed_at = now
            req.reviewed_by = admin_user
            rejected.append(req)
            notifications.append(
                Notification(
                    recipient=req.student,
                    notification_type=Notification.NotificationType.REJECTION,
                    title='Exam Request Rejected',
                    message=f'Your exam request was rejected. Reason: {reason}',
                )
            )

        if rejected:
            cls.objects.bulk_update(
                rejected, ['status', 'rejection_reason', 'reviewed_at', 'reviewed_by']
            )
            Notification.objects.bulk_create(notifications, batch_size=500)

        return rejected


# ──────────────────────────────────────────────
# 6. NOTIFICATION MODEL
# ──────────────────────────────────────────────

class Notification(models.Model):
    """
    Event-driven notifications for exam request approvals/rejections.

    Queried in real-time on both student and admin interfaces.
    Indexed on recipient + created_at for efficient "latest unread" queries.
    """

    class NotificationType(models.TextChoices):
        APPROVAL = 'Approval', 'Approval'
        REJECTION = 'Rejection', 'Rejection'
        INFO = 'Info', 'Information'
        RESULT = 'Result', 'Result Available'

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
        help_text='User who receives this notification.',
    )
    notification_type = models.CharField(
        max_length=15,
        choices=NotificationType.choices,
        default=NotificationType.INFO,
        db_index=True,
    )
    title = models.CharField(
        max_length=200,
        help_text='Short notification title.',
    )
    message = models.TextField(
        help_text='Full notification message body.',
    )
    is_read = models.BooleanField(
        default=False,
        db_index=True,
        help_text='Whether the recipient has read this notification.',
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = 'Notification'
        verbose_name_plural = 'Notifications'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', '-created_at'], name='idx_notif_recip_date'),
            models.Index(fields=['recipient', 'is_read', '-created_at'], name='idx_notif_unread'),
        ]

    def __str__(self):
        return f'[{self.notification_type}] {self.title} → {self.recipient.username}'

    def mark_as_read(self):
        """Mark notification as read without triggering auto_now fields."""
        if not self.is_read:
            self.is_read = True
            self.save(update_fields=['is_read'])

    @classmethod
    def unread_count(cls, user):
        """Efficient count of unread notifications for navbar badge."""
        return cls.objects.filter(recipient=user, is_read=False).count()

    @classmethod
    def mark_all_read(cls, user):
        """Bulk mark all notifications as read for a user."""
        return cls.objects.filter(
            recipient=user, is_read=False
        ).update(is_read=True)
