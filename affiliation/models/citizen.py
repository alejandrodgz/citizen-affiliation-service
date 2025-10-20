from django.db import models


class Citizen(models.Model):
    """Model representing a citizen in the affiliation system."""

    VERIFICATION_PENDING = "pending"
    VERIFICATION_VERIFIED = "verified"
    VERIFICATION_FAILED = "failed"

    VERIFICATION_STATUS_CHOICES = [
        (VERIFICATION_PENDING, "Pending MINTIC Verification"),
        (VERIFICATION_VERIFIED, "Verified by MINTIC"),
        (VERIFICATION_FAILED, "Verification Failed"),
    ]

    citizen_id = models.CharField(max_length=50, unique=True, db_index=True)
    name = models.CharField(max_length=255)
    address = models.CharField(max_length=500)
    email = models.EmailField()
    operator_id = models.CharField(max_length=100)
    operator_name = models.CharField(max_length=255)
    is_registered = models.BooleanField(default=False)
    is_verified = models.BooleanField(
        default=False, help_text="Whether registration is confirmed by MINTIC"
    )
    verification_status = models.CharField(
        max_length=50,
        default=VERIFICATION_PENDING,
        choices=VERIFICATION_STATUS_CHOICES,
        help_text="Current verification status",
    )
    pending_deletion = models.BooleanField(
        default=False, help_text="Whether citizen is pending deletion after unregister"
    )
    verification_message = models.TextField(
        blank=True, null=True, help_text="Message from MINTIC verification"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "citizens"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["citizen_id"]),
            models.Index(fields=["email"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.citizen_id})"
