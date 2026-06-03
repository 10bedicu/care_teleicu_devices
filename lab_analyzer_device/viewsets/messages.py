from care.emr.api.viewsets.base import EMRModelReadOnlyViewSet
from lab_analyzer_device.models import LabMessage
from lab_analyzer_device.spec import LabMessageReadSpec


class LabMessageViewSet(EMRModelReadOnlyViewSet):
    database_model = LabMessage
    pydantic_read_model = LabMessageReadSpec
    pydantic_retrieve_model = LabMessageReadSpec

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .filter(device__external_id=self.kwargs["device_external_id"])
            .select_related("device", "patient", "encounter")
            .order_by("-created_date")
        )
