from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import user_passes_test
from django.contrib import messages
from students.models import CustomUser, Course, Question, Result, Certificate
from django.db.models import Count, Q
import pandas as pd
from students.utils import generate_qr_code
import uuid

def is_admin(user):
    return user.is_authenticated and (user.is_superuser or user.is_staff)

@user_passes_test(is_admin, login_url='login')
def admin_dashboard(request):
    total_students = CustomUser.objects.filter(is_superuser=False, is_staff=False).count()
    total_courses = Course.objects.count()
    total_questions = Question.objects.count()
    total_certificates = Certificate.objects.count()
    
    # Example stats for charts
    course_stats = Course.objects.annotate(num_attempts=Count('result')).values('name', 'num_attempts')
    
    context = {
        'total_students': total_students,
        'total_courses': total_courses,
        'total_questions': total_questions,
        'total_certificates': total_certificates,
        'course_stats': list(course_stats),
    }
    return render(request, 'managers/dashboard.html', context)

@user_passes_test(is_admin, login_url='login')
def student_management(request):
    query = request.GET.get('q', '')
    students = CustomUser.objects.filter(is_superuser=False, is_staff=False)
    
    if query:
        students = students.filter(
            Q(first_name__icontains=query) | 
            Q(last_name__icontains=query) | 
            Q(email__icontains=query) |
            Q(username__icontains=query)
        )
        
    context = {
        'students': students,
        'query': query
    }
    return render(request, 'managers/students.html', context)


@user_passes_test(is_admin, login_url='login')
def reject_user(request, user_id):
    user = get_object_or_404(CustomUser, id=user_id)
    user.delete()
    messages.success(request, 'User registration rejected and deleted.')
    return redirect('student_management')

@user_passes_test(is_admin, login_url='login')
def course_management(request):
    courses = Course.objects.all().order_by('-created_at')
    if request.method == 'POST':
        name = request.POST.get('name')
        desc = request.POST.get('description')
        num_q = request.POST.get('num_questions')
        total_m = request.POST.get('total_marks')
        
        Course.objects.create(name=name, description=desc)
        messages.success(request, 'Course created successfully!')
        return redirect('course_management')
        
    return render(request, 'managers/courses.html', {'courses': courses})

@user_passes_test(is_admin, login_url='login')
def edit_course(request, course_id):
    course = get_object_or_404(Course, id=course_id)
    if request.method == 'POST':
        course.name = request.POST.get('name')
        course.description = request.POST.get('description')
        course.save()
        messages.success(request, 'Course updated successfully!')
        return redirect('course_management')
    return render(request, 'managers/course_edit.html', {'course': course})

@user_passes_test(is_admin, login_url='login')
def delete_course(request, course_id):
    course = get_object_or_404(Course, id=course_id)
    course.delete()
    messages.success(request, 'Course deleted successfully!')
    return redirect('course_management')

@user_passes_test(is_admin, login_url='login')
def view_course_questions(request, course_id):
    course = get_object_or_404(Course, id=course_id)
    questions = Question.objects.filter(course=course).order_by('id')
    
    if request.method == 'POST':
        # Manual Add
        if 'add_manual' in request.POST:
            Question.objects.create(
                course=course,
                text=request.POST.get('text'),
                option1=request.POST.get('opt1'),
                option2=request.POST.get('opt2'),
                option3=request.POST.get('opt3'),
                option4=request.POST.get('opt4'),
                correct_answer=request.POST.get('correct'),
                marks=request.POST.get('marks', 10)
            )
            messages.success(request, 'Question added successfully!')
        
        # Bulk Upload
        elif 'bulk_upload' in request.FILES:
            file = request.FILES['bulk_upload']
            try:
                if file.name.endswith('.csv'):
                    df = pd.read_csv(file)
                else:
                    df = pd.read_excel(file)
                
                count = 0
                errors = []
                for index, row in df.iterrows():
                    try:
                        if pd.isna(row.get('question')): continue
                        text = str(row['question']).strip()
                        opt1 = str(row['option1']).strip()
                        opt2 = str(row['option2']).strip()
                        opt3 = str(row['option3']).strip()
                        opt4 = str(row['option4']).strip()
                        # Robust Answer Parsing: Prioritize content matching then numeric mapping
                        raw_ans = str(row.get('correct_answer', '')).strip().lower()
                        opt_contents = [opt1.lower(), opt2.lower(), opt3.lower(), opt4.lower()]
                        correct_ans = 1 # Default
                        
                        # 1. Try matching full text content first (Handles case where '8' is an option value)
                        if raw_ans in opt_contents:
                            correct_ans = opt_contents.index(raw_ans) + 1
                        else:
                            # 2. Try parsing as a direct index (1-4)
                            try:
                                val = int(float(raw_ans))
                                if 1 <= val <= 4:
                                    correct_ans = val
                                else:
                                    raise ValueError("Index out of range")
                            except:
                                # 3. Try mapping common labels (a, b, c, d)
                                mapping = {'a': 1, 'b': 2, 'c': 3, 'd': 4, 'opt 1': 1, 'opt 2': 2, 'opt 3': 3, 'opt 4': 4, 'option 1': 1, 'option 2': 2, 'option 3': 3, 'option 4': 4}
                                if raw_ans in mapping:
                                    correct_ans = mapping[raw_ans]
                                else:
                                    errors.append(f"Row {index+2}: Unmatched answer '{raw_ans}', defaulting to Option 1")
                                    correct_ans = 1
                        
                        try:
                            marks = int(float(row.get('marks', 10)))
                        except:
                            marks = 10
                        
                        Question.objects.create(
                            course=course, text=text,
                            option1=opt1, option2=opt2, option3=opt3, option4=opt4,
                            correct_answer=correct_ans, marks=marks
                        )
                        count += 1
                    except Exception as e:
                        errors.append(f"Row {index+2}: {str(e)}")
                
                if count > 0:
                    messages.success(request, f'{count} questions uploaded successfully!')
                if errors:
                    messages.warning(request, f'Notice: {", ".join(errors[:3])}...')
            except Exception as e:
                messages.error(request, f'Bulk Upload Error: {str(e)}')
        
        return redirect('view_course_questions', course_id=course.id)

    return render(request, 'managers/questions.html', {'questions': questions, 'course': course})

