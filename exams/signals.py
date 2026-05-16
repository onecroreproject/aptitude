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
    Keep ``role``, ``is_superuser`` and ``is_staff`` consistent on every save.

    Precedence rule: the ``is_superuser`` flag is authoritative. This
    guarantees accounts created via ``python manage.py createsuperuser``
    keep their superuser status — that command sets ``is_superuser=True``
    but leaves ``role`` at its model default (``'Student'``), and we must
    not let the role default downgrade the freshly-set superuser flag.

    - is_superuser=True  → role auto-promoted to Admin, is_staff forced True.
    - role=Admin         → is_superuser & is_staff forced True (self-heal).
    - role=Sub Admin     → is_staff forced True, is_superuser forced False.
    - role=Student       → is_staff & is_superuser forced False
                           (only reached when is_superuser was not set above).
    """
    if instance.is_superuser:
        # Superuser flag wins: keep flags + bring role into alignment.
        instance.role = CustomUser.Role.ADMIN
        instance.is_staff = True
        return

    if instance.role == CustomUser.Role.ADMIN:
        # Admin role without superuser flag is invalid — self-heal.
        instance.is_superuser = True
        instance.is_staff = True
    elif instance.role == CustomUser.Role.SUB_ADMIN:
        instance.is_staff = True
        instance.is_superuser = False
    elif instance.role == CustomUser.Role.STUDENT:
        instance.is_staff = False
        instance.is_superuser = False
