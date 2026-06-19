"""Sysmex XP-300 Automated Hematology Analyzer ASTM profile.

3-part differential CBC analyzer.
Communication: Unidirectional (results only via ASTM E1394).

Supports two host connection modes (Menu -> Settings -> Host Output):
- **LAN (Ethernet):** analyzer connects inbound to LIS host on TCP port 5006
- **Serial (RS-232C):** point-to-point COM link; default 9600/8/N/1 (manual
  also supports 1200-19200 bps, 7-bit, Even/Odd parity, 2 stop bits, RTS/CTS)

Key characteristics (confirmed from instrument capture):
- ASTM E1381 framing + E1394 records (set device Format to ASTM)
- P record is minimal (``P|1``); demographics are not sent separately
- The analyzer has a single on-screen **Sample ID** field; it maps to O field 3
  component 2 as ``^^     <sample_id>^<gender>`` (O field 2 is always empty)
- Operators must enter the numeric CARE accession/sample ID in that field
- R record test ID format: ``^^^^CODE^1`` (code at component index 4)
- Sample ID ``0`` is used for internal QC/validation runs
"""

from __future__ import annotations

from lab_analyzer_device.astm import codec
from lab_analyzer_device.astm.devices.base import DeviceASTMProfile
from lab_analyzer_device.astm.devices.registry import registry
from lab_analyzer_device.hl7.devices.base import LoincMapping
from lab_analyzer_device.hl7.extractor import ObservationData, ORUData


def _extract_sysmex_test_code(test_id: str, component_delim: str) -> str:
    """Extract the analyte code from XP-300 universal test ID ``^^^^CODE^1``."""
    comps = codec.components(test_id, component_delim)
    for idx in (4, 3, 0, 1, 2):
        if idx < len(comps) and comps[idx].strip():
            return comps[idx].strip()
    return ""


def _is_numeric_value(value: str) -> bool:
    if not value:
        return False
    try:
        float(value)
        return True
    except ValueError:
        return False


def _apply_sample_id(data: ORUData, sample_id: str) -> None:
    normalized = sample_id.strip()
    if not normalized:
        return
    data.specimen_id = normalized
    data.sample_id = data.sample_id or normalized
    data.placer_order_number = data.placer_order_number or normalized


class SysmexXP300Profile(DeviceASTMProfile):
    """Sysmex XP-300 ASTM device profile."""

    @property
    def device_type(self) -> str:
        return "sysmex_xp_300"

    @property
    def display_name(self) -> str:
        return "Sysmex XP-300"

    @property
    def communication_mode(self) -> str:
        return "unidirectional"

    @property
    def astm_connection_mode(self) -> str:
        return "inbound"

    @property
    def default_oru_port(self) -> int:
        return 5006

    @property
    def code_mappings(self) -> dict[str, LoincMapping]:
        return {
            "WBC": LoincMapping("6690-2", "Leukocytes [#/volume] in Blood by Automated count"),
            "LYM#": LoincMapping("731-0", "Lymphocytes [#/volume] in Blood by Automated count"),
            "MXD#": LoincMapping("26484-6", "Monocytes [#/volume] in Blood"),
            "NEUT#": LoincMapping("751-8", "Neutrophils [#/volume] in Blood by Automated count"),
            "LYM%": LoincMapping("736-9", "Lymphocytes/Leukocytes in Blood by Automated count"),
            "MXD%": LoincMapping("26485-3", "Monocytes/Leukocytes in Blood"),
            "NEUT%": LoincMapping("770-8", "Neutrophils/Leukocytes in Blood by Automated count"),
            "RBC": LoincMapping("789-8", "Erythrocytes [#/volume] in Blood by Automated count"),
            "HGB": LoincMapping("718-7", "Hemoglobin [Mass/volume] in Blood"),
            "HCT": LoincMapping("4544-3", "Hematocrit [Volume Fraction] of Blood by Automated count"),
            "MCV": LoincMapping("787-2", "MCV [Entitic mean volume] by Automated count"),
            "MCH": LoincMapping("785-6", "MCH [Entitic mass] by Automated count"),
            "MCHC": LoincMapping("786-4", "MCHC [Entitic Mass/volume] by Automated count"),
            "RDW-SD": LoincMapping("21000-5", "Erythrocyte distribution width [Entitic volume] by Automated count"),
            "RDW-CV": LoincMapping("788-0", "Erythrocyte distribution width [Ratio] by Automated count"),
            "PLT": LoincMapping("777-3", "Platelets [#/volume] in Blood by Automated count"),
            "MPV": LoincMapping("32623-1", "Platelet [Entitic mean volume] in Blood by Automated count"),
            "PDW": LoincMapping("32207-3", "Platelet distribution width [Entitic volume] in Blood by Automated count"),
            "PCT": LoincMapping("51637-7", "Plateletcrit [Volume Fraction] in Blood"),
            "P-LCR": LoincMapping("48386-7", "Platelets Large/Platelets in Blood by Automated count"),
            "PLCR": LoincMapping("48386-7", "Platelets Large/Platelets in Blood by Automated count"),
        }

    def should_skip_result(self, data: ORUData) -> bool:
        sample = (data.sample_id or data.specimen_id or "").strip()
        return sample == "0"

    def _parse_order(self, parts: list[str], comp: str, data: ORUData) -> None:
        # O|seq|specimen_id|instrument_specimen_id|universal_test_id|...
        # XP-300: O-2 (specimen_id) is empty; the single on-screen Sample ID
        # field is transmitted in O-3 component 2, e.g. ``^^     12345^``.
        specimen = codec.field_at(parts, 2)
        if specimen:
            _apply_sample_id(data, specimen)

        instrument_field = codec.field_at(parts, 3)
        if not instrument_field:
            return

        if not data.sample_id:
            sample_id = codec.component_at(instrument_field, 2, comp)
            if sample_id:
                _apply_sample_id(data, sample_id)

        gender = codec.component_at(instrument_field, 3, comp)
        if gender and len(gender.strip()) == 1:
            data.gender = gender.strip().upper()[:1]

    def _parse_result(
        self,
        parts: list[str],
        comp: str,
        set_id: int,
        mappings: dict[str, LoincMapping],
    ) -> ObservationData | None:
        test_id = codec.field_at(parts, 2)
        if not test_id:
            return None

        code = _extract_sysmex_test_code(test_id, comp)
        if not code:
            return None

        value = codec.field_at(parts, 3)
        if not _is_numeric_value(value):
            return None

        comps = codec.components(test_id, comp)
        display = comps[5].strip() if len(comps) > 5 else ""

        system, resolved_code, mapped_display = self.resolve_code(code, mappings)
        return ObservationData(
            set_id=set_id,
            value_type="NM",
            code=resolved_code,
            display=display or mapped_display,
            system=system,
            value=value,
            units=codec.field_at(parts, 4),
            reference_range=codec.field_at(parts, 5),
            abnormal_flags=codec.field_at(parts, 6),
            result_status=codec.field_at(parts, 8) or "F",
            observation_datetime=codec.field_at(parts, 12) or None,
        )


registry.register(SysmexXP300Profile)