@user_passes_test(is_admin, login_url='login')
def edit_question(request, q_id):
    question = get_object_or_404(Question, id=q_id)
    courses = Course.objects.all()
    if request.method == 'POST':
        question.course_id = request.POST.get('course_id')
        question.text = request.POST.get('text')
        question.option1 = request.POST.get('opt1')
        question.option2 = request.POST.get('opt2')
        question.option3 = request.POST.get('opt3')
        question.option4 = request.POST.get('opt4')
        question.correct_answer = request.POST.get('correct')
        question.marks = request.POST.get('marks', 10)
        question.save()
        messages.success(request, 'Question updated successfully!')
        return redirect('view_course_questions', course_id=question.course.id)
    return render(request, 'managers/question_edit.html', {'question': question, 'courses': courses})

@user_passes_test(is_admin, login_url='login')
def delete_question(request, q_id):
    q = get_object_or_404(Question, id=q_id)
    course_id = q.course.id
    q.delete()
    messages.success(request, 'Question deleted!')
    return redirect('view_course_questions', course_id=course_id)

@user_passes_test(is_admin, login_url='login')
def bulk_delete_questions(request):
    if request.method == 'POST':
        q_ids = request.POST.getlist('question_ids')
        course_id = request.POST.get('course_id')
        if q_ids:
            Question.objects.filter(id__in=q_ids).delete()
            messages.success(request, f'Successfully deleted {len(q_ids)} questions.')
            
            # Recalculate course stats (Handled by model delete signal in students/models.py)
            # Actually, bulk delete doesn't trigger individual .delete() signals in some Django versions.
            # But my Course.update_stats() should be called.
            if course_id:
                course = get_object_or_404(Course, id=course_id)
                course.update_stats()
                return redirect('view_course_questions', course_id=course_id)
        
    return redirect('course_management')

@user_passes_test(is_admin, login_url='login')
def admin_results(request):
    export = request.GET.get('export')
    results = Result.objects.all().order_by('-attempt_date')
    
    if export == 'excel':
        import pandas as pd
        from django.http import HttpResponse
        
        data = []
        for r in results:
            data.append({
                'Date': r.attempt_date.strftime('%Y-%m-%d %H:%M'),
                'Student': f"{r.user.first_name} {r.user.last_name}",
                'Course': r.course.name,
                'Score': r.score,
                'Total': r.total_marks,
                'Percentage': f"{r.percentage}%",
                'Status': 'Pass' if r.pass_status else 'Fail'
            })
        df = pd.DataFrame(data)
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename="results.xlsx"'
        df.to_excel(response, index=False)
        return response

    return render(request, 'managers/results.html', {'results': results})

@user_passes_test(is_admin, login_url='login')
def certificate_management(request):
    certificates = Certificate.objects.all().order_by('-issued_at')
    # Auto-generate for any result >= 60% that doesn't have one
    pending_results = Result.objects.filter(percentage__gte=60, certificate__isnull=True)
    
    if request.method == 'POST' and 'generate_all' in request.POST:
        for res in pending_results:
            cert_id = f"CERT-{uuid.uuid4().hex[:8].upper()}"
            qr_content = f"Student: {res.user.first_name} {res.user.last_name}\nCourse: {res.course.name}\nScore: {res.percentage}%"
            qr_file = generate_qr_code(qr_content)
            
            cert = Certificate.objects.create(
                result=res,
                certificate_id=cert_id
            )
            cert.qr_code.save(f"{cert_id}.png", qr_file)
        messages.success(request, f'Generated {pending_results.count()} certificates!')
        return redirect('certificate_management')

    return render(request, 'managers/certificates.html', {'certificates': certificates, 'pending_count': pending_results.count()})
