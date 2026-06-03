"""Base class for device-specific ASTM (E1381/E1394) handling.

Mirrors :class:`lab_analyzer_device.hl7.devices.base.DeviceHL7Profile` so the
two protocols share the same registry pattern and the same domain payload
(:class:`~lab_analyzer_device.hl7.extractor.ORUData`). The default
implementation parses standard E1394 ``H/P/O/R/L`` records, so most analyzers
only need to override code mappings.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Literal

from lab_analyzer_device.astm import codec
from lab_analyzer_device.hl7.devices.base import LoincMapping
from lab_analyzer_device.hl7.extractor import (
    ObservationData,
    ORUData,
)

CommunicationMode = Literal["unidirectional", "host_query", "download"]


class DeviceASTMProfile(ABC):
    """Base class for device-specific ASTM handling."""

    @property
    @abstractmethod
    def device_type(self) -> str:
        """Unique device type identifier (auto-discovered by the profile registry)."""

    @property
    def display_name(self) -> str:
        return self.device_type.replace("_", " ").title()

    @property
    def astm_version(self) -> str:
        return "E1394-97"

    @property
    def communication_mode(self) -> CommunicationMode:
        """ASTM communication mode for this device.

        - ``unidirectional``: results only, no order interface.
        - ``host_query``: instrument queries host for orders (``Q`` records).
        - ``download``: host pushes orders to the instrument.
        """
        return "unidirectional"

    @property
    def supports_query_orders(self) -> bool:
        return self.communication_mode == "host_query"

    @property
    def code_mappings(self) -> dict[str, LoincMapping]:
        """Device-specific code → LOINC mappings. Override per device."""
        return {}

    @property
    def panel_mappings(self) -> dict[str, str | list[str]]:
        """Map of LOINC code → device-native panel code(s) for ordering."""
        return {}

    def get_effective_code_mappings(
        self, device_metadata: dict | None = None
    ) -> dict[str, LoincMapping]:
        mappings = dict(self.code_mappings)
        if device_metadata and "code_mappings" in device_metadata:
            for key, value in (device_metadata["code_mappings"] or {}).items():
                if isinstance(value, dict):
                    mappings[key] = LoincMapping(
                        loinc_code=value.get("loinc_code", ""),
                        display=value.get("display", ""),
                        system=value.get("system", "http://loinc.org"),
                    )
        return mappings

    def resolve_code(self, code: str, mappings: dict[str, LoincMapping]) -> tuple[str, str, str]:
        """Resolve a device code to ``(system, loinc_code, display)``."""
        if code in mappings:
            mapping = mappings[code]
            return mapping.system, mapping.loinc_code, mapping.display
        return "local", code, ""

    # -- result extraction --------------------------------------------

    def extract_result_data(
        self, records: list[str], device_metadata: dict | None = None
    ) -> ORUData:
        """Parse standard E1394 records into :class:`ORUData`.

        Override for analyzers that deviate from the standard record layout.
        """
        mappings = self.get_effective_code_mappings(device_metadata)
        delimiters = codec.detect_delimiters(records[0]) if records else (
            codec.DEFAULT_FIELD,
            codec.DEFAULT_REPEAT,
            codec.DEFAULT_COMPONENT,
            codec.DEFAULT_ESCAPE,
        )
        field_delim, _, component_delim, _ = delimiters

        data = ORUData()
        observations: list[ObservationData] = []
        set_id = 0

        for line in records:
            rtype = codec.record_type(line)
            parts = codec.fields(line, field_delim)

            if rtype == "P":
                self._parse_patient(parts, component_delim, data)
            elif rtype == "O":
                self._parse_order(parts, component_delim, data)
            elif rtype == "R":
                set_id += 1
                obs = self._parse_result(parts, component_delim, set_id, mappings)
                if obs is not None:
                    observations.append(obs)

        data.observations = observations
        return data

    def _parse_patient(self, parts: list[str], comp: str, data: ORUData) -> None:
        # P|seq|practice_pid|lab_pid|pid3|name|...|dob|sex
        lab_pid = codec.field_at(parts, 3) or codec.field_at(parts, 2)
        if lab_pid:
            data.patient_id = lab_pid
        name = codec.field_at(parts, 5)
        if name:
            family = codec.component_at(name, 0, comp)
            given = codec.component_at(name, 1, comp)
            data.patient_name = " ".join(p for p in (given, family) if p) or name
        dob = codec.field_at(parts, 7)
        if dob:
            data.date_of_birth = dob[:8]
        sex = codec.field_at(parts, 8)
        if sex:
            data.gender = sex.upper()[:1]

    def _parse_order(self, parts: list[str], comp: str, data: ORUData) -> None:
        # O|seq|specimen_id|instrument_specimen_id|universal_test_id|...
        specimen = codec.field_at(parts, 2)
        if specimen:
            data.specimen_id = specimen
            data.placer_order_number = data.placer_order_number or specimen
            data.sample_id = data.sample_id or specimen
        filler = codec.field_at(parts, 3)
        if filler:
            data.filler_order_number = filler

    def _parse_result(
        self,
        parts: list[str],
        comp: str,
        set_id: int,
        mappings: dict[str, LoincMapping],
    ) -> ObservationData | None:
        # R|seq|universal_test_id|value|units|ref_range|abnormal|...|status|...|datetime
        test_id = codec.field_at(parts, 2)
        if not test_id:
            return None
        comps = codec.components(test_id, comp)
        # Universal test ID is typically ^^^CODE^NAME; fall back to first non-empty.
        code = ""
        for idx in (3, 0, 1, 2):
            if idx < len(comps) and comps[idx].strip():
                code = comps[idx].strip()
                break
        display = comps[4].strip() if len(comps) > 4 else ""

        system, resolved_code, mapped_display = self.resolve_code(code, mappings)
        return ObservationData(
            set_id=set_id,
            value_type="NM",
            code=resolved_code,
            display=display or mapped_display,
            system=system,
            value=codec.field_at(parts, 3),
            units=codec.field_at(parts, 4),
            reference_range=codec.field_at(parts, 5),
            abnormal_flags=codec.field_at(parts, 6),
            result_status=codec.field_at(parts, 8) or "F",
            observation_datetime=codec.field_at(parts, 12) or None,
        )

    # -- order building (host-query worklist) -------------------------

    def build_worklist_response(
        self,
        orders: list[ORUData],
        control_id: str | None = None,
        raw_query: str | None = None,
    ) -> str | None:
        """Build an ASTM order-download message (``H/P/O/L``) for the analyzer.

        Returns newline-joined record lines, or ``None`` when there is nothing
        to send. Override for analyzers with non-standard order layouts.
        """
        if not orders:
            return None
        lines: list[str] = [r"H|\^&|||CARE|||||||P|" + self.astm_version]
        patient_seq = 0
        order_seq = 0
        for order in orders:
            patient_seq += 1
            name = order.patient_name or ""
            lines.append(
                f"P|{patient_seq}||{order.patient_id or ''}||{name}||"
                f"{order.date_of_birth or ''}|{order.gender or ''}"
            )
            for test in order.tests:
                order_seq += 1
                sample = order.sample_id or order.specimen_id or ""
                lines.append(
                    f"O|{order_seq}|{sample}||^^^{test.code}|{order.priority or 'R'}||"
                    f"{order.collect_time or ''}"
                )
        lines.append("L|1|N")
        return "\n".join(lines)
