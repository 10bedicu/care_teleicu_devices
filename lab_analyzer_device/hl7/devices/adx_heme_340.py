"""
Athenese-Dx ADX-HEME-340 Auto Hematology Analyzer HL7 profile.

3-part differential hematology analyzer.
Communication: Unidirectional (results only via ORU^R01).

Key characteristics:
- HL7 v2.3.1
- Results: ORU^R01 with plain-text OBX-3 codes (WBC, Lymph#, HGB, etc.)
- OBR-3: Filler Order Number = sample number (integer accession ID)
- OBR-4: 00001^Automated Count^99MRC (for CBC results)
- OBX-8: abnormal flags (N, H, L, RH, RL)
- OBX-2 = NM: numeric results (keep)
- OBX-2 = ED: histograms/scattergrams (skip)
- OBX-2 = IS: mode/flag fields (skip)
- MSH-11: P = sample/worklist, Q = QC data
- MSH-18: UNICODE (UTF-8)
- Heartbeat: 0x02 every 3 seconds on TCP
"""

from __future__ import annotations

from lab_analyzer_device.hl7.devices.base import CommunicationMode, DeviceHL7Profile, LoincMapping
from lab_analyzer_device.hl7.devices.registry import registry
from lab_analyzer_device.hl7.extractor import hl7_to_str


class AdxHeme340Profile(DeviceHL7Profile):

    @property
    def device_type(self) -> str:
        return "adx_heme_340"

    @property
    def display_name(self) -> str:
        return "Athenese-Dx ADX-HEME-340 Auto Hematology Analyzer"

    @property
    def hl7_version(self) -> str:
        return "2.3.1"

    @property
    def communication_mode(self) -> CommunicationMode:
        return "unidirectional"

    @property
    def code_mappings(self) -> dict[str, LoincMapping]:
        """
        ADX-HEME-340 sends plain-text codes in OBX-3 (single component, no system).
        Example: OBX|22|NM|WBC||11.0|10^3/uL|4 - 10|H|||F
        """
        return {
            # White blood cells
            "WBC": LoincMapping("6690-2", "Leukocytes [#/volume] in Blood by Automated count"),
            # 3-part differential — absolute counts
            # Note: "Mid" is the combined Monocyte+Eosinophil+Basophil population
            # from a 3-part diff. LOINC 26484-6 (Monocytes) is the standard mapping.
            "Lymph#": LoincMapping("731-0", "Lymphocytes [#/volume] in Blood by Automated count"),
            "Mid#": LoincMapping("26484-6", "Monocytes [#/volume] in Blood"),
            "Gran#": LoincMapping("751-8", "Neutrophils [#/volume] in Blood by Automated count"),
            # 3-part differential — percentages
            "Lymph%": LoincMapping("736-9", "Lymphocytes/Leukocytes in Blood by Automated count"),
            "Mid%": LoincMapping("26485-3", "Monocytes/Leukocytes in Blood"),
            "Gran%": LoincMapping("770-8", "Neutrophils/Leukocytes in Blood by Automated count"),
            # Red blood cells
            "RBC": LoincMapping("789-8", "Erythrocytes [#/volume] in Blood by Automated count"),
            "HGB": LoincMapping("718-7", "Hemoglobin [Mass/volume] in Blood"),
            "HCT": LoincMapping("4544-3", "Hematocrit [Volume Fraction] of Blood by Automated count"),
            "MCV": LoincMapping("787-2", "MCV [Entitic mean volume] by Automated count"),
            "MCH": LoincMapping("785-6", "MCH [Entitic mass] by Automated count"),
            "MCHC": LoincMapping("786-4", "MCHC [Entitic Mass/volume] by Automated count"),
            # Red cell distribution width
            "RDW-CV": LoincMapping("788-0", "Erythrocyte distribution width [Ratio] by Automated count"),
            "RDW-SD": LoincMapping("21000-5", "Erythrocyte distribution width [Entitic volume] by Automated count"),
            "RWD-SD": LoincMapping("21000-5", "Erythrocyte distribution width [Entitic volume] by Automated count"),
            # Platelets
            "PLT": LoincMapping("777-3", "Platelets [#/volume] in Blood by Automated count"),
            "MPV": LoincMapping("32623-1", "Platelet [Entitic mean volume] in Blood by Automated count"),
            "PDW": LoincMapping("32207-3", "Platelet distribution width [Entitic volume] in Blood by Automated count"),
            "PCT": LoincMapping("51637-7", "Plateletcrit [Volume Fraction] in Blood"),
            "PLCC": LoincMapping("96354-6", "Platelets Large [#/volume] in Blood by Automated count"),
            "PLCR": LoincMapping("48386-7", "Platelets Large/Platelets in Blood by Automated count"),
        }

    def should_skip_obx(self, segment) -> bool:
        """
        Keep only NM (numeric) result OBX segments.
        Skip ED (histograms/scattergrams) and IS (mode settings/flags).
        """
        value_type = hl7_to_str(segment, 2)
        return value_type != "NM"

    def extract_patient_id(self, pid_segment) -> str | None:
        """ADX PID-3 format: ID^^^^MR — first component is the MRN."""
        return hl7_to_str(pid_segment, 3, 1) or hl7_to_str(pid_segment, 3) or None

    def extract_specimen_from_obr(self, obr_segment) -> str | None:
        """OBR-3 (Filler Order Number) = sample number / accession identifier."""
        return hl7_to_str(obr_segment, 3) or None


registry.register(AdxHeme340Profile)
