"""
Athenese-Dx ADX AutoChem 200 Biochemistry Analyzer HL7 profile.

Semi-automated biochemistry analyzer.
Communication: Host Query (analyzer sends QRY^Q02 to request worklist,
receives QCK^Q02 + DSR^Q03 response, then sends ORU^R01 results).

Key characteristics:
- HL7 v2.3.1
- Results: ORU^R01 with integer test ID codes in OBX-3 (e.g. "1", "5", "7")
- Query: QRY^Q02 with barcode in QRD-8
- Response: Two messages:
  1. QCK^Q02 — acknowledgement with MSA|AA and ERR (success)
  2. DSR^Q03 — display response with positional DSP segments:
     - DSP|1| = priority (R)
     - DSP|2| = patient ID
     - DSP|3| = patient name
     - DSP|4| = date of birth (YYYYMMDDHHmmss)
     - DSP|5| = gender (M/F/O/U)
     - DSP|6-20| = demographics (mostly empty for basic usage)
     - DSP|21| = barcode
     - DSP|22| = sample ID
     - DSP|26| = sample type
     - DSP|29+| = test orders as "TestID^^^"
- OBX-3: Integer test ID (e.g. "7" for Total Bilirubin)
- OBX-4: Test name display (e.g. "BIL T")
- OBX-2 = NM: numeric results (keep)
- OBX-2 = ST: string values (keep — sometimes used for flags)
- MSH-3: ADX-CHEM-200
"""

from __future__ import annotations

from datetime import datetime, timezone

import hl7

from lab_analyzer_device.hl7.devices.base import CommunicationMode, DeviceHL7Profile, LoincMapping
from lab_analyzer_device.hl7.devices.registry import registry
from lab_analyzer_device.hl7.extractor import ORUData, hl7_to_str


