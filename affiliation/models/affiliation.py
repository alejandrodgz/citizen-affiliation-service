from django.db import models
from .citizen import Citizen


class Affiliation(models.Model):
    """
    Model representing the affiliation relationship between a citizen and an operator.
    Tracks the citizen's current status with the operator (affiliated, transferring, transferred).
    """

    STATUS_CHOICES = [
        ("AFFILIATED", "Affiliated"),  # Currently affiliated with this operator
        ("TRANSFERRING", "Transferring"),  # In process of being transferred
        ("TRANSFERRED", "Transferred"),  # Successfully transferred to another operator
        ("CANCELLED", "Cancelled"),  # Affiliation cancelled/removed
    ]

    citizen = models.OneToOneField(
        Citizen,
        on_delete=models.CASCADE,
        related_name="affiliation",
        help_text="The citizen affiliated with the operator",
    )
    operator_id = models.CharField(
        max_length=100, help_text="ID of the operator this citizen is affiliated with"
    )
    operator_name = models.CharField(
        max_length=255, help_text="Name of the operator this citizen is affiliated with"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="AFFILIATED",
        db_index=True,
        help_text="Current affiliation status",
    )
    affiliated_at = models.DateTimeField(
        auto_now_add=True, help_text="When the citizen was first affiliated"
    )
    status_changed_at = models.DateTimeField(
        auto_now=True, help_text="Last time the status was changed"
    )
    transfer_destination_operator_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Operator ID where citizen is being/was transferred to",
    )
    transfer_destination_operator_name = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Operator name where citizen is being/was transferred to",
    )
    transfer_destination_api_url = models.URLField(
        max_length=500,
        blank=True,
        null=True,
        help_text="API URL of the target operator for transfer",
    )
    notes = models.TextField(
        blank=True, null=True, help_text="Additional notes about the affiliation"
    )

    # Transfer tracking fields
    transfer_source_operator_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Operator ID where citizen is being transferred from (for incoming transfers)",
    )
    transfer_source_operator_name = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Operator name where citizen is being transferred from",
    )
    transfer_confirmation_url = models.URLField(
        max_length=500, blank=True, null=True, help_text="URL to call for transfer confirmation"
    )
    transfer_started_at = models.DateTimeField(
        blank=True, null=True, help_text="When the transfer process started"
    )
    transfer_completed_at = models.DateTimeField(
        blank=True, null=True, help_text="When the transfer was completed"
    )
    documents_ready = models.BooleanField(
        default=False,
        help_text="Whether documents have been downloaded and uploaded by document service",
    )

    class Meta:
        db_table = "affiliations"
        ordering = ["-affiliated_at"]
        indexes = [
            models.Index(fields=["status", "affiliated_at"]),
            models.Index(fields=["operator_id"]),
        ]
        verbose_name = "Affiliation"
        verbose_name_plural = "Affiliations"

    def __str__(self):
        return f"{self.citizen.name} - {self.operator_name} ({self.status})"

    def start_transfer(self, destination_operator_id: str, destination_operator_name: str):
        """Mark affiliation as transferring to another operator."""
        self.status = "TRANSFERRING"
        self.transfer_destination_operator_id = destination_operator_id
        self.transfer_destination_operator_name = destination_operator_name
        self.save()

    def complete_transfer(self):
        """Mark affiliation as transferred."""
        self.status = "TRANSFERRED"
        self.save()

    def cancel_affiliation(self):
        """Cancel the affiliation."""
        self.status = "CANCELLED"
        self.save()
