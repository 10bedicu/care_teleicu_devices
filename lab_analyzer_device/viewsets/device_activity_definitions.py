from django_filters import rest_framework as filters

from care.emr.api.viewsets.base import EMRModelViewSet, EMRCreateMixin, EMRListMixin, EMRDestroyMixin, EMRBaseViewSet
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

    def get_queryset(self):
        qs = super().get_queryset().select_related("device", "activity_definition")

        device_external_id = self.kwargs.get("device_external_id")
        if device_external_id:
            qs = qs.filter(device__external_id=device_external_id)

        return qs

    def perform_destroy(self, instance):
        # Hard delete - junction table has unique constraint, soft delete causes conflicts
        type(instance).objects.filter(pk=instance.pk).delete()
