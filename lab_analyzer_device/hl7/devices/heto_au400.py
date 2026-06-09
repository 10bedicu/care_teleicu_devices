"""
Heto AU400 Automatic Biochemistry Analyzer HL7 profile.

Fully automated chemistry analyzer.
Communication: Host Query (analyzer sends QRY^Q02 to request worklist,
receives QCK^Q02 + DSR^Q03 response, then sends ORU^R01 results).

Key characteristics per documentation:
- HL7 v2.5
- Results: ORU^R01 with MSH-16 indicating result type:
  - 0 = patient sample results
  - 1 = calibration results
  - 2 = QC results
- OBX-3: Empty or integer test channel number (item ID)
- OBX-4: Test name (primary identifier, e.g. "Tbil", "ALT", "AST")
- OBX-5: Result value
- OBX-6: Units
- OBX-13: Original result value
- OBX-14: Test time
- OBX-2 = NM: numeric results (keep)
- OBX-2 = ST: string values (keep — qualitative items)
- Query: QRY^Q02 with barcode in QRD-8, query type in QRD-2:
  - BC = barcode query
  - SN = sample ID query
  - ST = time-based query
- Response: Two messages:
  1. QCK^Q02 — acknowledgement
  2. DSR^Q03 — display response with positional DSP segments:
     - DSP|1| = admission no.
     - DSP|2| = bed no.
     - DSP|3| = patient name
     - DSP|4| = date of birth (YYYYMMDDHHmmss)
     - DSP|5| = gender (M/F/O)
     - DSP|6| = blood type
     - DSP|7-20| = demographics
     - DSP|21| = barcode (required)
     - DSP|22| = sample ID
     - DSP|23| = sample time
     - DSP|24| = priority (Y/N)
     - DSP|26| = sample type
     - DSP|27| = fetch doctor
     - DSP|28| = fetch department
     - DSP|29| = test orders as comma-separated names (e.g. "ALT,TP")
- DSC segment: non-empty = more samples follow, empty = last sample
- MSH-3: HETO (from analyzer), LIS sets MSH-5/6 to HETO/AU400
- MSH-4: AU400
- MSH-18: UNICODE

Document example (only 3 item IDs confirmed):
  Item IDs: 2, 5, 6
  Item Names: TBil, ALT, AST

NOTE: OBX-3 is typically EMPTY in ORU messages from this device.
The test name in OBX-4 is the primary identifier for mapping results.
"""

from __future__ import annotations

from datetime import datetime, timezone

import hl7

from lab_analyzer_device.hl7.devices.base import CommunicationMode, DeviceHL7Profile, LoincMapping
from lab_analyzer_device.hl7.devices.registry import registry
from lab_analyzer_device.hl7.extractor import ObservationData, ORUData, hl7_to_str


