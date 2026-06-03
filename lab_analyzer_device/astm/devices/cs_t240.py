"""Auto-Chemistry Analyzer CS-T240 ASTM profile.

Auto-Chemistry Analyzer.
Communication: Host Query (bidirectional).
"""

from __future__ import annotations

from datetime import datetime, timezone

from lab_analyzer_device.astm import codec
from lab_analyzer_device.astm.devices.base import DeviceASTMProfile
from lab_analyzer_device.astm.devices.registry import registry
from lab_analyzer_device.hl7.devices.base import LoincMapping
from lab_analyzer_device.hl7.extractor import ORUData


def _parse_query_specimen_ids(raw_query: str | None) -> dict[str, str]:
    """Maps sample_id/sample_no -> full specimen_id field from Q records."""
    if not raw_query:
        return {}

    lines = codec.split_lines(raw_query)
    if not lines:
        return {}

    delimiters = codec.detect_delimiters(lines[0])
    field_delim, _, component_delim, _ = delimiters

    mappings = {}
    for line in lines:
        if codec.record_type(line) != "Q":
            continue
        parts = codec.fields(line, field_delim)
        specimen = codec.field_at(parts, 2)
        if specimen:
            sample_id = codec.component_at(specimen, 0, component_delim)
            sample_no = codec.component_at(specimen, 1, component_delim)
            if sample_id:
                mappings[sample_id] = specimen
            if sample_no:
                mappings[sample_no] = specimen
    return mappings


