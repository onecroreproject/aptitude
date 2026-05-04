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


def generate_and_send_certificate(result):
    """
    Generate the certificate using Pillow in A4 Landscape style and send via email.
    """
    import os
    import tempfile
    from PIL import Image, ImageDraw, ImageFont
    from django.conf import settings
    from django.core.mail import EmailMessage
    from django.utils import timezone

    student = result.student
    student_name = f"{student.first_name} {student.last_name}".strip() or student.username
    course_name = result.exam_paper.category.name if result.exam_paper and result.exam_paper.category else "Aptitude Course"
    score = float(result.percentage())
    date_str = timezone.now().strftime("%B %Y")

    # 1. Create a blank white canvas exactly A4 Landscape size (1414 x 1000)
    img = Image.new("RGB", (1414, 1000), color="#FFFFFF")
    draw = ImageDraw.Draw(img)

    # Thin blue/orange bottom bar
    draw.rectangle([(0, 976), (1414, 1000)], fill="#0B4A8F")
    draw.rectangle([(1131, 976), (1414, 1000)], fill="#FF9900")

    # 2. Draw prominent vertical blue ribbon/stripe on the right
    draw.rectangle([(1131, 0), (1261, 888)], fill="#0B4A8F")
    # Ribbon pointed bottom
    draw.polygon([(1131, 888), (1196, 941), (1261, 888)], fill="#0B4A8F")
    # Ribbon orange accent tip
    draw.polygon([(1131, 894), (1196, 947), (1261, 894)], fill="#FF9900")

    # Font helper with fallback
    def get_font(font_name, size):
        try:
            return ImageFont.truetype(font_name, size)
        except OSError:
            try:
                return ImageFont.truetype("arial.ttf", size)
            except OSError:
                return ImageFont.load_default()

    # 3. Placement: Top Left - Logo
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

    # Option to also include Skill India.png on the right above profile
    skill_path = os.path.join(settings.BASE_DIR, 'static', 'images', 'Skill India.png')
    if os.path.exists(skill_path):
        try:
            skill_img = Image.open(skill_path).convert("RGBA")
            skill_img = skill_img.resize((120, 120), Image.Resampling.LANCZOS)
            img.paste(skill_img, (952, 76), skill_img)
        except Exception:
            pass

    # 4. Placement: Right - Profile Image
    draw.text((930, 222), "STUDENT PROFILE", font=get_font("arial.ttf", 16), fill="#555555")
    profile_photo = student.profile_photo
    profile_drawn = False
    if profile_photo and hasattr(profile_photo, 'path') and os.path.exists(profile_photo.path):
        try:
            p_img = Image.open(profile_photo.path).convert("RGB")
            p_img = p_img.resize((165, 165), Image.Resampling.LANCZOS)
            img.paste(p_img, (930, 250))
            profile_drawn = True
        except Exception:
            pass

    if not profile_drawn:
        draw.rectangle([(930, 250), (1095, 415)], outline="#D0D0D0", width=1, fill="#EFEFEF")
        draw.text((971, 321), "No Photo", fill="#7F8C8D", font=get_font("arial.ttf", 18))

    draw.rectangle([(928, 248), (1097, 417)], outline="#D0D0D0", width=1)

    # 5. Add Text Content on the Left
    font_title = get_font("times.ttf", 52)
    font_small = get_font("arial.ttf", 24)
    font_name = get_font("times.ttf", 54)
    font_course = get_font("times.ttf", 42)

    # Title
    draw.text((82, 247), "CERTIFICATE OF COMPLETION", font=font_title, fill="#1A1A1A")

    # Presented to
    draw.text((82, 335), "Presented to", font=font_small, fill="#555555")

    # Student Name
    draw.text((82, 382), student_name, font=font_name, fill="#0B4A8F")

    # Course info
    draw.text((82, 488), "For successfully completing an online course", font=font_small, fill="#555555")
    draw.text((82, 535), course_name, font=font_course, fill="#1A1A1A")

    # Date info
    draw.text((82, 606), f"Course completed on {date_str}", font=font_small, fill="#555555")

    # 6. Center Right - Seal Image (Overlapping the Ribbon)
    seal_path = os.path.join(settings.BASE_DIR, 'static', 'images', 'Seal Image.png')
    seal_drawn = False
    if os.path.exists(seal_path):
        try:
            seal_img = Image.open(seal_path).convert("RGBA")
            seal_img = seal_img.resize((165, 165), Image.Resampling.LANCZOS)
            img.paste(seal_img, (1114, 435), seal_img)
            seal_drawn = True
        except Exception:
            try:
                seal_img = Image.open(seal_path).convert("RGB")
                seal_img = seal_img.resize((165, 165), Image.Resampling.LANCZOS)
                img.paste(seal_img, (1114, 435))
                seal_drawn = True
            except Exception:
                pass

    if not seal_drawn:
        # Fallback drawn Great Learning style G-Certificate seal
        draw.ellipse([(1114, 435), (1279, 600)], outline="#0B4A8F", fill="#FFFFFF", width=4)
        draw.text((1155, 494), "G", font=get_font("times.ttf", 61), fill="#0B4A8F")

    # 7. Bottom Left - Signature
    sig_path = os.path.join(settings.BASE_DIR, 'static', 'images', 'Signature.png')
    if os.path.exists(sig_path):
        try:
            sig_img = Image.open(sig_path).convert("RGBA")
            sig_img = sig_img.resize((188, 70), Image.Resampling.LANCZOS)
            img.paste(sig_img, (82, 682), sig_img)
        except Exception:
            try:
                sig_img = Image.open(sig_path).convert("RGB")
                sig_img = sig_img.resize((188, 70), Image.Resampling.LANCZOS)
                img.paste(sig_img, (82, 682))
            except Exception:
                pass

    draw.line([(82, 759), (318, 759)], fill="#D0D0D0", width=1)
    draw.text((82, 771), "Harish Subramanian", fill="#1A1A1A", font=get_font("arial.ttf", 19))
    draw.text((82, 794), "Academic Director, Great Learning", fill="#555555", font=get_font("arial.ttf", 16))

    # 8. Save and send via email
    cert_filename = f"Certificate_{student.username}_{result.id.hex[:6]}.png"
    cert_path = os.path.join(tempfile.gettempdir(), cert_filename)
    img.save(cert_path, "PNG")

    subject = f"Congratulations {student.first_name or student.username}! Your Certificate of Completion"
    body = f"""Dear {student.first_name or student.username},

Congratulations! You have successfully passed the assessment for {course_name} with a score of {score:.2f}%.

Please find your certificate attached to this email.

Best regards,
Aptipro Exam Team"""

    email_msg = EmailMessage(
        subject=subject,
        body=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[student.email],
    )
    email_msg.attach_file(cert_path)
    email_msg.send(fail_silently=False)


