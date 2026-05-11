"""
View mixins for role-based access control.

These enforce:
    • Superuser-only access for the admin dashboard
    • Login-required for student views
    • No reliance on django.contrib.admin permissions
"""

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import redirect


class SuperuserRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """
    Restricts view access to superusers only.

    Used on every admin dashboard view to ensure only users with
    is_superuser=True can access the custom admin panel.
    """

    def test_func(self):
        return self.request.user.is_superuser

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return redirect('login')
        # Authenticated but not superuser — send to student dashboard
        return redirect('student_dashboard')


class BaseAdminRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """
    Restricts access to either Superusers (Admin) or Sub Admins.
    Used for general dashboard views.
    """
    def test_func(self):
        user = self.request.user
        return user.is_authenticated and (user.is_superuser or user.role == 'Sub Admin')

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return redirect('login')
        return redirect('student_dashboard')


class StudentRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """
    Restricts view access to authenticated students only.
    """

    def test_func(self):
        user = self.request.user
        return user.is_authenticated and user.role == 'Student' and not user.is_superuser

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return redirect('login')
        if self.request.user.is_superuser or self.request.user.role == 'Sub Admin':
            return redirect('admin_dashboard')
        return redirect('login')
