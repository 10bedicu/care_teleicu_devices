"""
External HL7 proxy device profile.

A dummy/proxy "device" used to forward lab requests to an external service that
mimics the MLLP gateway. Unlike physical analyzers, this profile speaks LOINC
natively in both directions, so no device-specific code or panel mappings are
needed:

- Orders carry the standard LOINC panel code directly in OBR-4.
- Results arrive as standard LOINC OBX segments (system "LN") and pass through
  the base extractor unchanged.

Uses the simplest common HL7 standard:
- HL7 v2.3
- Orders:  ORM^O01
- Results: ORU^R01
- Acknowledgment: ACK
- Communication mode: "download" (CARE pushes the order, the external service
  acknowledges it).

The order message carries patient name (PID-5), date of birth (PID-7) and
administrative gender (PID-8), the sample id (placer/filler order numbers and
specimen) and a single standard LOINC panel code per requested test.
"""

from __future__ import annotations

from datetime import datetime

import hl7

from lab_analyzer_device.hl7.devices.base import DeviceHL7Profile
from lab_analyzer_device.hl7.devices.registry import registry
from lab_analyzer_device.hl7.builder import ORMData


class ExternalHL7Profile(DeviceHL7Profile):
    @property
    def device_type(self) -> str:
        return "external_hl7"

    @property
    def display_name(self) -> str:
        return "External HL7 (LOINC Proxy)"

    @property
    def hl7_version(self) -> str:
        return "2.3"

    @property
    def result_message_type(self) -> str:
        return "ORU^R01"

    @property
    def order_message_type(self) -> str:
        return "ORM^O01"

    @property
    def ack_message_type(self) -> str:
        return "ACK"

    @property
    def communication_mode(self):
        return "download"

    # LOINC-native in both directions — no code or panel mappings required.
    # code_mappings / panel_mappings fall back to the empty base defaults,
    # so order codes and result codes pass through unchanged.

    def build_order_message(
        self, order_data: ORMData, device_metadata: dict | None = None
    ) -> hl7.Message:
        """
        Build a standard ORM^O01 order message.

        Segment layout:
            MSH | PID | ORC | OBR(+)

        PID carries name (PID-5), date of birth (PID-7) and administrative
        gender (PID-8). Each requested test produces one OBR with the standard
        LOINC panel code in OBR-4.
        """
        # No panel mappings: validate_tests passes the LOINC codes through.
        resolved_tests = self.validate_tests(
            order_data.tests, device_metadata=device_metadata
        )

        now = datetime.now().strftime("%Y%m%d%H%M%S")
        control_id = f"ORM{now}"

        segments = []

        # MSH
        segments.append(
            f"MSH|^~\\&|{self.sending_application}|{self.sending_facility}"
            f"|LAB_ANALYZER|LAB|{now}||{self.order_message_type}"
            f"|{control_id}|P|{self.hl7_version}"
        )

        # PID — PID-5 name, PID-7 date of birth, PID-8 administrative gender
        name_parts = (
            order_data.patient_name.split(" ", 1)
            if order_data.patient_name
            else ["", ""]
        )
        first_name = name_parts[0] if name_parts else ""
        last_name = name_parts[1] if len(name_parts) > 1 else ""
        dob = order_data.date_of_birth or ""
        gender = order_data.gender or "U"
        segments.append(
            f"PID|1||{order_data.patient_id}^^^^MR"
            f"||{last_name}^{first_name}||{dob}|{gender}"
        )

        # ORC — ORC-12: Ordering Provider
        physician_field = ""
        if order_data.ordering_physician:
            p = order_data.ordering_physician
            physician_field = f"{p.id}^{p.family_name}^{p.given_name}"
        segments.append(
            f"ORC|NW|{order_data.placer_order_number}"
            f"|{order_data.filler_order_number or ''}"
            f"|||||||||{physician_field}"
        )

        # OBR — one per test, standard LOINC code in OBR-4, sample id in OBR-15
        for i, test in enumerate(resolved_tests, start=1):
            specimen_part = order_data.specimen_id or ""
            fields = [""] * 22
            fields[0] = str(i)
            fields[1] = order_data.placer_order_number
            fields[2] = order_data.filler_order_number or ""
            fields[3] = f"{test.code}^{test.display}^{test.system}"
            fields[14] = specimen_part  # OBR-15: Specimen Source
            fields[21] = now  # OBR-22: Results Rpt/Status Chng Date/Time
            segments.append("OBR|" + "|".join(fields))

        raw = "\r".join(segments)
        return hl7.parse(raw)


registry.register(ExternalHL7Profile)