class AdxAutoChem200Profile(DeviceHL7Profile):

    @property
    def device_type(self) -> str:
        return "adx_autochem_200"

    @property
    def display_name(self) -> str:
        return "Athenese-Dx ADX AutoChem 200 Biochemistry Analyzer"

    @property
    def hl7_version(self) -> str:
        return "2.3.1"

    @property
    def communication_mode(self) -> CommunicationMode:
        return "host_query"

    @property
    def sending_application(self) -> str:
        return "LIS"

    @property
    def code_mappings(self) -> dict[str, LoincMapping]:
        """
        ADX AutoChem 200 OBX-3 codes — integer test IDs mapped to LOINC.
        The test ID is the first component of OBX-3 (e.g. OBX|1|NM|1^ALBUMIN||4.2|g/dL).
        IDs correspond to the machine's configured test numbers.
        """
        return {
            # 1-28: Default test configuration from machine
            "1": LoincMapping("1751-7", "Albumin [Mass/volume] in Serum or Plasma"),  # ALBUMIN (g/dL)
            "2": LoincMapping("6768-6", "Alkaline phosphatase [Enzymatic activity/volume] in Serum or Plasma"),  # ALPSR (U/L)
            "3": LoincMapping("1742-6", "Alanine aminotransferase [Enzymatic activity/volume] in Serum or Plasma"),  # SGPT (U/L)
            "4": LoincMapping("1798-8", "Amylase [Enzymatic activity/volume] in Serum or Plasma"),  # AMYLASE (U/L)
            "5": LoincMapping("1920-8", "Aspartate aminotransferase [Enzymatic activity/volume] in Serum or Plasma"),  # SGOT (U/L)
            "6": LoincMapping("1968-7", "Bilirubin.direct [Mass/volume] in Serum or Plasma"),  # BIL D (mg/dL)
            "7": LoincMapping("1975-2", "Bilirubin.total [Mass/volume] in Serum or Plasma"),  # BIL T (mg/dL)
            "8": LoincMapping("2075-0", "Chloride [Moles/volume] in Serum or Plasma"),  # CLORIDE (mmol/L)
            "9": LoincMapping("2093-3", "Cholesterol [Mass/volume] in Serum or Plasma"),  # CHOL (mg/dL)
            "10": LoincMapping("2345-7", "Glucose [Mass/volume] in Serum or Plasma"),  # GLU (mg/dL)
            "11": LoincMapping("2571-8", "Triglyceride [Mass/volume] in Serum or Plasma"),  # TGL (mg/dL)
            "12": LoincMapping("2885-2", "Protein [Mass/volume] in Serum or Plasma"),  # TP (g/dL)
            "13": LoincMapping("3084-1", "Urate [Mass/volume] in Serum or Plasma"),  # URIC A (mg/dL)
            "14": LoincMapping("3094-0", "Urea nitrogen [Mass/volume] in Serum or Plasma"),  # UREA (mg/dL)
            "15": LoincMapping("2823-3", "Potassium [Moles/volume] in Serum or Plasma"),  # POTTA (mmol/L)
            "16": LoincMapping("2951-2", "Sodium [Moles/volume] in Serum or Plasma"),  # NA (mmol/L)
            "17": LoincMapping("17861-6", "Calcium [Mass/volume] in Serum or Plasma"),  # CA (mg/dL)
            "18": LoincMapping("1988-5", "C reactive protein [Mass/volume] in Serum or Plasma"),  # CRP (mg/L)
            "19": LoincMapping("11572-5", "Rheumatoid factor [Units/volume] in Serum or Plasma"),  # RF (IU/mL)
            "20": LoincMapping("5370-2", "Streptolysin O Ab [Units/volume] in Serum or Plasma"),  # ASO (IU/mL)
            "21": LoincMapping("3084-1", "Urate [Mass/volume] in Serum or Plasma"),  # U ACID (mg/dL)
            "22": LoincMapping("2160-0", "Creatinine [Mass/volume] in Serum or Plasma"),  # CREAT2R (mg/dL)
            "23": LoincMapping("3040-3", "Lipase [Enzymatic activity/volume] in Serum or Plasma"),  # LIPASE (U/L)
            "24": LoincMapping("2160-0", "Creatinine [Mass/volume] in Serum or Plasma"),  # CREATSR (mg/dL)
            "25": LoincMapping("2324-2", "Gamma glutamyl transferase [Enzymatic activity/volume] in Serum or Plasma"),  # GGT (U/L)
            "26": LoincMapping("2085-9", "Cholesterol in HDL [Mass/volume] in Serum or Plasma"),  # DHDL (mg/dL)
            "27": LoincMapping("4548-4", "Hemoglobin A1c/Hemoglobin.total in Blood"),  # HbA1C (%)
            "28": LoincMapping("2777-1", "Phosphate [Mass/volume] in Serum or Plasma"),  # PHOSPHO (mg/dL)
        }

    @property
    def panel_mappings(self) -> dict[str, str | list[str]]:
        """
        LOINC panel codes → ADX AutoChem 200 individual test IDs.

        Each panel expands to a list of integer test IDs that the analyzer
        understands. These are sent as individual DSP "TestID^^^" segments
        in the worklist response.

        Test ID reference:
          1=Albumin, 2=ALP, 3=ALT/SGPT, 4=Amylase, 5=AST/SGOT,
          6=Bilirubin Direct, 7=Bilirubin Total, 8=BUN/Urea,
          9=Cholesterol Total, 10=Creatinine, 11=HDL Cholesterol,
          12=GGT, 13=Glucose, 14=Potassium, 15=Sodium, 16=Chloride,
          17=Calcium, 18=Iron, 19=TIBC, 20=Magnesium, 21=Phosphorus,
          22=CO2/Bicarbonate, 23=Uric Acid, 24=LDH, 25=Total Protein,
          26=Triglycerides, 27=CK/CPK, 28=Lithium
        """
        return {
            # LFT — Hepatic function panel (LOINC 24325-3)
            "26958001": ["7", "6", "3", "5", "2", "25", "12", "1"],
            # KFT — Renal function panel (LOINC 24362-6)
            "54610007": ["14", "22", "15", "16", "17", "28", "13"],
            # CMP — Comprehensive metabolic panel (LOINC 24320-4)
            "24320-4": ["1", "2", "3", "5", "6", "7", "8", "10", "12", "14", "15", "16", "17", "22"],
            # BMP — Basic metabolic panel (LOINC 24321-2)
            "24321-2": ["10", "14", "22", "8", "15", "16", "17"],
            # Lipid panel (LOINC 24331-1)
            "24331-1": ["9", "11", "26"],
        }

    def should_skip_obx(self, segment) -> bool:
        """
        Keep NM and ST type OBX segments only.
        Skip ED (embedded data) if the analyzer sends any.
        """
        value_type = hl7_to_str(segment, 2)
        if value_type in ("NM", "ST"):
            return False
        return True

    def extract_observation_id(self, obx_segment) -> tuple[str, str]:
        """
        Extract test code and display name from OBX-3.

        ADX AutoChem 200 format: OBX|n|NM|<test_id>^<test_name>||value|units
        Example: OBX|1|NM|1^ALBUMIN||4.2|g/dL|3.5-5.3|N|||F
        Returns: ("1", "ALBUMIN")
        """
        obx3 = hl7_to_str(obx_segment, 3)
        parts = obx3.split("^", 1) if obx3 else ["", ""]
        code = parts[0].strip()
        display = parts[1].strip() if len(parts) > 1 else ""
        return code, display

    def build_worklist_response(
        self,
        orders: list[ORUData],
        original_control_id: str,
        *,
        raw_query: str | None = None,
    ) -> list[str] | None:
        """
        Build ADX AutoChem 200 worklist response as two HL7 messages:
        1. QCK^Q02 — query acknowledgement
        2. DSR^Q03 — display response with sample/patient info and test orders

        The DSR uses positional DSP segments where DSP-1 is the field index
        and DSP-3 contains the value.

        Returns a list of two raw HL7 message strings, or None if no orders.
        """
        if not orders:
            return None

        now = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        messages = []

        # --- Message 1: QCK^Q02 (Query Acknowledgement) ---
        qck_segments = [
            f"MSH|^~\\&|LIS||||{now}||QCK^Q02"
            f"|{original_control_id}|P|2.3.1||||||UNICODE",
            f"MSA|AA|{original_control_id}",
            "ERR|0",
        ]
        qck_raw = "\r".join(qck_segments)
        qck_message = hl7.parse(qck_raw)
        messages.append(str(qck_message))

        # --- Message 2: DSR^Q03 (Display Response) ---
        dsr_segments = [
            f"MSH|^~\\&|LIS||||{now}||DSR^Q03"
            f"|{original_control_id}|P|2.3.1||||||UNICODE",
            f"MSA|AA|{original_control_id}",
            "ERR|0",
            f"QAK|{original_control_id}|OK",
        ]

        for order in orders:
            patient_id = order.patient_id or ""
            patient_name = order.patient_name or ""
            date_of_birth = order.date_of_birth or ""
            gender = order.gender or ""
            sample_id = order.sample_id or ""
            sample_type = order.sample_type or ""
            tests = order.tests

            # DSP segments — positional format for ADX AutoChem 200
            # Fields 1-28 are patient/sample demographics
            # Fields 29+ are test orders
            dsp_fields: list[str] = [""] * 28  # Pre-fill 28 empty fields

            # Key positions (1-indexed in DSP-1)
            dsp_fields[0] = "R"  # DSP|1| = Priority (R=Routine)
            dsp_fields[1] = patient_id  # DSP|2| = Patient ID
            dsp_fields[2] = patient_name  # DSP|3| = Patient Name
            dsp_fields[3] = date_of_birth  # DSP|4| = Date of Birth (YYYYMMDDHHmmss)
            dsp_fields[4] = gender  # DSP|5| = Gender
            dsp_fields[20] = sample_id  # DSP|21| = Barcode
            dsp_fields[21] = sample_id  # DSP|22| = Sample ID
            dsp_fields[25] = sample_type  # DSP|26| = Sample Type (Serum, Plasma, Urine)

            # Add test orders starting at position 29
            for test in tests:
                test_code = test.code
                dsp_fields.append(f"{test_code}^^^")

            # Build DSP segments (1-indexed field number in DSP-1)
            for idx, value in enumerate(dsp_fields):
                field_num = idx + 1
                dsr_segments.append(f"DSP|{field_num}||{value}||")

        dsr_raw = "\r".join(dsr_segments)
        dsr_message = hl7.parse(dsr_raw)
        messages.append(str(dsr_message))

        return messages


registry.register(AdxAutoChem200Profile)
