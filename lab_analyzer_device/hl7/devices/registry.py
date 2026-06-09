"""Device profile registry — maps device_type strings to profile instances."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lab_analyzer_device.hl7.devices.base import DeviceHL7Profile


class DeviceProfileRegistry:
    """
    Registry for device HL7 profiles.

    Device profile modules call `registry.register(ProfileClass)` at import time
    to self-register. The registry is populated when `_ensure_loaded()` triggers
    discovery of all device modules in this package.
    """

    def __init__(self):
        self._profiles: dict[str, DeviceHL7Profile] = {}
        self._loaded = False

    def register(self, profile_cls: type[DeviceHL7Profile]) -> None:
        """Register a device profile class. Instantiates it and stores by device_type."""
        instance = profile_cls()
        self._profiles[instance.device_type] = instance

    def _ensure_loaded(self) -> None:
        """Import all device modules to trigger their self-registration."""
        if self._loaded:
            return
        self._loaded = True

        import importlib
        import pkgutil
        import lab_analyzer_device.hl7.devices as devices_pkg

        for importer, modname, ispkg in pkgutil.iter_modules(devices_pkg.__path__):
            if modname.startswith("test_") or modname in ("base", "registry"):
                continue
            importlib.import_module(f"lab_analyzer_device.hl7.devices.{modname}")

    def get_profiles(self) -> dict[str, DeviceHL7Profile]:
        """Get all registered device profiles."""
        self._ensure_loaded()
        return self._profiles

    def get_profile(self, device_type: str) -> DeviceHL7Profile:
        """
        Get the HL7 profile for a device type.

        Falls back to the generic profile if the device type is unknown.
        """
        self._ensure_loaded()
        if device_type in self._profiles:
            return self._profiles[device_type]
        return self._profiles["generic"]


# Module-level singleton
registry = DeviceProfileRegistry()
