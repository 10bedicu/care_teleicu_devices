"""ASTM device profile registry — maps device_type strings to profile instances."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lab_analyzer_device.astm.devices.base import DeviceASTMProfile


class ASTMDeviceProfileRegistry:
    """Registry for device ASTM profiles.

    Profile modules call ``registry.register(ProfileClass)`` at import time to
    self-register. Modules are discovered lazily on first access.
    """

    def __init__(self):
        self._profiles: dict[str, DeviceASTMProfile] = {}
        self._loaded = False

    def register(self, profile_cls: type[DeviceASTMProfile]) -> None:
        instance = profile_cls()
        self._profiles[instance.device_type] = instance

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        self._loaded = True

        import importlib
        import pkgutil

        import lab_analyzer_device.astm.devices as devices_pkg

        for _importer, modname, _ispkg in pkgutil.iter_modules(devices_pkg.__path__):
            if modname.startswith("test_") or modname in ("base", "registry"):
                continue
            importlib.import_module(f"lab_analyzer_device.astm.devices.{modname}")

    def get_profiles(self) -> dict[str, DeviceASTMProfile]:
        self._ensure_loaded()
        return self._profiles

    def get_profile(self, device_type: str) -> DeviceASTMProfile:
        """Return the ASTM profile for *device_type*, falling back to generic."""
        self._ensure_loaded()
        if device_type in self._profiles:
            return self._profiles[device_type]
        return self._profiles["generic"]


# Module-level singleton
registry = ASTMDeviceProfileRegistry()