class CST240Profile(DeviceASTMProfile):
    """CS-T240 ASTM device profile."""

    @property
    def device_type(self) -> str:
        return "cs_t240"

    @property
    def display_name(self) -> str:
        return "Auto-Chemistry Analyzer CS-T240"

    @property
    def communication_mode(self) -> str:
        return "host_query"

    @property
    def code_mappings(self) -> dict[str, LoincMapping]:
        return {
            # Key chemistry analytes
            "ALT": LoincMapping("1742-6", "Alanine aminotransferase [Enzymatic activity/volume] in Serum or Plasma"),
            "AST": LoincMapping("1920-8", "Aspartate aminotransferase [Enzymatic activity/volume] in Serum or Plasma"),
            "ALB": LoincMapping("1751-7", "Albumin [Mass/volume] in Serum or Plasma"),
            "TP": LoincMapping("2885-2", "Protein [Mass/volume] in Serum or Plasma"),
            "GGT": LoincMapping("2324-2", "Gamma glutamyl transferase [Enzymatic activity/volume] in Serum or Plasma"),
            "GLU": LoincMapping("2345-7", "Glucose [Mass/volume] in Serum or Plasma"),
            "BUN": LoincMapping("3094-0", "Urea nitrogen [Mass/volume] in Serum or Plasma"),
            "CRE": LoincMapping("2160-0", "Creatinine [Mass/volume] in Serum or Plasma"),
            "CREA": LoincMapping("2160-0", "Creatinine [Mass/volume] in Serum or Plasma"),
            "UA": LoincMapping("3084-1", "Urate [Mass/volume] in Serum or Plasma"),
            "URIC": LoincMapping("3084-1", "Urate [Mass/volume] in Serum or Plasma"),
            "CHOL": LoincMapping("2093-3", "Cholesterol [Mass/volume] in Serum or Plasma"),
            "TRIG": LoincMapping("2571-8", "Triglyceride [Mass/volume] in Serum or Plasma"),
            "TBIL": LoincMapping("1975-2", "Bilirubin.total [Mass/volume] in Serum or Plasma"),
            "DBIL": LoincMapping("1968-7", "Bilirubin.direct [Mass/volume] in Serum or Plasma"),
            "ALP": LoincMapping("6768-6", "Alkaline phosphatase [Enzymatic activity/volume] in Serum or Plasma"),
            "AMY": LoincMapping("1798-8", "Amylase [Enzymatic activity/volume] in Serum or Plasma"),
            "LIP": LoincMapping("3040-3", "Lipase [Enzymatic activity/volume] in Serum or Plasma"),
            "LDH": LoincMapping("2532-0", "Lactate dehydrogenase [Enzymatic activity/volume] in Serum or Plasma"),
            "CK": LoincMapping("2157-6", "Creatine kinase [Enzymatic activity/volume] in Serum or Plasma"),
            "CKMB": LoincMapping("13969-1", "Creatine kinase.MB [Mass/volume] in Serum or Plasma"),
            "CA": LoincMapping("17861-6", "Calcium [Mass/volume] in Serum or Plasma"),
            "P": LoincMapping("2777-1", "Phosphate [Mass/volume] in Serum or Plasma"),
            "PHOS": LoincMapping("2777-1", "Phosphate [Mass/volume] in Serum or Plasma"),
            "MG": LoincMapping("19123-9", "Magnesium [Mass/volume] in Serum or Plasma"),
            "FE": LoincMapping("2498-4", "Iron [Mass/volume] in Serum or Plasma"),
        }

    @property
    def panel_mappings(self) -> dict[str, str | list[str]]:
        return {
            # LFT — Hepatic function panel
            "26958001": ["ALT", "AST", "ALB", "TP", "GGT", "TBIL", "DBIL", "ALP"],
            "24325-3": ["ALT", "AST", "ALB", "TP", "GGT", "TBIL", "DBIL", "ALP"],
            # KFT / BMP — Basic metabolic panel
            "24321-2": ["GLU", "BUN", "CRE", "CA"],
            # Comprehensive metabolic panel
            "24320-4": ["ALT", "AST", "ALB", "TP", "TBIL", "ALP", "GLU", "BUN", "CRE", "CA"],
            # Lipid panel
            "24331-1": ["CHOL", "TRIG"],
        }

    def _parse_order(self, parts: list[str], comp: str, data: ORUData) -> None:
        specimen = codec.field_at(parts, 2)
        if specimen:
            sample_id = codec.component_at(specimen, 0, comp)
            if not sample_id:
                sample_id = codec.component_at(specimen, 1, comp)

            val = sample_id or specimen
            data.specimen_id = val
            data.placer_order_number = data.placer_order_number or val
            data.sample_id = data.sample_id or val

        filler = codec.field_at(parts, 3)
        if filler:
            data.filler_order_number = filler

    def build_worklist_response(
        self,
        orders: list[ORUData],
        control_id: str | None = None,
        raw_query: str | None = None,
    ) -> str | None:
        if not orders:
            return None

        query_specimens = _parse_query_specimen_ids(raw_query)

        lines: list[str] = [r"H|\^&"]
        patient_seq = 0
        order_seq = 0

        for order in orders:
            patient_seq += 1
            patient_id = order.patient_id or ""
            patient_name = order.patient_name or ""
            gender = order.gender or ""

            age_str = ""
            age_unit = ""
            if order.date_of_birth:
                try:
                    dob_year = int(order.date_of_birth[:4])
                    current_year = datetime.now(timezone.utc).year
                    age = max(1, current_year - dob_year)
                    age_str = str(age)
                    age_unit = "Y"
                except Exception:
                    pass

            lines.append(
                f"P|{patient_seq}||{patient_id}||{patient_name}|||"
                f"{gender}||||||{age_str}^{age_unit}"
            )

            descriptor = "1"
            if order.sample_type:
                st_lower = order.sample_type.lower()
                if "serum" in st_lower:
                    descriptor = "1"
                elif "urine" in st_lower:
                    descriptor = "2"
                elif "plasma" in st_lower:
                    descriptor = "3"
                elif "gastric" in st_lower:
                    descriptor = "4"
                elif "ascites" in st_lower:
                    descriptor = "5"
                elif "csf" in st_lower or "cerebrospinal" in st_lower:
                    descriptor = "6"
                else:
                    descriptor = "7"

            now_str = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
            date_time = now_str
            if order.collect_time:
                try:
                    dt = datetime.fromisoformat(order.collect_time.replace("Z", "+00:00"))
                    date_time = dt.strftime("%Y%m%d%H%M%S")
                except Exception:
                    date_time = order.collect_time[:14]

            sample = order.sample_id or order.specimen_id or ""
            specimen_id = query_specimens.get(sample)
            if not specimen_id:
                if sample.isdigit():
                    specimen_id = f"^{sample}^1^1^N"
                else:
                    specimen_id = f"{sample}^^1^1^N"

            for test in order.tests:
                order_seq += 1
                priority = order.priority or "R"
                lines.append(
                    f"O|{order_seq}|{specimen_id}||^^^{test.code}|{priority}|"
                    f"{date_time}|||||||||{descriptor}||||||||||O"
                )

        lines.append("L|1|N")
        return "\n".join(lines)


registry.register(CST240Profile)
