from care.emr.api.viewsets.base import EMRModelReadOnlyViewSet
from care.emr.models import Device
from care.emr.models import FacilityLocation, Encounter
from care.emr.resources.device.spec import (
    DeviceListSpec,
    DeviceRetrieveSpec,
)
from care.emr.resources.encounter.constants import StatusChoices
from care.security.authorization import AuthorizationController
from rest_framework.exceptions import PermissionDenied
from rest_framework.generics import get_object_or_404


class PresetEncounterCameraViewSet(EMRModelReadOnlyViewSet):
    database_model = Device
    pydantic_read_model = DeviceListSpec
    pydantic_retrieve_model = DeviceRetrieveSpec


    def get_encounter_obj(self):
        return get_object_or_404(
            Encounter, external_id=self.kwargs["encounter_external_id"]
        )

    def get_queryset(self):
        encounter = self.get_encounter_obj()
        location = encounter.current_location
        queryset = super().get_queryset()
        if encounter.status == StatusChoices.completed or not encounter.current_location:
            return queryset.none()
        if not AuthorizationController.call(
            "can_read_devices_on_location", self.request.user, location
        ):
            raise PermissionDenied(
                "You do not have permission to get devices of this location."
            )
        return (
            queryset
            .filter(
                care_type="camera",
                position_presets__location=location,
            )
            .distinct("id")
        )
