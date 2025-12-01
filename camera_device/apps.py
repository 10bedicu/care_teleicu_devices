from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _

PLUGIN_NAME = "camera_device"


class CameraDeviceConfig(AppConfig):
    name = PLUGIN_NAME
    verbose_name = _("Camera Device")

    def ready(self):
        """
        Import models, signals, and other dependencies here to ensure
        Django's app registry is fully initialized before use.
        """
        from care.emr.registries.device_type.device_registry import DeviceTypeRegistry
        from camera_device.device import CameraDevice
        from camera_device.permissions import CameraDeviceControlPermissions, CameraDeviceControlAccess # noqa: F401

        try:
            DeviceTypeRegistry.get_care_device_class("gateway")
        except ValueError as e:
            raise ImportError(
                "Camera device requires the gateway_device plugin. Ensure the gateway_device plugin is installed and registered."
            ) from e

        DeviceTypeRegistry.register("camera", CameraDevice)
