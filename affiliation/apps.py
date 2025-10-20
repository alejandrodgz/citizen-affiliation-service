from django.apps import AppConfig


class AffiliationConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "affiliation"

    def ready(self):
        """Import signal handlers and other app initialization code."""
        import affiliation.signals  # noqa
