from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

import hl7

from lab_analyzer_device.hl7.extractor import ObservationData, OrderingPhysicianData, ORUData, hl7_to_str
from lab_analyzer_device.hl7.builder import ORMData, OrderedTest, OrderingPhysician


CommunicationMode = Literal["unidirectional", "host_query", "download"]
Hl7ConnectionMode = Literal["inbound", "outbound"]


@dataclass(frozen=True)
class LoincMapping:
    loinc_code: str
    display: str
    system: str = "http://loinc.org"


class DeviceHL7Profile(ABC):
    """
    Base class for device-specific HL7 handling.

    Subclass this for each analyzer model to customize:
    - HL7 version and message types
    - Code mappings
    - Field extraction from OBX segments
    - ORM message building
    """

    @property
    @abstractmethod
    def device_type(self) -> str:
        """Unique device type identifier (auto-discovered by the profile registry)."""

    @property
    def display_name(self) -> str:
        """Human-readable name for the device type."""
        return self.device_type.replace("_", " ").title()

    @property
    def hl7_version(self) -> str:
        return "2.3"

    @property
    def result_message_type(self) -> str:
        """HL7 message type for results (e.g. 'ORU^R01', 'OUL^R22')."""
        return "ORU^R01"

    @property
    def order_message_type(self) -> str:
        """HL7 message type for orders (e.g. 'ORM^O01', 'OML^O33')."""
        return "ORM^O01"

    @property
    def ack_message_type(self) -> str:
        """HL7 message type for acknowledgments."""
        return "ACK"

    @property
    def communication_mode(self) -> CommunicationMode:
        """
        HL7 communication mode for this device.

        - "unidirectional": Device only sends results (ORU). No order interface.
        - "host_query": Device queries host for orders (sends ORM, receives ORR).
        - "download": Host pushes orders to device (sends ORM, device ACKs).
        """
        return "download"

    @property
    def hl7_connection_mode(self) -> Hl7ConnectionMode:
        """
        TCP transport role for HL7/MLLP over Ethernet.

        - "inbound": the analyzer connects to the gateway's MLLP listeners.
        - "outbound": the gateway dials out to the analyzer's fixed port and
          maintains a persistent connection.
        """
        return "inbound"

    @property
    def default_oru_port(self) -> int:
        """Default MLLP port when the device metadata does not specify one."""
        return 2575

    @property
    def supports_query_orders(self) -> bool:
        """Whether this device queries for orders (True) or receives pushed orders (False)."""
        return self.communication_mode == "host_query"

    @property
    def order_response_message_type(self) -> str:
        """HL7 message type for order responses (query-based devices)."""
        return "ORR^O02"

    @property
    def sending_application(self) -> str:
        return "CARE"

    @property
    def sending_facility(self) -> str:
        return "CARE_FACILITY"

    @property
    def code_mappings(self) -> dict[str, LoincMapping]:
        """Device-specific code → LOINC mappings. Override per device."""
        return {}

    @property
    def panel_mappings(self) -> dict[str, str | list[str]]:
        """
        Map of LOINC code → device-native panel code(s) for ordering.

        Value can be:
        - str: a single device panel code (e.g. "CBC")
        - list[str]: individual test IDs to send (e.g. ["7", "6", "3", "5"])

        Override per device. If empty, codes are passed through as-is.
        """
        return {}

    def get_effective_panel_mappings(self, device_metadata: dict | None = None) -> dict[str, str | list[str]]:
        """
        Get panel mappings with optional device metadata overrides.

        If device_metadata contains a non-null "panel_mappings" key, it completely
        overrides the profile defaults.
        """
        if device_metadata and device_metadata.get("panel_mappings"):
            return device_metadata["panel_mappings"]
        return self.panel_mappings

    def get_effective_code_mappings(self, device_metadata: dict | None = None) -> dict[str, LoincMapping]:
        """
        Get code mappings with optional device metadata overrides.

        If device_metadata contains a "code_mappings" key, entries override
        profile defaults (merged, not replaced).
        """
        mappings = dict(self.code_mappings)
        if device_metadata and "code_mappings" in device_metadata:
            for key, value in device_metadata["code_mappings"].items():
                if isinstance(value, dict):
                    mappings[key] = LoincMapping(
                        loinc_code=value.get("loinc_code", ""),
                        display=value.get("display", ""),
                        system=value.get("system", "http://loinc.org"),
                    )
        return mappings

    def validate_tests(
        self, tests: list[OrderedTest], device_metadata: dict | None = None
    ) -> list[OrderedTest]:
        """
        Validate and resolve test codes to device-native panel codes.

        Raises ValueError if any test code is not supported by the device.
        Returns a list of OrderedTests with codes resolved to device-native values.

        For panel mappings with list values (test ID expansion), each test ID
        becomes a separate OrderedTest in the output.
        """
        effective_mappings = self.get_effective_panel_mappings(device_metadata)
        if not effective_mappings:
            return tests

        resolved = []
        for test in tests:
            panel_code = effective_mappings.get(test.code)
            if panel_code is None:
                valid = ", ".join(
                    f"{code}" for code in effective_mappings.keys()
                )
                raise ValueError(
                    f"Test code '{test.code}' is not supported by {self.display_name}. "
                    f"Valid codes: {valid}"
                )
            if isinstance(panel_code, list):
                for test_id in panel_code:
                    resolved.append(OrderedTest(
                        code=test_id,
                        display=test.display,
                        system=test.system,
                    ))
            else:
                resolved.append(OrderedTest(
                    code=panel_code,
                    display=test.display,
                    system=test.system,
                ))
        return resolved

    def resolve_code(self, code: str, system: str) -> tuple[str, str, str]:
        """
        Resolve a code from an OBX-3 field to (system, code, display).

        If the code is already LOINC (system="LN"), passes through.
        If a mapping exists in code_mappings, returns the LOINC mapping.
        Otherwise returns the original code with system="local".
        """
        if system == "LN":
            return "http://loinc.org", code, ""

        if mapping := self.code_mappings.get(code):
            return mapping.system, mapping.loinc_code, mapping.display

        return "local", code, ""

    def should_skip_obx(self, segment) -> bool:
        """
        Return True if this OBX segment should be skipped during extraction.

        Override to filter out non-result OBX segments (reagent traceability,
        curves, histograms, etc.)
        """
        value_type = hl7_to_str(segment, 2)
        # Skip encapsulated data (ED) by default — curves, reagent traceability
        return value_type == "ED"

    def extract_result_data(self, message: hl7.Message) -> ORUData:
        """
        Extract domain data from a result HL7 message.

        The base implementation handles standard HL7 v2.x segment layout
        (PID, OBR, ORC, SPM, OBX). Override for non-standard layouts.
        """
        patient_id = None
        patient_name = None
        date_of_birth = None
        placer_order_number = None
        filler_order_number = None
        specimen_id = None
        ordering_physician: OrderingPhysicianData | None = None
        observations: list[ObservationData] = []

        for segment in message:
            seg_id = str(segment(0))

            if seg_id == "PID":
                patient_id = self.extract_patient_id(segment)
                patient_name = self.extract_patient_name(segment)
                date_of_birth = self.extract_date_of_birth(segment)

            elif seg_id == "ORC":
                if not ordering_physician:
                    ordering_physician = self.extract_ordering_physician(segment)

            elif seg_id == "OBR":
                placer, filler = self.extract_order_numbers(segment)
                placer_order_number = placer_order_number or placer
                filler_order_number = filler_order_number or filler
                if not specimen_id:
                    specimen_id = self.extract_specimen_from_obr(segment)
                # OBR-16 also carries ordering provider as fallback
                if not ordering_physician:
                    ordering_physician = self.extract_ordering_physician_from_obr(segment)

            elif seg_id == "SPM":
                specimen_id = self.extract_specimen_from_spm(segment) or specimen_id

            elif seg_id == "OBX":
                if self.should_skip_obx(segment):
                    continue
                obs = self.extract_observation(segment)
                if obs:
                    observations.append(obs)

        return ORUData(
            patient_id=patient_id,
            patient_name=patient_name,
            date_of_birth=date_of_birth,
            placer_order_number=placer_order_number,
            filler_order_number=filler_order_number,
            specimen_id=specimen_id,
            ordering_physician=ordering_physician,
            observations=observations,
        )

    def extract_patient_id(self, pid_segment) -> str | None:
        """Extract patient ID from PID segment. Override for custom formats."""
        # PID-3: Patient Identifier List — first component
        return hl7_to_str(pid_segment, 3, 1) or hl7_to_str(pid_segment, 3) or None

    def extract_patient_name(self, pid_segment) -> str | None:
        """
        Extract patient name from PID-5.

        PID-5 format: family_name^given_name^middle^suffix^prefix
        Returns "given_name family_name" or None.
        """
        family_name = hl7_to_str(pid_segment, 5, 1)
        given_name = hl7_to_str(pid_segment, 5, 2)
        if not family_name and not given_name:
            return None
        parts = [p for p in [given_name, family_name] if p]
        return " ".join(parts) or None

    def extract_date_of_birth(self, pid_segment) -> str | None:
        """
        Extract date of birth from PID-7.

        Returns raw HL7 datetime string (YYYYMMDD or YYYYMMDDHHMMSS).
        """
        return hl7_to_str(pid_segment, 7) or None

    def extract_order_numbers(self, obr_segment) -> tuple[str | None, str | None]:
        """Extract (placer_order_number, filler_order_number) from OBR."""
        placer = hl7_to_str(obr_segment, 2) or None
        filler = hl7_to_str(obr_segment, 3) or None
        return placer, filler

    def extract_ordering_physician(self, orc_segment) -> OrderingPhysicianData | None:
        """
        Extract ordering physician from ORC-12 (Ordering Provider).

        ORC-12 format: ID^family_name^given_name^...
        """
        physician_id = hl7_to_str(orc_segment, 12, 1)
        family_name = hl7_to_str(orc_segment, 12, 2)
        given_name = hl7_to_str(orc_segment, 12, 3)
        if not physician_id and not family_name:
            return None
        return OrderingPhysicianData(
            id=physician_id,
            family_name=family_name,
            given_name=given_name,
        )

    def extract_ordering_physician_from_obr(self, obr_segment) -> OrderingPhysicianData | None:
        """
        Extract ordering physician from OBR-16 (Ordering Provider) as fallback.

        OBR-16 format: ID^family_name^given_name^...
        """
        physician_id = hl7_to_str(obr_segment, 16, 1)
        family_name = hl7_to_str(obr_segment, 16, 2)
        given_name = hl7_to_str(obr_segment, 16, 3)
        if not physician_id and not family_name:
            return None
        return OrderingPhysicianData(
            id=physician_id,
            family_name=family_name,
            given_name=given_name,
        )

    def extract_specimen_from_obr(self, obr_segment) -> str | None:
        """Extract specimen info from OBR-15 (older HL7 versions)."""
        return hl7_to_str(obr_segment, 15, 1) or None

    def extract_specimen_from_spm(self, spm_segment) -> str | None:
        """Extract specimen ID from SPM-2."""
        return hl7_to_str(spm_segment, 2, 1) or hl7_to_str(spm_segment, 2) or None

    def extract_units(self, obx_segment) -> str:
        """
        Extract units from OBX-6.

        Uses the full field value rather than component 1, because some
        analyzers send UCUM units containing '^' (e.g. "10^3/uL") without
        proper HL7 escaping. Device profiles with properly-encoded CE fields
        can override to use component 1.
        """
        return hl7_to_str(obx_segment, 6)

    def extract_observation(self, obx_segment) -> ObservationData | None:
        """Extract a single observation from an OBX segment."""
        set_id_str = hl7_to_str(obx_segment, 1)
        set_id = int(set_id_str) if set_id_str.isdigit() else 0

        value_type = hl7_to_str(obx_segment, 2)

        # OBX-3: Observation Identifier (code^display^system)
        raw_code = hl7_to_str(obx_segment, 3, 1)
        raw_display = hl7_to_str(obx_segment, 3, 2)
        raw_system = hl7_to_str(obx_segment, 3, 3)

        if not raw_code:
            return None

        system, code, mapped_display = self.resolve_code(raw_code, raw_system)
        display = raw_display or mapped_display

        value = hl7_to_str(obx_segment, 5)
        units = self.extract_units(obx_segment)
        reference_range = hl7_to_str(obx_segment, 7)
        abnormal_flags = hl7_to_str(obx_segment, 8)
        result_status = hl7_to_str(obx_segment, 11)
        observation_datetime = hl7_to_str(obx_segment, 14) or None

        return ObservationData(
            set_id=set_id,
            value_type=value_type,
            code=code,
            display=display,
            system=system,
            value=value,
            units=units,
            reference_range=reference_range,
            abnormal_flags=abnormal_flags,
            result_status=result_status,
            observation_datetime=observation_datetime,
        )

    def build_order_message(self, order_data: ORMData, device_metadata: dict | None = None) -> hl7.Message:
        """
        Build an order HL7 message. Override for device-specific order formats.

        The base implementation builds a standard ORM^O01.
        """
        # Validate and resolve test codes to device-native panel codes
        resolved_tests = self.validate_tests(order_data.tests, device_metadata=device_metadata)

        now = datetime.now().strftime("%Y%m%d%H%M%S")
        control_id = f"ORM{now}"

        segments = []

        segments.append(
            f"MSH|^~\\&|{self.sending_application}|{self.sending_facility}"
            f"|LAB_ANALYZER|LAB|{now}||{self.order_message_type}"
            f"|{control_id}|P|{self.hl7_version}"
        )

        name_parts = order_data.patient_name.split(" ", 1) if order_data.patient_name else ["", ""]
        last_name = name_parts[1] if len(name_parts) > 1 else ""
        first_name = name_parts[0] if name_parts else ""
        dob = order_data.date_of_birth or ""
        segments.append(
            f"PID|1||{order_data.patient_id}|||{last_name}^{first_name}||{dob}"
        )

        # ORC-12: Ordering Provider
        physician_field = ""
        if order_data.ordering_physician:
            p = order_data.ordering_physician
            physician_field = f"{p.id}^{p.family_name}^{p.given_name}"

        segments.append(
            f"ORC|NW|{order_data.placer_order_number}|{order_data.filler_order_number or ''}"
            f"|||||||||{physician_field}"
        )

        for i, test in enumerate(resolved_tests, start=1):
            specimen_part = order_data.specimen_id or ""
            segments.append(
                f"OBR|{i}|{order_data.placer_order_number}"
                f"|{order_data.filler_order_number or ''}|"
                f"{test.code}^{test.display}^{test.system}"
                f"|||||||||||||||||{now}|||||||{specimen_part}"
            )

        raw = "\r".join(segments)
        return hl7.parse(raw)

    def build_worklist_response(
        self,
        orders: list[ORUData],
        original_control_id: str,
        *,
        raw_query: str | None = None,
    ) -> str | list[str] | None:
        """
        Build an ORR^O02 worklist response for a query-based analyzer.

        Override in device profiles that need a custom response format.
        Returns a raw HL7 message string, a list of message strings,
        or None if the device does not support worklist responses.

        The base implementation builds a generic ORR^O02 suitable for
        most hematology analyzers that use the host_query communication mode.
        """
        if self.communication_mode != "host_query":
            return None

        now = datetime.now().strftime("%Y%m%d%H%M%S")

        segments = []

        # MSH
        segments.append(
            f"MSH|^~\\&|{self.sending_application}||||{now}"
            f"||ORR^O02|{original_control_id}|P|{self.hl7_version}"
        )

        # MSA — acknowledge the query
        segments.append(f"MSA|AA|{original_control_id}")

        for order in orders:
            patient_id = order.patient_id or ""
            patient_name = order.patient_name or ""
            dob = order.date_of_birth or ""
            gender = order.gender or ""
            sample_id = order.sample_id or ""
            department = order.department or ""
            bed_number = order.bed or ""
            patient_class = order.patient_class or ""
            collect_time = order.collect_time or ""

            # Format name as family^given for HL7
            name_parts = patient_name.split(" ", 1) if patient_name else [""]
            hl7_name = (
                f"{name_parts[1]}^{name_parts[0]}"
                if len(name_parts) == 2
                else name_parts[0]
            )

            # PID
            segments.append(
                f"PID|1||{patient_id}^^^^MR||{hl7_name}||{dob}|{gender}"
            )

            # PV1
            location = (
                f"{department}^^{bed_number}"
                if department or bed_number
                else ""
            )
            segments.append(f"PV1|1|{patient_class}|{location}")

            # ORC
            segments.append(f"ORC|NW|{sample_id}")

            # OBR
            segments.append(
                f"OBR|1||{sample_id}|00001^Automated Count^99MRC"
                f"||{collect_time}|||||||||||||||||||HM"
            )

        raw = "\r".join(segments)
        message = hl7.parse(raw)
        return str(message)
