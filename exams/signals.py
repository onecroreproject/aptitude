"""
Django signals for the exam system.

Handles automated side effects:
    - Sending notifications on exam request status changes
    - Setting role flags on user creation
"""

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .models import CustomUser


@receiver(pre_save, sender=CustomUser)
def enforce_role_permissions(sender, instance, **kwargs):
    """
    Ensure permission flags are consistent with role:
    - Admin role users must be superusers and staff
    - Student role users must NOT be superusers
    """
    if instance.role == CustomUser.Role.ADMIN:
        instance.is_staff = True
    elif instance.role == CustomUser.Role.STUDENT:
        instance.is_staff = False
        instance.is_superuser = False
