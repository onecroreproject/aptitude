"""
Forms for the online examination system.

All forms are designed for custom Django views — no dependency on
django.contrib.admin form handling.
"""

from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.core.exceptions import ValidationError

from .models import (
    CustomUser,
    Category,
    Question,
    ExamRequest,
)


# ──────────────────────────────────────────────
# AUTHENTICATION FORMS
# ──────────────────────────────────────────────

class StudentRegistrationForm(UserCreationForm):
    """
    Registration form for students.
    Automatically sets role=Student and ensures no superuser flags.
    """

    first_name = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'First Name',
            'autocomplete': 'given-name',
        }),
    )
    last_name = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Last Name',
            'autocomplete': 'family-name',
        }),
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'form-input',
            'placeholder': 'Email Address',
            'autocomplete': 'email',
        }),
    )
    phone_number = forms.CharField(
        max_length=15,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Phone Number',
            'autocomplete': 'tel',
        }),
    )
    whatsapp_number = forms.CharField(
        max_length=15,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'WhatsApp Number',
        }),
    )
    institution = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Institution / College',
        }),
    )
    profile_photo = forms.ImageField(
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'form-input',
            'accept': 'image/*',
        }),
    )

    class Meta:
        model = CustomUser
        fields = [
            'username', 'first_name', 'last_name', 'email', 
            'phone_number', 'whatsapp_number', 'institution', 
            'profile_photo', 'password1', 'password2'
        ]
        widgets = {
            'username': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Username',
                'autocomplete': 'username',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Style password fields
        self.fields['password1'].widget.attrs.update({
            'class': 'form-input',
            'placeholder': 'Password',
        })
        self.fields['password2'].widget.attrs.update({
            'class': 'form-input',
            'placeholder': 'Confirm Password',
        })

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if CustomUser.objects.filter(email=email, is_active=True).exists():
            raise ValidationError("A user with this email already exists.")
        return email

        if commit:
            user.save()
        return user


class SubAdminForm(forms.ModelForm):
    """
    Form for Admin to create and edit Sub-Admins.
    """
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-input',
            'placeholder': 'Enter Password',
        }),
        required=False, # Optional for editing
        help_text="Leave blank to keep existing password when editing."
    )

    class Meta:
        model = CustomUser
        fields = ['first_name', 'last_name', 'username', 'email', 'phone_number', 'role']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'First Name'}),
            'last_name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Last Name'}),
            'username': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Username'}),
            'email': forms.EmailInput(attrs={'class': 'form-input', 'placeholder': 'Email Address'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Contact Number'}),
            'role': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Limit role choices to SUB_ADMIN for this form
        self.fields['role'].choices = [
            (CustomUser.Role.SUB_ADMIN, 'Sub Admin'),
        ]
        self.fields['role'].initial = CustomUser.Role.SUB_ADMIN

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = CustomUser.Role.SUB_ADMIN
        password = self.cleaned_data.get('password')
        if password:
            user.set_password(password)
            user.raw_password = password # As requested by user
        if commit:
            user.save()
        return user


class CustomLoginForm(AuthenticationForm):
    """Styled login form for the Aptipro platform."""

    username = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Username',
            'autocomplete': 'username',
        }),
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-input',
            'placeholder': 'Password',
            'autocomplete': 'current-password',
        }),
    )


class ForgotPasswordForm(forms.Form):
    """Form for requesting a password reset OTP."""
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'form-input',
            'placeholder': 'Enter your registered email',
            'autocomplete': 'email',
        }),
    )

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if not CustomUser.objects.filter(email=email).exists():
            raise ValidationError("No user found with this email address.")
        return email


class OTPVerificationForm(forms.Form):
    """Form specifically for verifying the 6-digit OTP."""
    code = forms.CharField(
        max_length=6,
        min_length=6,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Enter 6-digit OTP',
            'style': 'text-align: center; letter-spacing: 0.5em; font-weight: 700;',
        }),
    )

    def clean_code(self):
        code = self.cleaned_data.get('code')
        if not code.isdigit():
            raise ValidationError("OTP must be digits only.")
        return code


class ResetPasswordForm(forms.Form):
    """Form for setting a new password after OTP verification."""
    password = forms.CharField(
        label="New Password",
        widget=forms.PasswordInput(attrs={
            'class': 'form-input',
            'placeholder': 'New Password',
        }),
    )
    confirm_password = forms.CharField(
        label="Confirm New Password",
        widget=forms.PasswordInput(attrs={
            'class': 'form-input',
            'placeholder': 'Confirm Password',
        }),
    )

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")

        if password and confirm_password and password != confirm_password:
            raise ValidationError("Passwords do not match.")
        
        if password and len(password) < 8:
             raise ValidationError("Password must be at least 8 characters.")

        return cleaned_data


