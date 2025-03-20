from django.conf import settings
from rest_framework.routers import DefaultRouter, SimpleRouter

from camera_device.viewsets.actions import CameraActionsViewSet
from camera_device.viewsets.position_preset import CameraPositionPresetViewSet
from camera_device.viewsets.preset_location_camera import PresetLocationCameraViewSet

router = DefaultRouter() if settings.DEBUG else SimpleRouter()

router.register("actions", CameraActionsViewSet, basename="camera-actions")
router.register(
    r"(?P<camera_external_id>[^/.]+)/position_presets",
    CameraPositionPresetViewSet,
    basename="camera-position-presets",
)
router.register(
    r"preset_location_cameras/(?P<location_external_id>[^/.]+)",
    PresetLocationCameraViewSet,
    basename="preset-location-cameras",
)

urlpatterns = router.urls
