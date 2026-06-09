from __future__ import annotations

import hl7

from pydantic import BaseModel


class OrderedTest(BaseModel):
    code: str
    display: str = ""
    system: str = "http://loinc.org"


class OrderingPhysician(BaseModel):
    id: str = ""
    family_name: str = ""
    given_name: str = ""


class ORMData(BaseModel):
    patient_id: str
    placer_order_number: str
    filler_order_number: str | None = None
    patient_name: str = ""
    date_of_birth: str | None = None  # HL7 format: YYYYMMDD
    gender: str = ""  # HL7 v2.x administrative gender code (M, F, O, U)
    ordering_physician: OrderingPhysician | None = None
    tests: list[OrderedTest] = []
    specimen_id: str | None = None


def build_orm_message(order_data: ORMData, device_type: str = "generic", device_metadata: dict | None = None) -> hl7.Message:
    """
    Build an order HL7 message using the device profile.

    Delegates to the appropriate DeviceHL7Profile based on device_type.

    Args:
        order_data: Order parameters
        device_type: Device type string (matches a registered profile)
        device_metadata: Optional device metadata for overriding panel/code mappings

    Returns:
        hl7.Message ready for serialization with str()
    """
    from lab_analyzer_device.hl7.devices.registry import registry

    profile = registry.get_profile(device_type)
    return profile.build_order_message(order_data, device_metadata=device_metadata)
