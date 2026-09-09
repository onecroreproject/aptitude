from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Category, CustomUser, ExamRequest, Question, StudentExamResult
from .utils import generate_exam_paper


class DirectExamAccessFlowTests(TestCase):
    def setUp(self):
        self.admin = CustomUser.objects.create_user(
            username='admin1',
            email='admin1@example.com',
            password='StrongPass123!',
            role=CustomUser.Role.ADMIN,
            is_superuser=True,
        )
        self.student = CustomUser.objects.create_user(
            username='student1',
            email='student1@example.com',
            password='StrongPass123!',
            role=CustomUser.Role.STUDENT,
        )
        self.category = Category.objects.create(name='Python', is_active=True)
        self.question = Question.objects.create(
            category=self.category,
            question_text='What is 2 + 2?',
            option_a='3',
            option_b='4',
            option_c='5',
            option_d='6',
            correct_answer='B',
            marks=1,
            time_limit_minutes=1,
        )

    def test_admin_category_list_uses_live_question_counts(self):
        self.client.force_login(self.admin)

        category = Category.objects.create(name='Java', is_active=True)
        Question.objects.create(
            category=category,
            question_text='Question 1',
            option_a='A',
            option_b='B',
            correct_answer='A',
            marks=1,
            time_limit_minutes=1,
            is_active=True,
        )
        Question.objects.create(
            category=category,
            question_text='Question 2',
            option_a='A',
            option_b='B',
            correct_answer='A',
            marks=1,
            time_limit_minutes=1,
            is_active=True,
        )
        Question.objects.create(
            category=category,
            question_text='Inactive question',
            option_a='A',
            option_b='B',
            correct_answer='A',
            marks=1,
            time_limit_minutes=1,
            is_active=False,
        )

        response = self.client.get(reverse('admin_categories'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['categories'].get(pk=category.pk).actual_question_count, 2)

        Question.objects.filter(category=category).order_by('created_at').first().delete()
        response = self.client.get(reverse('admin_categories'))
        self.assertEqual(response.context['categories'].get(pk=category.pk).actual_question_count, 1)

    def test_new_student_can_start_exam_directly(self):
        from .models import can_start_exam

        self.assertTrue(can_start_exam(self.student, self.category)['allowed'])

    def test_failed_attempt_enforces_24_hour_cooldown(self):
        from .models import can_start_exam

        paper = generate_exam_paper(self.student, self.category, num_questions=1)
        result = StudentExamResult.objects.create(
            student=self.student,
            exam_paper=paper,
            total_marks_possible=paper.total_marks,
            status=StudentExamResult.Status.EVALUATED,
            completed_at=timezone.now() - timedelta(minutes=30),
        )
        result.total_marks_obtained = 0
        result.save(update_fields=['total_marks_obtained'])

        eligibility = can_start_exam(self.student, self.category)
        self.assertFalse(eligibility['allowed'])
        self.assertEqual(eligibility['reason'], 'cooldown')
        self.assertGreater(eligibility['cooldown_remaining'].total_seconds(), 0)

    def test_start_exam_endpoint_creates_attempt_without_exam_request(self):
        self.client.login(username='student1', password='StrongPass123!')

        response = self.client.post(reverse('start_exam', args=[self.category.id]))

        self.assertEqual(response.status_code, 302)
        self.assertFalse(ExamRequest.objects.filter(student=self.student, category=self.category).exists())
        self.assertTrue(
            StudentExamResult.objects.filter(
                student=self.student,
                exam_paper__category=self.category,
                status=StudentExamResult.Status.IN_PROGRESS,
            ).exists()
        )
