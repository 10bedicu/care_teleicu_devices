"""
Device HL7 profile system.

Each lab analyzer model has its own profile that defines:
- HL7 version and message types
- Code mappings (device codes → LOINC)
- Result extraction from ORU messages
- Order message building
- OBX segment filtering

Profiles are registered via the registry module.
"""

from lab_analyzer_device.hl7.devices.base import CommunicationMode, DeviceHL7Profile
from lab_analyzer_device.hl7.devices.registry import registry

__all__ = ["CommunicationMode", "DeviceHL7Profile", "registry"]
