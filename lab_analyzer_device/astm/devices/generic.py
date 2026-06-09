"""Generic ASTM device profile — fallback for analyzers speaking standard E1394.

Reuses the generic HL7 profile's LOINC code mappings so common analytes
resolve identically regardless of the wire protocol.
"""

from __future__ import annotations

from lab_analyzer_device.astm.devices.base import DeviceASTMProfile
from lab_analyzer_device.astm.devices.registry import registry
from lab_analyzer_device.hl7.devices.base import LoincMapping
from lab_analyzer_device.hl7.devices.generic import GenericDeviceProfile


class GenericASTMProfile(DeviceASTMProfile):
    """Generic ASTM E1394 device profile used as the fallback for unknown models."""

    @property
    def device_type(self) -> str:
        return "generic"

    @property
    def display_name(self) -> str:
        return "Generic Lab Analyzer (ASTM)"

    @property
    def code_mappings(self) -> dict[str, LoincMapping]:
        return GenericDeviceProfile().code_mappings


registry.register(GenericASTMProfile)