class HetoAU400Profile(DeviceHL7Profile):

    @property
    def device_type(self) -> str:
        return "heto_au400"

    @property
    def display_name(self) -> str:
        return "Heto AU400 Automatic Biochemistry Analyzer"

    @property
    def hl7_version(self) -> str:
        return "2.5"

    @property
    def communication_mode(self) -> CommunicationMode:
        return "host_query"

    @property
    def sending_application(self) -> str:
        return "LIS"

    @property
    def code_mappings(self) -> dict[str, LoincMapping]:
        """
        Heto AU400 test name → LOINC mappings.

        The AU400 primarily identifies tests by name in OBX-4. OBX-3 is
        typically empty per the documented ORU example. When OBX-3 contains
        a channel number, it is used as an additional lookup key.

        Only channel IDs confirmed by the documentation are mapped:
          2 = TBil, 5 = ALT, 6 = AST

        The worklist (DSP|29|) uses comma-separated test names (e.g. "ALT,TP").
        """
        return {
            # Documented channel IDs (from ORU example: Item IDs 2, 5, 6)
            "2": LoincMapping("1975-2", "Bilirubin.total [Mass/volume] in Serum or Plasma"),
            "5": LoincMapping("1742-6", "Alanine aminotransferase [Enzymatic activity/volume] in Serum or Plasma"),
            "6": LoincMapping("1920-8", "Aspartate aminotransferase [Enzymatic activity/volume] in Serum or Plasma"),
            # Test names (OBX-4 values — primary identification mechanism)
            "Tbil": LoincMapping("1975-2", "Bilirubin.total [Mass/volume] in Serum or Plasma"),
            "TBil": LoincMapping("1975-2", "Bilirubin.total [Mass/volume] in Serum or Plasma"),
            "TBIL": LoincMapping("1975-2", "Bilirubin.total [Mass/volume] in Serum or Plasma"),
            "ALT": LoincMapping("1742-6", "Alanine aminotransferase [Enzymatic activity/volume] in Serum or Plasma"),
            "SGPT": LoincMapping("1742-6", "Alanine aminotransferase [Enzymatic activity/volume] in Serum or Plasma"),
            "AST": LoincMapping("1920-8", "Aspartate aminotransferase [Enzymatic activity/volume] in Serum or Plasma"),
            "SGOT": LoincMapping("1920-8", "Aspartate aminotransferase [Enzymatic activity/volume] in Serum or Plasma"),
            "DBil": LoincMapping("1968-7", "Bilirubin.direct [Mass/volume] in Serum or Plasma"),
            "DBIL": LoincMapping("1968-7", "Bilirubin.direct [Mass/volume] in Serum or Plasma"),
            "ALB": LoincMapping("1751-7", "Albumin [Mass/volume] in Serum or Plasma"),
            "TP": LoincMapping("2885-2", "Protein [Mass/volume] in Serum or Plasma"),
            "ALP": LoincMapping("6768-6", "Alkaline phosphatase [Enzymatic activity/volume] in Serum or Plasma"),
            "GGT": LoincMapping("2324-2", "Gamma glutamyl transferase [Enzymatic activity/volume] in Serum or Plasma"),
            "BUN": LoincMapping("3094-0", "Urea nitrogen [Mass/volume] in Serum or Plasma"),
            "UREA": LoincMapping("3094-0", "Urea nitrogen [Mass/volume] in Serum or Plasma"),
            "CREA": LoincMapping("2160-0", "Creatinine [Mass/volume] in Serum or Plasma"),
            "UA": LoincMapping("3084-1", "Urate [Mass/volume] in Serum or Plasma"),
            "CHOL": LoincMapping("2093-3", "Cholesterol [Mass/volume] in Serum or Plasma"),
            "TG": LoincMapping("2571-8", "Triglyceride [Mass/volume] in Serum or Plasma"),
            "TGL": LoincMapping("2571-8", "Triglyceride [Mass/volume] in Serum or Plasma"),
            "HDL": LoincMapping("2085-9", "Cholesterol in HDL [Mass/volume] in Serum or Plasma"),
            "LDL": LoincMapping("2089-1", "Cholesterol in LDL [Mass/volume] in Serum or Plasma"),
            "GLU": LoincMapping("2345-7", "Glucose [Mass/volume] in Serum or Plasma"),
            "K": LoincMapping("2823-3", "Potassium [Moles/volume] in Serum or Plasma"),
            "NA": LoincMapping("2951-2", "Sodium [Moles/volume] in Serum or Plasma"),
            "CA": LoincMapping("17861-6", "Calcium [Mass/volume] in Serum or Plasma"),
            "CL": LoincMapping("2075-0", "Chloride [Moles/volume] in Serum or Plasma"),
            "CRP": LoincMapping("1988-5", "C reactive protein [Mass/volume] in Serum or Plasma"),
            "AMY": LoincMapping("1798-8", "Amylase [Enzymatic activity/volume] in Serum or Plasma"),
            "LDH": LoincMapping("2532-0", "Lactate dehydrogenase [Enzymatic activity/volume] in Serum or Plasma"),
            "LIP": LoincMapping("3040-3", "Lipase [Enzymatic activity/volume] in Serum or Plasma"),
            "HBA1C": LoincMapping("4548-4", "Hemoglobin A1c/Hemoglobin.total in Blood"),
            "HbA1C": LoincMapping("4548-4", "Hemoglobin A1c/Hemoglobin.total in Blood"),
        }

    @property
    def panel_mappings(self) -> dict[str, str | list[str]]:
        """
        LOINC panel codes → Heto AU400 test names for ordering.

        The AU400 worklist uses comma-separated test names in DSP|29|
        (e.g. "ALT,TP"). Panel mappings expand to lists of test names
        that the analyzer recognizes.
        """
        return {
            # LFT — Hepatic function panel
            "26958001": ["Tbil", "DBil", "ALT", "AST", "ALP", "TP", "GGT", "ALB"],
            # KFT — Renal function panel
            "54610007": ["BUN", "CREA", "UA", "K", "NA", "CA"],
            # Lipid panel
            "24331-1": ["CHOL", "TG", "HDL", "LDL"],
        }

    def should_skip_obx(self, segment) -> bool:
        """
        Keep NM and ST type OBX segments only.
        The AU400 only sends NM and ST results for patient samples.
        """
        value_type = hl7_to_str(segment, 2)
        return value_type not in ("NM", "ST")

    def extract_observation_id(self, obx_segment) -> tuple[str, str]:
        """
        Extract test code and display name from OBX segment.

        Heto AU400 format per documentation example:
          OBX|1|NM||Tbil|100|umol/L|||||||100|20070413093253||||

        - OBX-3: Typically empty; may contain channel number (integer)
        - OBX-4: Test name (e.g. "Tbil", "ALT", "AST") — primary identifier

        Returns: (code, display_name)
        """
        obx3 = hl7_to_str(obx_segment, 3).strip()
        obx4 = hl7_to_str(obx_segment, 4).strip()

        if obx3:
            # OBX-3 has a channel number; use it as code, OBX-4 as display
            return obx3, obx4
        # OBX-3 is empty (typical case) — use OBX-4 test name as the code
        return obx4, obx4

    def extract_observation(self, obx_segment) -> ObservationData | None:
        """
        Extract a single observation from an OBX segment.

        Overrides base implementation because the Heto AU400 sends OBX-3
        empty and puts the test identifier in OBX-4. The base implementation
        would return None for empty OBX-3.

        Documented format:
          OBX|1|NM||Tbil|100|umol/L|0-17.1|H||N|F||100|20070413093253||||
        """
        set_id_str = hl7_to_str(obx_segment, 1)
        set_id = int(set_id_str) if set_id_str.isdigit() else 0

        value_type = hl7_to_str(obx_segment, 2)

        # Extract code using device-specific logic (OBX-4 primary)
        code, display = self.extract_observation_id(obx_segment)
        if not code:
            return None

        # Resolve to LOINC if mapping exists
        system, resolved_code, mapped_display = self.resolve_code(code, "")
        display = display or mapped_display

        value = hl7_to_str(obx_segment, 5)
        units = self.extract_units(obx_segment)
        reference_range = hl7_to_str(obx_segment, 7)
        abnormal_flags = hl7_to_str(obx_segment, 8)
        result_status = hl7_to_str(obx_segment, 11)
        observation_datetime = hl7_to_str(obx_segment, 14) or None

        return ObservationData(
            set_id=set_id,
            value_type=value_type,
            code=resolved_code,
            display=display,
            system=system,
            value=value,
            units=units,
            reference_range=reference_range,
            abnormal_flags=abnormal_flags,
            result_status=result_status,
            observation_datetime=observation_datetime,
        )

    def extract_specimen_from_obr(self, obr_segment) -> str | None:
        """
        OBR-2 (Placer Order Number) = sample barcode.
        Per doc: "Patient order number, used as sample barcode"
        """
        return hl7_to_str(obr_segment, 2) or None

    def build_worklist_response(
        self,
        orders: list[ORUData],
        original_control_id: str,
        *,
        raw_query: str | None = None,
    ) -> list[str] | None:
        """
        Build Heto AU400 worklist response as two HL7 messages:
        1. QCK^Q02 — query acknowledgement
        2. DSR^Q03 — display response with sample/patient info and test orders

        The DSR uses positional DSP segments where DSP-1 is the field index
        and DSP-3 contains the value. Test items at position 29 use
        comma-separated test names (per doc example: "ALT,TP").

        Returns a list of two raw HL7 message strings, or None if no orders.
        """
        if not orders:
            return None

        now = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        messages = []

        # --- Message 1: QCK^Q02 (Query Acknowledgement) ---
        qck_segments = [
            f"MSH|^~\\&|LIS||HETO|AU400|{now}||QCK^Q02"
            f"|{original_control_id}|P|2.5||||||UNICODE",
            f"MSA|AA|{original_control_id}|Message accepted|||0",
            "ERR|0",
            f"QAK|SR|OK",
        ]
        qck_raw = "\r".join(qck_segments)
        qck_message = hl7.parse(qck_raw)
        messages.append(str(qck_message))

        # --- Message 2: DSR^Q03 (Display Response) ---
        dsr_segments = [
            f"MSH|^~\\&|LIS||HETO|AU400|{now}||DSR^Q03"
            f"|{original_control_id}|P|2.5||||||UNICODE",
            f"MSA|AA|{original_control_id}|Message accepted|||0",
            "ERR|0",
            f"QAK|SR|OK",
        ]

        for order_idx, order in enumerate(orders):
            patient_name = order.patient_name or ""
            date_of_birth = order.date_of_birth or ""
            gender = order.gender or ""
            sample_id = order.sample_id or ""
            sample_type = order.sample_type or "serum"
            barcode = order.barcode or sample_id
            priority = order.priority or "N"
            tests = order.tests

            # QRD segment for this order
            dsr_segments.append(
                f"QRD|{now}|BC|D|{order_idx + 1}|||RD||||{barcode}"
            )

            # DSP segments — positional format for Heto AU400
            # Positions 1-28: patient/sample demographics
            # Position 29: comma-separated test names
            dsp_fields: list[str] = [""] * 28  # Pre-fill 28 empty fields

            dsp_fields[2] = patient_name  # DSP|3| = Patient Name
            dsp_fields[3] = date_of_birth  # DSP|4| = Date of Birth
            dsp_fields[4] = gender  # DSP|5| = Gender
            dsp_fields[20] = barcode  # DSP|21| = Barcode (required)
            dsp_fields[21] = sample_id  # DSP|22| = Sample ID
            dsp_fields[23] = priority  # DSP|24| = Priority
            dsp_fields[25] = sample_type  # DSP|26| = Sample Type

            # Position 29: comma-separated test names (per doc: "ALT,TP")
            test_names = ",".join(t.display or t.code for t in tests)
            dsp_fields.append(test_names)

            # Build DSP segments
            for idx, value in enumerate(dsp_fields):
                field_num = idx + 1
                dsr_segments.append(f"DSP|{field_num}||{value}||")

            # DSC — continuation pointer (empty = last sample)
            is_last = order_idx == len(orders) - 1
            dsr_segments.append(f"DSC|{'|' if is_last else '1|'}")

        dsr_raw = "\r".join(dsr_segments)
        dsr_message = hl7.parse(dsr_raw)
        messages.append(str(dsr_message))

        return messages


registry.register(HetoAU400Profile)