# ──────────────────────────────────────────────
# STUDENT PROFILE FORM
# ──────────────────────────────────────────────

class StudentProfileForm(forms.ModelForm):
    """
    Profile update form for students.
    Excludes role, is_staff, is_superuser from editing.
    """

    class Meta:
        model = CustomUser
        fields = [
            'first_name', 'last_name', 'email', 'phone_number', 
            'whatsapp_number', 'date_of_birth', 'address', 
            'institution', 'profile_photo'
        ]
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'First Name'}),
            'last_name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Last Name'}),
            'email': forms.EmailInput(attrs={'class': 'form-input', 'placeholder': 'Email'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Phone Number'}),
            'whatsapp_number': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'WhatsApp Number'}),
            'date_of_birth': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'address': forms.Textarea(attrs={'class': 'form-input', 'rows': 3, 'placeholder': 'Address'}),
            'institution': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Institution'}),
            'profile_photo': forms.FileInput(attrs={'class': 'form-input'}),
        }


# ──────────────────────────────────────────────
# CATEGORY FORM (ADMIN DASHBOARD)
# ──────────────────────────────────────────────

class CategoryForm(forms.ModelForm):
    """
    Form for creating / editing categories in the admin dashboard.
    """

    class Meta:
        model = Category
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Category Name (e.g. Python)'}),
            'description': forms.Textarea(attrs={'class': 'form-input', 'rows': 3, 'placeholder': 'Optional description...'}),
        }


# ──────────────────────────────────────────────
# QUESTION FORMS (ADMIN DASHBOARD)
# ──────────────────────────────────────────────

class QuestionForm(forms.ModelForm):
    """
    Form for creating / editing individual questions in the admin dashboard.
    """

    class Meta:
        model = Question
        fields = [
            'category', 'difficulty', 'question_type',
            'question_text',
            'option_a', 'option_b', 'option_c', 'option_d',
            'correct_answer', 'marks', 'time_limit_minutes',
            'is_active',
        ]
        widgets = {
            'category': forms.Select(attrs={'class': 'form-select'}),
            'difficulty': forms.Select(attrs={'class': 'form-select'}),
            'question_type': forms.Select(attrs={'class': 'form-select'}),
            'question_text': forms.Textarea(attrs={'class': 'form-input', 'rows': 4, 'placeholder': 'Question text...'}),
            'option_a': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Option A'}),
            'option_b': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Option B'}),
            'option_c': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Option C'}),
            'option_d': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Option D'}),
            'correct_answer': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Correct answer (A/B/C/D for MCQ)'}),
            'marks': forms.NumberInput(attrs={'class': 'form-input', 'min': 1, 'max': 100}),
            'time_limit_minutes': forms.NumberInput(attrs={'class': 'form-input', 'min': 1, 'max': 120}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
        }


class ExcelImportForm(forms.Form):
    """
    Form for bulk-importing questions from Excel files.
    Accepts .xlsx and .xls files.
    """

    excel_file = forms.FileField(
        widget=forms.FileInput(attrs={
            'class': 'form-input',
            'accept': '.xlsx,.xls',
        }),
        help_text='Upload an Excel file (.xlsx) with question data.',
    )

    def clean_excel_file(self):
        uploaded = self.cleaned_data['excel_file']
        # Validate file extension
        name = uploaded.name.lower()
        if not name.endswith(('.xlsx', '.xls')):
            raise ValidationError('Only Excel files (.xlsx, .xls) are accepted.')
        # Limit file size (10 MB)
        if uploaded.size > 10 * 1024 * 1024:
            raise ValidationError('File size must be under 10 MB.')
        return uploaded


# ──────────────────────────────────────────────
# EXAM REQUEST FORMS
# ──────────────────────────────────────────────

class ExamRequestForm(forms.ModelForm):
    """Student form to request exam access."""

    class Meta:
        model = ExamRequest
        fields = ['category']
        widgets = {
            'category': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Ensure only non-empty categories are shown
        self.fields['category'].queryset = Category.objects.all().order_by('name')
        self.fields['category'].empty_label = "Select a Category"


class ExamRequestReviewForm(forms.Form):
    """Admin form for approving/rejecting exam requests."""

    action = forms.ChoiceField(
        choices=[('approve', 'Approve'), ('reject', 'Reject')],
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    rejection_reason = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-input',
            'rows': 3,
            'placeholder': 'Reason for rejection (required if rejecting)...',
        }),
    )

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('action') == 'reject' and not cleaned.get('rejection_reason', '').strip():
            raise ValidationError(
                {'rejection_reason': 'A reason is required when rejecting a request.'}
            )
        return cleaned
