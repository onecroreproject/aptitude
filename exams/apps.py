from django.apps import AppConfig


class ExamsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "exams"
    verbose_name = "Online Examination System"

    def ready(self):
        # Import signals when app is ready
        import exams.signals  # noqa: F401
