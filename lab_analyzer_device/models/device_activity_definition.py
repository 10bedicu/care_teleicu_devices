from django.db import models

from care.emr.models.base import EMRBaseModel


class DeviceActivityDefinition(EMRBaseModel):
    device = models.ForeignKey(
        "emr.Device",
        on_delete=models.CASCADE,
        related_name="activity_definitions",
    )
    activity_definition = models.ForeignKey(
        "emr.ActivityDefinition",
        on_delete=models.CASCADE,
        related_name="analyzer_devices",
    )

    class Meta:
        unique_together = ("device", "activity_definition")

    def __str__(self):
        return f"Device {self.device_id} <-> ActivityDefinition {self.activity_definition_id}"
