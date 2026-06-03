from django.db import models

from care.emr.models.base import EMRBaseModel


class MessageType(models.TextChoices):
    ORM = "ORM", "Order Message"
    ORU = "ORU", "Observation Result"
    QRY = "QRY", "Query"
    DSP = "DSP", "Worklist Response"


class MessageStatus(models.TextChoices):
    SENT = "sent", "Sent"
    RECEIVED = "received", "Received"
    ACKNOWLEDGED = "acknowledged", "Acknowledged"
    PROCESSED = "processed", "Processed"
    REJECTED = "rejected", "Rejected"
    ERROR = "error", "Error"


class LabMessage(EMRBaseModel):
    device = models.ForeignKey(
        "emr.Device", on_delete=models.CASCADE, related_name="lab_messages"
    )
    patient = models.ForeignKey(
        "emr.Patient",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="lab_messages",
    )
    encounter = models.ForeignKey(
        "emr.Encounter",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="lab_messages",
    )
    specimen = models.ForeignKey(
        "emr.Specimen",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="lab_messages",
    )
    message_type = models.CharField(max_length=10, choices=MessageType.choices)
    message_control_id = models.CharField(max_length=199)
    raw_message = models.TextField()
    parsed_data = models.JSONField(default=dict)
    status = models.CharField(
        max_length=20, choices=MessageStatus.choices, default=MessageStatus.RECEIVED
    )
    error_details = models.TextField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["message_type", "message_control_id"]),
            models.Index(fields=["device", "message_type"]),
        ]

    def __str__(self):
        return f"{self.message_type} {self.message_control_id} ({self.status})"
