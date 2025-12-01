from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _

PLUGIN_NAME = "vitals_observation_device"


class VitalsObservationDeviceConfig(AppConfig):
    name = PLUGIN_NAME
    verbose_name = _("Vitals Observation Device")

    def ready(self):
        """
        Import models, signals, and other dependencies here to ensure
        Django's app registry is fully initialized before use.
        """
        import vitals_observation_device.signals  # noqa

        from care.emr.registries.device_type.device_registry import DeviceTypeRegistry
        from vitals_observation_device.device import VitalsObservationDevice

        DeviceTypeRegistry.register("vitals-observation", VitalsObservationDevice)
