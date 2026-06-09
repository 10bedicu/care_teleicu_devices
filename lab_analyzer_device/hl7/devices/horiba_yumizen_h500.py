"""
HORIBA Yumizen H500/H500E hematology analyzer HL7 profile.

Reference: RAA085BEN — Output Format for Host Connection (v4.0.x, 06/2024)

Key differences from generic HL7 v2.3:
- HL7 v2.5
- Results: OUL^R22 (not ORU^R01)
- Orders: OML^O33 (not ORM^O01)
- Acknowledgment: ACK^R22 / ORL^O34
- Two sockets: one for results, one for orders
- SPM segment for specimen (not OBR-15)
- PID-3 format: ID^^^^PI
- OBX-3: LOINC code^name^LN (already sends LOINC natively)
- OBX-7: range_values^REFERENCE_RANGE (range type in component 2)
- OBX-8: abnormal flags (L, H, LL, HH, <, >, A, N, X, >>)
- OBX segments with value_type ED are reagent traceability or curves → skip
- OBX segments with value_type ST for "Dosage category" → skip
- NTE segments with comment_type I carry analytical alarms
- Sends CBC (18 params), DIF (20 params), ESR (1 param)
"""

from __future__ import annotations

from datetime import datetime

import hl7

from lab_analyzer_device.hl7.devices.base import DeviceHL7Profile, LoincMapping
from lab_analyzer_device.hl7.devices.registry import registry
from lab_analyzer_device.hl7.extractor import ObservationData, hl7_to_str
from lab_analyzer_device.hl7.builder import ORMData


