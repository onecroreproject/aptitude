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
import re

# ──────────────────────────────────────────────
# VALIDATION HELPERS
# ──────────────────────────────────────────────

def validate_complex_password(password):
    if len(password) < 8:
        raise ValidationError("Password must be at least 8 characters.")
    if not re.search(r'[A-Z]', password):
        raise ValidationError("Password must contain at least one uppercase letter.")
    if not re.search(r'[a-z]', password):
        raise ValidationError("Password must contain at least one lowercase letter.")
    if not re.search(r'\d', password):
        raise ValidationError("Password must contain at least one number.")
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        raise ValidationError("Password must contain at least one special character.")
    return password

def validate_email_unique(email, exclude_user_id=None):
    email = email.strip().lower()
    if not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email):
        raise ValidationError("Please enter a valid email address.")
    qs = CustomUser.objects.filter(email=email)
    if exclude_user_id:
        qs = qs.exclude(id=exclude_user_id)
    if qs.exists():
        raise ValidationError("A user with this email already exists.")
    return email

def validate_phone_number(phone_number, field_name="Phone number", exclude_user_id=None):
    if not phone_number:
        return phone_number
    phone_number = phone_number.strip()
    if not re.match(r'^\d{10}$', phone_number):
        raise ValidationError(f"{field_name} must be exactly 10 digits and numeric.")
    
    # Check for duplicates
    # Depending on the field, we query phone_number or whatsapp_number
    qs = CustomUser.objects.filter(**{field_name.lower().replace(' ', '_'): phone_number})
    if exclude_user_id:
        qs = qs.exclude(id=exclude_user_id)
    if qs.exists():
        raise ValidationError(f"This {field_name.lower()} is already in use.")
    return phone_number

def validate_profile_image(photo):
    if not photo:
        return photo
    # Check file extension
    ext = photo.name.split('.')[-1].lower()
    if ext not in ['jpg', 'jpeg', 'png', 'webp']:
        raise ValidationError("Profile image must be in JPG, JPEG, PNG, or WEBP format.")
    # Check file size (5MB)
    if photo.size > 5 * 1024 * 1024:
        raise ValidationError("Profile image size must not exceed 5 MB.")
    return photo


# ──────────────────────────────────────────────
# AUTHENTICATION FORMS
# ──────────────────────────────────────────────

