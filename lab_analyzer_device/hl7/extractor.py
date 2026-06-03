from __future__ import annotations

import hl7

from pydantic import BaseModel

from lab_analyzer_device.hl7.builder import OrderedTest


class ObservationData(BaseModel):
    set_id: int
    value_type: str
    code: str
    display: str
    system: str
    value: str
    units: str
    reference_range: str
    abnormal_flags: str
    result_status: str
    observation_datetime: str | None = None


class OrderingPhysicianData(BaseModel):
    id: str = ""
    family_name: str = ""
    given_name: str = ""


class ORUData(BaseModel):
    """
    Unified HL7 patient/order/result payload.

    Originally modelled on ORU^R01 results, this is also used to carry
    pending-order worklist data shared with host-query analyzers (the
    ``tests`` and logistics fields below). Result extraction populates
    ``observations``; worklist building populates ``tests``.
    """

    patient_id: str | None = None
    patient_name: str | None = None
    date_of_birth: str | None = None  # HL7 format: YYYYMMDD
    gender: str | None = None  # HL7 v2.x administrative gender code (M, F, O, U)
    placer_order_number: str | None = None
    filler_order_number: str | None = None
    specimen_id: str | None = None
    ordering_physician: OrderingPhysicianData | None = None
    observations: list[ObservationData] = []

    # Worklist / order-sharing fields (host-query download to analyzers)
    sample_id: str | None = None
    sample_type: str | None = None
    department: str | None = None
    bed: str | None = None
    patient_class: str | None = None
    collect_time: str | None = None
    barcode: str | None = None
    priority: str | None = None
    test_mode: str | None = None
    blood_mode: str | None = None
    tests: list[OrderedTest] = []


def _str(segment, field: int, component: int = 0) -> str:
    """
    Safely extract a string from an HL7 segment field/component using the hl7 library.

    Args:
        segment: hl7.Segment object
        field: 1-based field index
        component: 1-based component index (0 = full field value)
    """
    try:
        f = segment(field)
        if component > 0:
            rep = f[0]  # first repetition
            # If the repetition is a plain string (no component separator was present),
            # it's a single-component field — return it for component 1, empty otherwise
            if isinstance(rep, str):
                return rep.strip() if component == 1 else ""
            idx = component - 1
            if idx < len(rep):
                return str(rep[idx]).strip()
            return ""
        return str(f).strip()
    except (IndexError, KeyError, AttributeError):
        return ""


def extract_oru_data(message: hl7.Message, device_type: str) -> ORUData:
    """
    Extract domain data from an HL7 result message using the device profile.

    Delegates to the appropriate DeviceHL7Profile based on device_type.

    Args:
        message: Parsed hl7.Message
        device_type: Device type string (matches a registered profile)

    Returns:
        ORUData with extracted patient, order, and observation information
    """
    from lab_analyzer_device.hl7.devices.registry import registry

    profile = registry.get_profile(device_type)
    return profile.extract_result_data(message)