class HoribaYumizenH500Profile(DeviceHL7Profile):

    @property
    def device_type(self) -> str:
        return "horiba_yumizen_h500"

    @property
    def display_name(self) -> str:
        return "HORIBA Yumizen H500/H500E"

    @property
    def hl7_version(self) -> str:
        return "2.5"

    @property
    def result_message_type(self) -> str:
        return "OUL^R22^OUL_R22"

    @property
    def order_message_type(self) -> str:
        return "OML^O33^OML_O33"

    @property
    def ack_message_type(self) -> str:
        return "ACK^R22^ACK_R22"

    @property
    def code_mappings(self) -> dict[str, LoincMapping]:
        """
        Yumizen H500 sends LOINC codes natively (system=LN) so these
        mappings are only needed as fallback if the system field is missing.

        From RAA085BEN §4.3.1.1 Parameters table.
        """
        return {
            # CBC
            "RBC": LoincMapping("789-8", "Erythrocytes [#/volume] in Blood by Automated count"),
            "HGB": LoincMapping("718-7", "Hemoglobin [Mass/volume] in Blood"),
            "HCT": LoincMapping("4544-3", "Hematocrit [Volume Fraction] of Blood by Automated count"),
            "MCV": LoincMapping("787-2", "MCV [Entitic mean volume] by Automated count"),
            "MCH": LoincMapping("785-6", "MCH [Entitic mass] by Automated count"),
            "MCHC": LoincMapping("786-4", "MCHC [Entitic Mass/volume] by Automated count"),
            "RDW-SD": LoincMapping("21000-5", "Erythrocyte distribution width [Entitic volume] by Automated count"),
            "RDW-CV": LoincMapping("788-0", "Erythrocyte distribution width [Ratio] by Automated count"),
            # No standard LOINC for microcytic/macrocytic RBC percentages
            "MIC": LoincMapping("MIC", "Microcytic Red Blood Cells percentage", system="local"),
            "MAC": LoincMapping("MAC", "Macrocytic Red Blood Cells percentage", system="local"),
            "PLT": LoincMapping("777-3", "Platelets [#/volume] in Blood by Automated count"),
            "PCT": LoincMapping("51637-7", "Plateletcrit [Volume Fraction] in Blood"),
            "PDW": LoincMapping("51631-0", "Platelet distribution width [Ratio] in Blood"),
            "MPV": LoincMapping("32623-1", "Platelet [Entitic mean volume] in Blood by Automated count"),
            "P-LCC": LoincMapping("96354-6", "Platelets Large [#/volume] in Blood by Automated count"),
            "P-LCR": LoincMapping("48386-7", "Platelets Large/Platelets in Blood by Automated count"),
            "WBC": LoincMapping("6690-2", "Leukocytes [#/volume] in Blood by Automated count"),
            # DIF
            "LYM#": LoincMapping("731-0", "Lymphocytes [#/volume] in Blood by Automated count"),
            "LYM%": LoincMapping("736-9", "Lymphocytes/Leukocytes in Blood by Automated count"),
            "MON#": LoincMapping("742-7", "Monocytes [#/volume] in Blood by Automated count"),
            "MON%": LoincMapping("5905-5", "Monocytes/Leukocytes in Blood by Automated count"),
            "NEU#": LoincMapping("751-8", "Neutrophils [#/volume] in Blood by Automated count"),
            "NEU%": LoincMapping("770-8", "Neutrophils/Leukocytes in Blood by Automated count"),
            "EOS#": LoincMapping("711-2", "Eosinophils [#/volume] in Blood by Automated count"),
            "EOS%": LoincMapping("713-8", "Eosinophils/Leukocytes in Blood by Automated count"),
            "BAS#": LoincMapping("704-7", "Basophils [#/volume] in Blood by Automated count"),
            "BAS%": LoincMapping("706-2", "Basophils/Leukocytes in Blood by Automated count"),
            "IMG#": LoincMapping("53115-2", "Immature granulocytes [#/volume] in Blood by Automated count"),
            "IMG%": LoincMapping("71695-1", "Immature granulocytes/Leukocytes in Blood by Automated count"),
            # No standard LOINC for immature monocytic/lymphocytic cells
            "IMM#": LoincMapping("IMM#", "Immature Monocytic cells [#/volume] in Blood", system="local"),
            "IMM%": LoincMapping("IMM%", "Immature Monocytic cells/Leukocytes in Blood", system="local"),
            "IML#": LoincMapping("IML#", "Immature Lymphocytic cells [#/volume] in Blood", system="local"),
            "IML%": LoincMapping("IML%", "Immature Lymphocytic cells/Leukocytes in Blood", system="local"),
            "ALY#": LoincMapping("43743-4", "Variant lymphocytes [#/volume] in Blood by Automated count"),
            "ALY%": LoincMapping("42250-1", "Variant lymphocytes/Leukocytes in Blood by Automated count"),
            "LIC#": LoincMapping("55432-9", "Immature cells [#/volume] in Blood"),
            "LIC%": LoincMapping("55433-7", "Immature cells/Leukocytes in Blood"),
            # ESR
            "ESR": LoincMapping("82477-1", "Erythrocyte [Sedimentation Rate] in Blood by Photometric method"),
        }

    @property
    def panel_mappings(self) -> dict[str, str]:
        """
        Yumizen H500 OBR-4 only accepts: CBC, DIF, or ESR.

        Maps LOINC panel codes to device-native identifiers.
        Per RAA085BEN §3.6: "The Universal Service Identifier field
        corresponds to any parameters or compatible panels: CBC, DIF, ESR."

        Also maps SNOMED codes commonly used in activity definitions.
        """
        return {
            # CBC panel (LOINC)
            "58410-2": "CBC",
            # CBC with auto differential (combined order = CBC + DIF)
            "57021-8": "CBC",
            # Differential panel (LOINC)
            "69738-3": "DIF",
            # ESR (LOINC)
            "82477-1": "ESR",
            # CBC (SNOMED)
            "26604007": "CBC",
            # Differential (SNOMED)
            "9091006": "DIF",
            # ESR (SNOMED)
            "416838001": "ESR",
        }

    # --- OBX filtering ---

    def extract_units(self, obx_segment) -> str:
        """
        Yumizen H500 sends properly-encoded CE fields for OBX-6 (units).
        Use component 1 (the UCUM identifier) which uses '*' for exponents.
        """
        return hl7_to_str(obx_segment, 6, 1) or hl7_to_str(obx_segment, 6)

    # Non-result OBX identifiers to skip
    _SKIP_OBX_IDENTIFIERS = {
        "Dosage category",    # OBX with ST type for patient profile
        "LYSE", "CLEANER", "DILUENT",  # Reagent traceability
    }

    def should_skip_obx(self, segment) -> bool:
        """
        Skip non-result OBX segments:
        - ED (Encapsulated Data): reagent traceability, curves, histograms
        - ST with "Dosage category": patient profile classification
        """
        value_type = hl7_to_str(segment, 2)
        if value_type == "ED":
            return True

        # Check observation identifier for known non-result fields
        obs_id = hl7_to_str(segment, 3, 2) or hl7_to_str(segment, 3, 1) or hl7_to_str(segment, 3)
        if obs_id in self._SKIP_OBX_IDENTIFIERS:
            return True

        return False

    # --- Patient ID extraction ---

    def extract_patient_id(self, pid_segment) -> str | None:
        """
        Yumizen PID-3 format: ID^^^^PI
        First component is the patient ID, fifth is the type code (PI).
        """
        return hl7_to_str(pid_segment, 3, 1) or None

    # --- Specimen extraction ---

    def extract_specimen_from_obr(self, obr_segment) -> str | None:
        """Yumizen uses SPM for specimen, not OBR-15."""
        return None

    def extract_specimen_from_spm(self, spm_segment) -> str | None:
        """SPM-2: Specimen ID."""
        return hl7_to_str(spm_segment, 2) or None

    # --- Observation extraction ---

    def extract_observation(self, obx_segment) -> ObservationData | None:
        """
        Extract observation with Yumizen-specific reference range parsing.

        OBX-7 format: "range_values^REFERENCE_RANGE"
        OBX-8 format: "flag~" (may have trailing ~)
        OBX-19: Date/Time of the Analysis (Yumizen uses field 19 instead of 14)
        """
        obs = super().extract_observation(obx_segment)
        if obs is None:
            return None

        # Parse Yumizen reference range: "4.20 - 6.00^REFERENCE_RANGE"
        # Extract just the range values (component 1), drop the type label
        raw_range = hl7_to_str(obx_segment, 7)
        if "^" in raw_range:
            range_parts = raw_range.split("^")
            range_value = range_parts[0].strip()
        else:
            range_value = raw_range

        # Parse abnormal flags — Yumizen may append ~ (repetition separator)
        raw_flags = hl7_to_str(obx_segment, 8)
        flags = raw_flags.rstrip("~").strip()

        # Yumizen uses OBX-19 for analysis datetime
        obs_datetime = hl7_to_str(obx_segment, 19) or hl7_to_str(obx_segment, 14) or None

        return ObservationData(
            set_id=obs.set_id,
            value_type=obs.value_type,
            code=obs.code,
            display=obs.display,
            system=obs.system,
            value=obs.value,
            units=obs.units,
            reference_range=range_value,
            abnormal_flags=flags,
            result_status=obs.result_status,
            observation_datetime=obs_datetime,
        )

    # --- Order building ---

    def build_order_message(self, order_data: ORMData, device_metadata: dict | None = None) -> hl7.Message:
        """
        Build an OML^O33 message for the Yumizen H500.

        Structure per RAA085BEN §4.1.2.1:
        MSH | PID | [NTE] | SPM | [OBX] | ORC | [TQ1] | OBR | [NTE]

        Validates and resolves LOINC test codes to device-native panel codes
        (CBC, DIF, ESR). For the combined "57021-8" (CBC+DIF), expands into
        two OBR segments.
        """
        # Validate and resolve LOINC codes to device panel codes
        resolved_tests = self.validate_tests(order_data.tests, device_metadata=device_metadata)

        # Expand combined panel: 57021-8 maps to CBC, but also needs DIF
        panel_codes = []
        for orig_test, resolved_test in zip(order_data.tests, resolved_tests):
            panel_codes.append(resolved_test.code)
            # If the original was the combined CBC+DIF panel, also add DIF
            if orig_test.code == "57021-8" and "DIF" not in panel_codes:
                panel_codes.append("DIF")

        # Deduplicate while preserving order
        seen = set()
        unique_panels = []
        for code in panel_codes:
            if code not in seen:
                seen.add(code)
                unique_panels.append(code)

        now = datetime.now().strftime("%Y%m%d%H%M%S")
        counter = now[-5:]  # last 5 digits as counter
        control_id = f"{now}{counter}"

        segments = []

        # MSH
        segments.append(
            f"MSH|^~\\&|{self.sending_application}|{self.sending_facility}"
            f"|||{now}||{self.order_message_type}"
            f"|{control_id}|P|{self.hl7_version}||||||UNICODE UTF-8"
        )

        # PID
        name_parts = order_data.patient_name.split(" ", 1) if order_data.patient_name else ["", ""]
        last_name = name_parts[1] if len(name_parts) > 1 else ""
        first_name = name_parts[0] if name_parts else ""
        dob = order_data.date_of_birth or ""
        segments.append(
            f"PID|1||{order_data.patient_id}^^^^PI||{last_name}^{first_name}||{dob}"
        )

        # SPM
        specimen_id = order_data.specimen_id or ""
        segments.append(
            f"SPM|1|{specimen_id}||WB||||||P"
        )

        # ORC — ORC-12: Ordering Provider
        physician_field = ""
        if order_data.ordering_physician:
            p = order_data.ordering_physician
            physician_field = f"{p.id}^{p.family_name}^{p.given_name}"

        segments.append(
            f"ORC|NW||||||||||||{physician_field}" if physician_field
            else "ORC|NW"
        )

        # OBR for each panel code (device-native: CBC, DIF, ESR)
        for i, panel_code in enumerate(unique_panels, start=1):
            segments.append(
                f"OBR|{i}|||{panel_code}"
            )

        raw = "\r".join(segments)
        return hl7.parse(raw)


registry.register(HoribaYumizenH500Profile)
