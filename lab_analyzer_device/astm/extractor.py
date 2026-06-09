"""ASTM result extraction — delegates to the device profile.

Mirrors :func:`lab_analyzer_device.hl7.extractor.extract_oru_data` so the
communication viewset can treat both protocols uniformly.
"""

from __future__ import annotations

from lab_analyzer_device.astm.devices.registry import registry
from lab_analyzer_device.hl7.extractor import ORUData


def extract_astm_data(
    records: list[str], device_type: str, device_metadata: dict | None = None
) -> ORUData:
    """Parse ASTM result records into :class:`ORUData` using the device profile."""
    profile = registry.get_profile(device_type)
    return profile.extract_result_data(records, device_metadata)
