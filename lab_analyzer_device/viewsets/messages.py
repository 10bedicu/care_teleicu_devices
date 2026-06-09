from care.emr.api.viewsets.base import EMRModelReadOnlyViewSet
from lab_analyzer_device.authorization import (
    authorize_read_lab_analyzer,
    get_lab_analyzer_device,
)
from lab_analyzer_device.models import LabMessage
from lab_analyzer_device.spec import LabMessageReadSpec


class LabMessageViewSet(EMRModelReadOnlyViewSet):
    database_model = LabMessage
    pydantic_read_model = LabMessageReadSpec
    pydantic_retrieve_model = LabMessageReadSpec

    def get_lab_analyzer_device(self):
        return get_lab_analyzer_device(self.kwargs["device_external_id"])

    def get_queryset(self):
        device = self.get_lab_analyzer_device()
        authorize_read_lab_analyzer(self.request.user, device)
        return (
            super()
            .get_queryset()
            .filter(device=device)
            .select_related("device", "patient", "encounter")
            .order_by("-created_date")
        )
