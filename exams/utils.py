"""
Utility functions for the exam system.

Includes:
    - Excel bulk import for questions
    - Randomized paper generation
    - Auto-evaluation runner
"""

import random
from django.db import transaction
from django.utils import timezone


def import_questions_from_excel(file_obj, created_by=None, forced_category=None):
    """
    Parse an uploaded Excel file and bulk-import questions.
    """
    try:
        import openpyxl
    except ImportError:
        return {
            'created_count': 0,
            'error_count': 1,
            'errors': [{'row': 0, 'error': 'openpyxl is not installed. Run: pip install openpyxl'}],
        }

    from .models import Question

    wb = openpyxl.load_workbook(file_obj, read_only=True)
    ws = wb.active

    # Extract headers from first row
    headers = []
    for cell in ws[1]:
        val = cell.value
        if val:
            headers.append(str(val).strip().lower().replace(' ', '_'))
        else:
            headers.append('')

    # Build rows as list of dicts
    rows = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        row_dict = {}
        for i, val in enumerate(row):
            if i < len(headers) and headers[i]:
                row_dict[headers[i]] = val
        # Skip completely empty rows
        if any(v is not None and str(v).strip() for v in row_dict.values()):
            rows.append(row_dict)

    wb.close()

    if not rows:
        return {
            'created_count': 0,
            'error_count': 0,
            'errors': [],
        }

    created, errors = Question.objects.bulk_import_from_rows(
        rows, created_by=created_by, forced_category=forced_category
    )

    return {
        'created_count': len(created),
        'error_count': len(errors),
        'errors': errors,
    }


def generate_exam_paper(student, category, num_questions=None):
    """
    Generate a randomized exam paper for a student for a specific category.

    Args:
        student: CustomUser instance (role=Student)
        category: Category instance
        num_questions: Optional number of questions to include. 
                       If None, all active questions in the category are included.

    Returns:
        ExamPaper instance with linked questions

    Raises:
        ValueError: If no questions available in the category
    """
    from .models import Question, ExamPaper, ExamPaperQuestion

    # Fetch all active questions for this category
    all_questions = list(
        Question.objects.filter(
            category=category,
            is_active=True,
        ).values_list('id', flat=True)
    )

    if not all_questions:
        raise ValueError(
            f'No active questions found in the "{category.name}" category. '
            'Please add questions before approving requests.'
        )

    # Determine how many questions to pick
    if num_questions and len(all_questions) > num_questions:
        selected_questions = random.sample(all_questions, num_questions)
    else:
        selected_questions = all_questions

    # Shuffle the final selection for random order
    random.shuffle(selected_questions)

    with transaction.atomic():
        # Prevent multiple active papers for the same student/category?
        # Actually, the view handles that by checking for existing result/paper.
        paper = ExamPaper.objects.create(
            student=student, 
            category=category
        )

        # Create through-model entries preserving order
        through_objects = [
            ExamPaperQuestion(
                exam_paper=paper,
                question_id=q_id,
                order=idx,
            )
            for idx, q_id in enumerate(selected_questions, start=1)
        ]
        ExamPaperQuestion.objects.bulk_create(through_objects, batch_size=500)

        # Recalculate totals from linked questions
        paper.recalculate_totals()

    return paper


def submit_and_evaluate(result):
    """
    Finalize an exam submission and run auto-evaluation.

    Args:
        result: StudentExamResult instance (status=In Progress)

    Returns:
        The updated StudentExamResult instance
    """
    from .models import StudentExamResult, Notification

    result.submitted_at = timezone.now()
    result.status = StudentExamResult.Status.SUBMITTED
    result.save(update_fields=['submitted_at', 'status'])

    # Auto-evaluate MCQ and True/False answers
    result.auto_evaluate()

    # Notify admin that a submission is ready for review (for essay/short answer)
    has_manual_review = result.answers.filter(
        question__question_type__in=['Short Answer', 'Essay']
    ).exists()

    if has_manual_review:
        # Notify admins (superusers) about manual review needed
        from .models import CustomUser
        admins = CustomUser.objects.filter(is_superuser=True, is_active=True)
        notifications = [
            Notification(
                recipient=admin,
                notification_type=Notification.NotificationType.INFO,
                title='Manual Review Required',
                message=f'{result.student.username} submitted an exam with questions requiring manual review.',
            )
            for admin in admins
        ]
        Notification.objects.bulk_create(notifications, batch_size=100)

    return result
