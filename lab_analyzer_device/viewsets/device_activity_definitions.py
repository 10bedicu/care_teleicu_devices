from django_filters import rest_framework as filters
from rest_framework.exceptions import PermissionDenied, ValidationError

from care.emr.api.viewsets.base import (
    EMRBaseViewSet,
    EMRCreateMixin,
    EMRDestroyMixin,
    EMRListMixin,
)
from care.emr.models import ActivityDefinition, Device
from care.security.authorization import AuthorizationController
from care.utils.shortcuts import get_object_or_404
from lab_analyzer_device.authorization import (
    authorize_manage_lab_analyzer,
    authorize_read_lab_analyzer,
    get_lab_analyzer_device,
)
from lab_analyzer_device.models import DeviceActivityDefinition
from lab_analyzer_device.spec import (
    DeviceActivityDefinitionCreateSpec,
    DeviceActivityDefinitionReadSpec,
)


class DeviceActivityDefinitionFilters(filters.FilterSet):
    activity_definition = filters.UUIDFilter(
        field_name="activity_definition__external_id", lookup_expr="exact"
    )


class DeviceActivityDefinitionViewSet(
    EMRCreateMixin,
    EMRListMixin,
    EMRDestroyMixin,
    EMRBaseViewSet,
):
    database_model = DeviceActivityDefinition
    pydantic_model = DeviceActivityDefinitionCreateSpec
    pydantic_read_model = DeviceActivityDefinitionReadSpec
    pydantic_retrieve_model = DeviceActivityDefinitionReadSpec
    filterset_class = DeviceActivityDefinitionFilters
    filter_backends = (filters.DjangoFilterBackend,)

    def get_lab_analyzer_device(self):
        return get_lab_analyzer_device(self.kwargs["device_external_id"])

    def authorize_create(self, instance):
        device = self.get_lab_analyzer_device()
        authorize_manage_lab_analyzer(self.request.user, device)

    def authorize_destroy(self, instance):
        authorize_manage_lab_analyzer(self.request.user, instance.device)

    def get_queryset(self):
        qs = super().get_queryset().select_related("device", "activity_definition")

        device_external_id = self.kwargs.get("device_external_id")
        if device_external_id:
            device = self.get_lab_analyzer_device()
            authorize_read_lab_analyzer(self.request.user, device)
            return qs.filter(device=device)

        activity_definition_id = self.request.GET.get("activity_definition")
        if not activity_definition_id:
            raise ValidationError(
                {"activity_definition": "This query parameter is required"}
            )

        activity_definition = get_object_or_404(
            ActivityDefinition, external_id=activity_definition_id
        )
        qs = qs.filter(
            activity_definition=activity_definition,
            device__facility=activity_definition.facility,
            device__care_type="lab-analyzer",
        )

        representative_device = Device.objects.filter(
            care_type="lab-analyzer",
            facility=activity_definition.facility,
        ).first()
        if representative_device:
            authorize_read_lab_analyzer(self.request.user, representative_device)
        elif not AuthorizationController.call(
            "can_create_device", self.request.user, activity_definition.facility
        ):
            raise PermissionDenied(
                "You do not have permission to access activity definitions "
                "for this facility"
            )

        return qs

    def perform_destroy(self, instance):
        # Hard delete - junction table has unique constraint, soft delete causes conflicts
        type(instance).objects.filter(pk=instance.pk).delete()
