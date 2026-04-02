import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'exam_platform.settings')
django.setup()

from exams.models import Category, Question, CustomUser

def seed():
    # ── Create Users ─────────────────────────────
    admin, created = CustomUser.objects.get_or_create(
        username='admin',
        defaults={'role': 'Superuser', 'is_staff': True, 'is_superuser': True}
    )
    if created:
        admin.set_password('admin123')
        admin.save()
        print("Superuser 'admin' created.")

    student, created = CustomUser.objects.get_or_create(
        username='student1',
        defaults={'role': 'Student', 'name': 'Test Student'}
    )
    if created:
        student.set_password('student123')
        student.save()
        print("Student 'student1' created.")

    # ── Create Categories ────────────────────────
    cats = [
        ('Python Programming', 'Core Python, Data Structures, and OOP.'),
        ('JavaScript & Web', 'Modern ES6+, DOM manipulation, and Web APIs.'),
        ('Database Management', 'SQL, Normalization, and ACID properties.'),
        ('General Science', 'Physics, Chemistry, and Biology fundamentals.'),
    ]
    
    category_objs = {}
    for name, desc in cats:
        cat, _ = Category.objects.get_or_create(name=name, defaults={'description': desc})
        category_objs[name] = cat
        print(f"Category: {name}")

    # ── Create Questions ─────────────────────────
    questions = [
        # Python
        ('Python Programming', 'Easy', 'MCQ', 'What is the correct extension of Python files?', '.py', '.python', '.pyt', '.pyw', 'A', 2, 1),
        ('Python Programming', 'Medium', 'MCQ', 'Which keyword is used to create a function?', 'def', 'func', 'function', 'define', 'A', 3, 2),
        ('Python Programming', 'Hard', 'MCQ', 'What is the output of print(0.1 + 0.2 == 0.3)?', 'True', 'False', 'Error', '0.3', 'B', 5, 3),
        
        # JS
        ('JavaScript & Web', 'Easy', 'MCQ', 'Which keyword is used to declare a block-scoped variable?', 'var', 'let', 'set', 'dim', 'B', 2, 1),
        ('JavaScript & Web', 'Medium', 'MCQ', 'What does DOM stand for?', 'Data Object Model', 'Document Object Model', 'Digital Object Memory', 'Display Object Menu', 'B', 3, 2),
        ('JavaScript & Web', 'Hard', 'MCQ', 'What is the behavior of "eval()"?', 'Executes code', 'Safety check', 'Parses JSON', 'Binary search', 'A', 5, 3),
    ]

    for cat_name, diff, q_type, text, o_a, o_b, o_c, o_d, ans, marks, time in questions:
        Question.objects.get_or_create(
            question_text=text,
            defaults={
                'category': category_objs[cat_name],
                'difficulty': diff,
                'question_type': q_type,
                'option_a': o_a,
                'option_b': o_b,
                'option_c': o_c,
                'option_d': o_d,
                'correct_answer': ans,
                'marks': marks,
                'time_limit_minutes': time
            }
        )
    print("Questions seeded.")

if __name__ == '__main__':
    seed()
