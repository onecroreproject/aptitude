import random
import string
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from datetime import timedelta

class CustomUser(AbstractUser):
    email = models.EmailField(unique=True)
    mobile = models.CharField(max_length=15, blank=True, null=True)
    profile_pic = models.ImageField(upload_to='profile_pics/', blank=True, null=True)
    
    # Students are users who are not superusers/staff
    @property
    def is_student(self):
        return not self.is_superuser and not self.is_staff
    
    # Required for custom auth with email/username
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'first_name', 'last_name']

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.email})"

class OTP(models.Model):
    user_email = models.EmailField()
    otp_code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    is_verified = models.BooleanField(default=False)

    def is_expired(self):
        return timezone.now() > self.created_at + timedelta(minutes=10)

    @staticmethod
    def generate_otp():
        return ''.join(random.choices(string.digits, k=6))

class Course(models.Model):
    course_id = models.CharField(max_length=20, unique=True, editable=False)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    num_questions = models.IntegerField(default=0)  # Auto-calculated
    total_marks = models.IntegerField(default=0)    # Auto-calculated
    created_at = models.DateTimeField(auto_now_add=True)

    def update_stats(self):
        questions = self.questions.all()
        self.num_questions = questions.count()
        self.total_marks = sum(q.marks for q in questions)
        self.save()

    def save(self, *args, **kwargs):
        if not self.course_id:
            last_course = Course.objects.all().order_by('id').last()
            if not last_course:
                self.course_id = 'COURSE_0001'
            else:
                last_id = int(last_course.course_id.split('_')[1])
                self.course_id = f'COURSE_{str(last_id + 1).zfill(4)}'
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.course_id})"

class Question(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='questions')
    text = models.TextField()
    option1 = models.CharField(max_length=200)
    option2 = models.CharField(max_length=200)
    option3 = models.CharField(max_length=200)
    option4 = models.CharField(max_length=200)
    correct_answer = models.IntegerField(choices=[(1, 'Option 1'), (2, 'Option 2'), (3, 'Option 3'), (4, 'Option 4')])
    marks = models.IntegerField(default=10)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.course.update_stats()

    def delete(self, *args, **kwargs):
        course = self.course
        super().delete(*args, **kwargs)
        course.update_stats()

    def __str__(self):
        return self.text[:50]

class Result(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    score = models.FloatField()
    total_marks = models.FloatField()
    percentage = models.FloatField()
    pass_status = models.BooleanField()
    attempt_date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.course.name} - {self.percentage}%"

class Certificate(models.Model):
    result = models.OneToOneField(Result, on_delete=models.CASCADE, related_name='certificate')
    certificate_id = models.CharField(max_length=50, unique=True)
    qr_code = models.ImageField(upload_to='certificates/qrcodes/', blank=True, null=True)
    issued_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Certificate {self.certificate_id} for {self.result.user.username}"
