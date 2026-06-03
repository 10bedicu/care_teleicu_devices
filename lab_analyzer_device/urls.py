from django.conf import settings
from rest_framework.routers import DefaultRouter, SimpleRouter

from lab_analyzer_device.viewsets.communication import LabAnalyzerCommunicationViewSet
from lab_analyzer_device.viewsets.actions import LabAnalyzerActionsViewSet
from lab_analyzer_device.viewsets.messages import LabMessageViewSet
from lab_analyzer_device.viewsets.metadata import LabAnalyzerMetadataViewSet
from lab_analyzer_device.viewsets.device_activity_definitions import (
    DeviceActivityDefinitionViewSet,
)

router = DefaultRouter() if settings.DEBUG else SimpleRouter()

router.register(
    "metadata",
    LabAnalyzerMetadataViewSet,
    basename="lab-analyzer-metadata",
)

router.register(
    "communication",
    LabAnalyzerCommunicationViewSet,
    basename="lab-analyzer-communication",
)

router.register(
    "actions",
    LabAnalyzerActionsViewSet,
    basename="lab-analyzer-actions",
)

router.register(
    "devices/(?P<device_external_id>[^/.]+)/messages",
    LabMessageViewSet,
    basename="lab-analyzer-messages",
)

router.register(
    "devices/(?P<device_external_id>[^/.]+)/activity_definitions",
    DeviceActivityDefinitionViewSet,
    basename="lab-analyzer-activity-definitions",
)

# Global activity definition lookup (find analyzers for a test)
router.register(
    "activity_definitions",
    DeviceActivityDefinitionViewSet,
    basename="lab-analyzer-activity-definitions-global",
)

urlpatterns = router.urls
