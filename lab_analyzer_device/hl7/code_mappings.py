"""Re-exports for backward compatibility."""

from lab_analyzer_device.hl7.devices.base import LoincMapping

__all__ = ["LoincMapping", "resolve_code"]


def resolve_code(device_type: str, code: str, system: str) -> tuple[str, str, str]:
    """
    Resolve a device-specific code to LOINC using the device profile.

    Returns (system, code, display).
    """
    from lab_analyzer_device.hl7.devices.registry import registry

    profile = registry.get_profile(device_type)
    return profile.resolve_code(code, system)
