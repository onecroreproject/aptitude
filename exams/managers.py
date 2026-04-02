"""
Custom QuerySet and Manager utilities for the exam system.

These provide reusable, chainable query patterns that are consumed
by custom Django views (not django.contrib.admin).
"""

from django.db import models
from django.db.models import Avg, Count, Sum, Q, F


class StudentQuerySet(models.QuerySet):
    """Chainable filters for student-related queries in admin dashboard."""

    def students_only(self):
        return self.filter(role='Student')

    def admins_only(self):
        return self.filter(role='Admin', is_superuser=True)

    def with_exam_stats(self):
        """
        Annotate each student with exam statistics for dashboard cards.
        """
        return self.annotate(
            total_exams=Count('exam_results', distinct=True),
            avg_score=Avg('exam_results__total_marks_obtained'),
            total_requests=Count('exam_requests', distinct=True),
            pending_requests=Count(
                'exam_requests',
                filter=Q(exam_requests__status='Pending'),
                distinct=True,
            ),
        )

    def active_students(self):
        return self.students_only().filter(is_active=True)


class ExamRequestQuerySet(models.QuerySet):
    """Chainable filters for exam request management."""

    def pending(self):
        return self.filter(status='Pending')

    def approved(self):
        return self.filter(status='Approved')

    def rejected(self):
        return self.filter(status='Rejected')

    def for_student(self, student):
        return self.filter(student=student)

    def recent(self, days=7):
        from django.utils import timezone
        cutoff = timezone.now() - timezone.timedelta(days=days)
        return self.filter(requested_at__gte=cutoff)


class QuestionQuerySet(models.QuerySet):
    """Chainable filters for question management and paper generation."""

    def active(self):
        return self.filter(is_active=True)

    def by_category(self, category):
        return self.filter(category=category)

    def by_difficulty(self, difficulty):
        return self.filter(difficulty=difficulty)

    def mcq_only(self):
        return self.filter(question_type='MCQ')

    def with_usage_stats(self):
        """Annotate with how many papers include each question."""
        return self.annotate(
            times_used=Count('paper_inclusions', distinct=True),
            times_answered_correctly=Count(
                'student_answers',
                filter=Q(student_answers__is_correct=True),
                distinct=True,
            ),
            times_answered=Count('student_answers', distinct=True),
        )


class ResultQuerySet(models.QuerySet):
    """Chainable filters for admin analytics."""

    def evaluated(self):
        return self.filter(status='Evaluated')

    def for_student(self, student):
        return self.filter(student=student)

    def pass_rate(self, pass_percentage=40):
        """
        Calculate pass rate across all evaluated results.
        Returns dict with total, passed, failed, pass_rate.
        """
        evaluated = self.evaluated()
        total = evaluated.count()
        if total == 0:
            return {'total': 0, 'passed': 0, 'failed': 0, 'pass_rate': 0}

        # Use raw annotation for percentage calculation
        passed = 0
        for result in evaluated.only('total_marks_obtained', 'total_marks_possible'):
            if result.total_marks_possible > 0:
                pct = (float(result.total_marks_obtained) / result.total_marks_possible) * 100
                if pct >= pass_percentage:
                    passed += 1

        return {
            'total': total,
            'passed': passed,
            'failed': total - passed,
            'pass_rate': round((passed / total) * 100, 2) if total else 0,
        }

    def average_score(self):
        """Return average percentage score across evaluated results."""
        return self.evaluated().aggregate(
            avg_obtained=Avg('total_marks_obtained'),
            avg_possible=Avg('total_marks_possible'),
        )

    def difficulty_analysis(self):
        """
        Per-difficulty breakdown: how students performed on Easy/Medium/Hard questions.
        Returns queryset of dicts.
        """
        from .models import StudentAnswer
        return StudentAnswer.objects.filter(
            result__in=self
        ).values(
            'question__difficulty'
        ).annotate(
            total_answers=Count('id'),
            correct_answers=Count('id', filter=Q(is_correct=True)),
            avg_marks=Avg('marks_awarded'),
        ).order_by('question__difficulty')
