import uuid

from drf_spectacular.utils import extend_schema
from pydantic import BaseModel, RootModel
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from care.emr.models import Device, Observation
from care.emr.resources.observation.spec import ObservationSpec
from care.emr.resources.questionnaire.spec import SubjectType
from vitals_observation_device.authentication import AutomatedObservationsAuthentication


class DeviceListSpec(BaseModel):
    id: str
    endpoint_address: str


class DeviceListResponse(RootModel[list[DeviceListSpec]]):
    pass


class RecordRequest(RootModel[list[ObservationSpec]]):
    pass


class AutomatedObservationsViewSet(GenericViewSet):
    queryset = Device.objects.filter(
        care_type="vitals-observation", current_encounter__isnull=False
    )
    lookup_field = "external_id"
    authentication_classes = (AutomatedObservationsAuthentication,)

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .filter(metadata__gateway=str(self.request.gateway.external_id))
        )

    @extend_schema(
        description="Lists vitals observation devices of the gateway that can be used for yielding automated observations.",
        responses={
            200: DeviceListResponse,
        },
    )
    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        return Response(
            [
                DeviceListSpec(
                    id=str(d.external_id),
                    endpoint_address=d.metadata["endpoint_address"],
                ).model_dump(mode="json")
                for d in queryset
            ]
        )

    @extend_schema(
        description="Callback for Gateway Device to post observations.",
        request=RecordRequest,
        responses={
            200: {"type": "object", "example": {"message": "ok"}},
            400: {"type": "object", "properties": {"error": {"type": "string"}}},
        },
    )
    @action(detail=True, methods=["post"])
    def record(self, request, *args, **kwargs):
        encounter = self.get_object().current_encounter
        if encounter is None:
            raise ValueError("No encounter associated with the device")
        observations_objects = [
            ObservationSpec(
                **observation,
                subject_type=SubjectType.encounter,
                encounter=encounter.external_id,
                data_entered_by_id=request.user.id,
                created_by_id=request.user.id,
                updated_by_id=request.user.id,
            )
            for observation in request.data
        ]
        bulk = []
        for observation in observations_objects:
            temp = observation.de_serialize()
            temp.patient = encounter.patient
            temp.encounter = encounter
            temp.subject_id = encounter.external_id
            temp.external_id = uuid.uuid4()
            bulk.append(temp)
        Observation.objects.bulk_create(bulk)
        return Response({"message": "ok"})