class StudentRegistrationForm(UserCreationForm):
    """
    Registration form for students with comprehensive backend validation.
    """
    first_name = forms.CharField(max_length=50, required=True, widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'First Name'}))
    last_name = forms.CharField(max_length=50, required=True, widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Last Name'}))
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={'class': 'form-input', 'placeholder': 'Email Address'}))
    institution = forms.CharField(max_length=150, required=True, widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Institution / College'}))
    date_of_birth = forms.DateField(required=True, widget=forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}))
    phone_number = forms.CharField(max_length=10, required=True, widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Phone Number'}))
    whatsapp_number = forms.CharField(max_length=10, required=True, widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'WhatsApp Number'}))
    profile_image = forms.ImageField(required=True, widget=forms.FileInput(attrs={'class': 'form-input', 'accept': '.jpg,.jpeg,.png,.webp'}))

    class Meta:
        model = CustomUser
        fields = [
            'username', 'first_name', 'last_name', 'email', 
            'institution', 'date_of_birth',
            'phone_number', 'whatsapp_number', 
            'profile_image'
        ]
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Username', 'autocomplete': 'username'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'password1' in self.fields:
            self.fields['password1'].widget.attrs.update({'class': 'form-input', 'placeholder': 'Password'})
        if 'password2' in self.fields:
            self.fields['password2'].widget.attrs.update({'class': 'form-input', 'placeholder': 'Confirm Password'})

    def _trim_and_collapse_spaces(self, text):
        import re
        return re.sub(r'\s+', ' ', str(text).strip()) if text else text

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if username:
            username = username.strip().lower()
            import re
            if not re.match(r'^[a-z0-9_]{4,30}$', username):
                raise forms.ValidationError("Username must be 4-30 characters long and contain only lowercase letters, numbers, and underscores.")
            if CustomUser.objects.filter(username=username).exists():
                raise forms.ValidationError("Username already exists.")
        return username

    def clean_first_name(self):
        first_name = self._trim_and_collapse_spaces(self.cleaned_data.get('first_name'))
        if first_name:
            import re
            if not re.match(r'^[a-zA-Z\s]{2,50}$', first_name):
                raise forms.ValidationError("First name must be 2-50 characters long and contain only letters.")
        return first_name

    def clean_last_name(self):
        last_name = self._trim_and_collapse_spaces(self.cleaned_data.get('last_name'))
        if last_name:
            import re
            if not re.match(r'^[a-zA-Z\s]{2,50}$', last_name):
                raise forms.ValidationError("Last name must be 2-50 characters long and contain only letters.")
        return last_name

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email:
            email = email.replace(" ", "").lower()
            return validate_email_unique(email)
        return email
        
    def clean_institution(self):
        inst = self._trim_and_collapse_spaces(self.cleaned_data.get('institution'))
        if inst:
            if len(inst) < 3 or len(inst) > 150:
                raise forms.ValidationError("Institution must be between 3 and 150 characters.")
            if inst.isdigit():
                raise forms.ValidationError("Institution cannot contain only numbers.")
        return inst

    def clean_date_of_birth(self):
        dob = self.cleaned_data.get('date_of_birth')
        if dob:
            from datetime import date
            today = date.today()
            if dob > today:
                raise forms.ValidationError("Future dates are not allowed.")
            age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
            if age < 10 or age > 100:
                raise forms.ValidationError("Student age must be between 10 and 100 years.")
        return dob

    def clean_phone_number(self):
        phone = self.cleaned_data.get('phone_number')
        if phone:
            phone = phone.replace(" ", "")
            if not phone.isdigit() or len(phone) != 10:
                raise forms.ValidationError("Phone number must be exactly 10 digits.")
            return validate_phone_number(phone, "Phone number")
        return phone
        
    def clean_whatsapp_number(self):
        wa = self.cleaned_data.get('whatsapp_number')
        if wa:
            wa = wa.replace(" ", "")
            if not wa.isdigit() or len(wa) != 10:
                raise forms.ValidationError("WhatsApp number must be exactly 10 digits.")
        return wa
        
    def clean_profile_image(self):
        return validate_profile_image(self.cleaned_data.get('profile_image'))
        
    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password1")
        if password:
            validate_complex_password(password)
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = CustomUser.Role.STUDENT
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

    def clean_email(self):
        email = self.cleaned_data.get('email')
        return validate_email_unique(email, exclude_user_id=self.instance.id if self.instance else None)

    def clean_phone_number(self):
        return validate_phone_number(self.cleaned_data.get('phone_number'), "Phone number", exclude_user_id=self.instance.id if self.instance else None)

    def clean_password(self):
        password = self.cleaned_data.get('password')
        if password:
            validate_complex_password(password)
        return password

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
        
        if password:
            validate_complex_password(password)

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
            'institution', 'profile_image'
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
            'profile_image': forms.FileInput(attrs={'class': 'form-input', 'accept': '.jpg,.jpeg,.png,.webp'}),
        }

    def clean_email(self):
        email = self.cleaned_data.get('email')
        return validate_email_unique(email, exclude_user_id=self.instance.id if self.instance else None)

    def clean_phone_number(self):
        return validate_phone_number(self.cleaned_data.get('phone_number'), "Phone number", exclude_user_id=self.instance.id if self.instance else None)
        
    def clean_whatsapp_number(self):
        return validate_phone_number(self.cleaned_data.get('whatsapp_number'), "WhatsApp number", exclude_user_id=self.instance.id if self.instance else None)
        
    def clean_profile_image(self):
        return validate_profile_image(self.cleaned_data.get('profile_image'))


class AdminProfileForm(forms.ModelForm):
    """
    Profile update form for Admin and Sub-Admin.
    """

    class Meta:
        model = CustomUser
        fields = [
            'first_name', 'last_name', 'email', 'phone_number', 
            'profile_image'
        ]
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'First Name'}),
            'last_name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Last Name'}),
            'email': forms.EmailInput(attrs={'class': 'form-input', 'placeholder': 'Email'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Phone Number'}),
            'profile_image': forms.FileInput(attrs={'class': 'form-input', 'accept': '.jpg,.jpeg,.png,.webp'}),
        }

    def clean_email(self):
        email = self.cleaned_data.get('email')
        return validate_email_unique(email, exclude_user_id=self.instance.id if self.instance else None)

    def clean_phone_number(self):
        return validate_phone_number(self.cleaned_data.get('phone_number'), "Phone number", exclude_user_id=self.instance.id if self.instance else None)
        
    def clean_profile_image(self):
        return validate_profile_image(self.cleaned_data.get('profile_image'))


# ──────────────────────────────────────────────
# CATEGORY FORM (ADMIN DASHBOARD)
# ──────────────────────────────────────────────

class CategoryForm(forms.ModelForm):
    """
    Form for creating / editing categories in the admin dashboard.
    """

    class Meta:
        model = Category
        fields = ['name', 'description', 'pass_mark']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Category Name (e.g. Python)'}),
            'description': forms.Textarea(attrs={'class': 'form-input', 'rows': 3, 'placeholder': 'Optional description...'}),
            'pass_mark': forms.NumberInput(attrs={'class': 'form-input', 'step': '0.01', 'min': '0', 'max': '100', 'placeholder': 'Pass Mark (e.g. 35)'}),
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
