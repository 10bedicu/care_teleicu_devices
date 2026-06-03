"""
Mindray BC-5150 Auto Hematology Analyzer HL7 profile.

3-part/5-part differential hematology analyzer (3107 protocol).
Communication: Host Query (analyzer sends ORM^O01 to request worklist,
receives ORR^O02, then sends ORU^R01 results).

Key characteristics:
- HL7 v2.3.1
- Results: ORU^R01 with LOINC codes in OBX-3 (system=LN) and 99MRC codes
- Orders: ORM^O01 worklist query with ORC|RF||<sample_id>||IP
- Response: ORR^O02 with MSA, PID, PV1, ORC(AF|<sample_id>), OBR, OBX
- OBR-4: 00001^Automated Count^99MRC (for CBC results)
- OBX-2 = NM: numeric results (keep)
- OBX-2 = ED: histograms/scattergrams (skip)
- OBX-2 = IS: mode/flag fields (skip)
- OBX-2 = ST: remarks (skip)
- MSH-11: P = sample/worklist, Q = QC data
- MSH-18: UNICODE (UTF-8)
- PID-3: patient ID^^^^MR format
"""

from __future__ import annotations

from datetime import datetime, timezone

import hl7

from lab_analyzer_device.hl7.devices.base import (
    CommunicationMode,
    DeviceHL7Profile,
    Hl7ConnectionMode,
    LoincMapping,
)
from lab_analyzer_device.hl7.devices.registry import registry
from lab_analyzer_device.hl7.extractor import ORUData, _str


class MindrayBC5150Profile(DeviceHL7Profile):

    @property
    def device_type(self) -> str:
        return "mindray_bc_5150"

    @property
    def display_name(self) -> str:
        return "Mindray BC-5150 Auto Hematology Analyzer"

    @property
    def hl7_version(self) -> str:
        return "2.3.1"

    @property
    def communication_mode(self) -> CommunicationMode:
        return "host_query"

    @property
    def hl7_connection_mode(self) -> Hl7ConnectionMode:
        """BC-5150 listens on TCP port 5100; the gateway dials out to it."""
        return "outbound"

    @property
    def default_oru_port(self) -> int:
        return 5100

    @property
    def sending_application(self) -> str:
        return "LIS"

    @property
    def code_mappings(self) -> dict[str, LoincMapping]:
        """
        Mindray BC-5150 OBX-3 codes mapped to LOINC.

        The BC-5150 sends LOINC codes natively (system=LN) for standard
        parameters, and 99MRC codes for proprietary parameters (PCT, PLCC,
        PLCR, Blast%, MID#, MID%, GRAN#, GRAN%).

        LOINC displays validated against loinc.org.
        """
        return {
            # White blood cells
            "6690-2": LoincMapping("6690-2", "Leukocytes [#/volume] in Blood by Automated count"),
            # 5-part differential — absolute counts
            "704-7": LoincMapping("704-7", "Basophils [#/volume] in Blood by Automated count"),
            "751-8": LoincMapping("751-8", "Neutrophils [#/volume] in Blood by Automated count"),
            "711-2": LoincMapping("711-2", "Eosinophils [#/volume] in Blood by Automated count"),
            "731-0": LoincMapping("731-0", "Lymphocytes [#/volume] in Blood by Automated count"),
            "742-7": LoincMapping("742-7", "Monocytes [#/volume] in Blood by Automated count"),
            # 5-part differential — percentages
            "706-2": LoincMapping("706-2", "Basophils/100 leukocytes in Blood by Automated count"),
            "770-8": LoincMapping("770-8", "Neutrophils/100 leukocytes in Blood by Automated count"),
            "713-8": LoincMapping("713-8", "Eosinophils/100 leukocytes in Blood by Automated count"),
            "736-9": LoincMapping("736-9", "Lymphocytes/100 leukocytes in Blood by Automated count"),
            "5905-5": LoincMapping("5905-5", "Monocytes/100 leukocytes in Blood by Automated count"),
            # RUO parameters
            "26477-0": LoincMapping("26477-0", "Variant lymphocytes [#/volume] in Blood"),
            "13046-8": LoincMapping("13046-8", "Variant lymphocytes/Leukocytes in Blood"),
            "10000": LoincMapping("55432-9", "Immature cells [#/volume] in Blood"),
            "10001": LoincMapping("55433-7", "Immature cells/Leukocytes in Blood"),
            # Blasts (99MRC Blast% only — Blast# sent as LN 30376-8)
            "10049": LoincMapping("26446-5", "Blasts/Leukocytes in Blood"),
            # Red blood cells
            "789-8": LoincMapping("789-8", "Erythrocytes [#/volume] in Blood by Automated count"),
            "718-7": LoincMapping("718-7", "Hemoglobin [Mass/volume] in Blood"),
            "4544-3": LoincMapping("4544-3", "Hematocrit [Volume Fraction] of Blood by Automated count"),
            "787-2": LoincMapping("787-2", "MCV [Entitic volume] by Automated count"),
            "785-6": LoincMapping("785-6", "MCH [Entitic mass] by Automated count"),
            "786-4": LoincMapping("786-4", "MCHC [Mass/volume] by Automated count"),
            # Red cell distribution width
            "788-0": LoincMapping("788-0", "Erythrocyte distribution width [Ratio] by Automated count"),
            "21000-5": LoincMapping("21000-5", "Erythrocyte distribution width [Entitic volume] by Automated count"),
            # Platelets
            "777-3": LoincMapping("777-3", "Platelets [#/volume] in Blood by Automated count"),
            "32623-1": LoincMapping("32623-1", "Platelet mean volume [Entitic volume] in Blood by Automated count"),
            "32207-3": LoincMapping("32207-3", "Platelet distribution width [Entitic volume] in Blood by Automated count"),
            # 99MRC proprietary codes
            "10002": LoincMapping("51637-7", "Plateletcrit [Volume Fraction] in Blood"),
            "10013": LoincMapping("96354-6", "Platelets Large [#/volume] in Blood by Automated count"),
            "10014": LoincMapping("48386-7", "Platelets Large/Platelets in Blood by Automated count"),
            # 3-part differential (MID/GRAN) — used when running in 3-diff mode
            "10027": LoincMapping("26484-6", "Monocytes [#/volume] in Blood"),
            "10029": LoincMapping("26485-3", "Monocytes/Leukocytes in Blood"),
            "10028": LoincMapping("751-8", "Neutrophils [#/volume] in Blood by Automated count"),
            "10030": LoincMapping("770-8", "Neutrophils/100 leukocytes in Blood by Automated count"),
        }

    @property
    def panel_mappings(self) -> dict[str, str]:
        """
        LOINC/SNOMED panel codes → Mindray BC-5150 OBR-4 service type.

        BC-5150 uses 00001^Automated Count^99MRC for all CBC analyses.
        Test mode (CBC vs CBC+DIFF) is controlled via OBX settings in the
        worklist response, not via OBR-4.
        """
        return {
            "58410-2": "00001",
            "57021-8": "00001",
            "69738-3": "00001",
            "26604007": "00001",
        }

    _SKIP_OBX_CODES = {
        # Mode/metadata (IS type — also caught by value_type check)
        "08001", "08002", "08003", "01002", "01006",
        # Age (NM metadata)
        "30525-0",
        # QC/discriminator coordinates
        "10003", "10004", "10005", "10006", "10007", "10008",
        # 5-part scattergram discriminator X/Y/Z
        "10069", "10070", "10071", "10072", "10073", "10074", "10075", "10076", "10077",
        # Histogram metadata (NM type but non-result)
        "15004", "15001", "15002", "15003", "15005", "15006", "15007", "15009",
        "15010", "15011", "15012", "15013",
        "15051", "15052", "15053",
        "15111", "15112", "15113",
        "15203", "15204",
        # Flags (IS type)
        "12011", "34165-1", "15192-8", "12013", "12014", "12015", "12016",
        "12045", "12046", "12048", "12049", "12050", "12051", "12052",
    }

    def should_skip_obx(self, segment) -> bool:
        """
        Keep only NM (numeric) OBX segments that represent clinical results.
        Skip ED/IS/ST types and NM segments with metadata/discriminator codes.
        """
        value_type = _str(segment, 2)

        if value_type in ("ED", "IS", "ST"):
            return True

        if value_type == "NM":
            code = _str(segment, 3, 1) or _str(segment, 3)
            if code in self._SKIP_OBX_CODES:
                return True

        return False

    def extract_patient_id(self, pid_segment) -> str | None:
        """BC-5150 PID-3 format: patientID^^^^MR — first component is the MRN."""
        return _str(pid_segment, 3, 1) or _str(pid_segment, 3) or None

    def extract_specimen_from_obr(self, obr_segment) -> str | None:
        """OBR-3 (Filler Order Number) = sample ID / accession identifier."""
        return _str(obr_segment, 3) or None

    def build_worklist_response(
        self, orders: list[ORUData], original_control_id: str
    ) -> str | None:
        """
        Build a Mindray BC-5150 specific ORR^O02 worklist response.

        OBX settings control the analysis mode:
        - 08002^Blood Mode: W=whole blood, P=predilute
        - 08003^Test Mode: CBC or CBC+DIFF
        """
        if not orders:
            return None

        now = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")

        segments = []

        segments.append(
            f"MSH|^~\\&||Mindray|||{now}||ORR^O02"
            f"|{original_control_id}|P|2.3.1||||||UNICODE"
        )
        segments.append(f"MSA|AA|{original_control_id}")

        for order in orders:
            patient_id = order.patient_id or ""
            patient_name = order.patient_name or ""
            date_of_birth = order.date_of_birth or ""
            gender = order.gender or ""
            sample_id = order.sample_id or ""
            department = order.department or ""
            bed = order.bed or ""
            collect_time = order.collect_time or ""
            test_mode = order.test_mode or "CBC+DIFF"
            blood_mode = order.blood_mode or "W"

            segments.append(
                f"PID|1||{patient_id}^^^^MR||{patient_name}||{date_of_birth}|{gender}"
            )
            segments.append(f"PV1|1||{department}^^{bed}")
            segments.append(f"ORC|AF|{sample_id}")
            segments.append(
                f"OBR|1|{sample_id}||00001^Automated Count^99MRC"
                f"||{collect_time}||||||||{collect_time}||||||||||HM"
            )

            obx_idx = 1
            segments.append(
                f"OBX|{obx_idx}|IS|08002^Blood Mode^99MRC||{blood_mode}||||||F"
            )
            obx_idx += 1
            segments.append(
                f"OBX|{obx_idx}|IS|08003^Test Mode^99MRC||{test_mode}||||||F"
            )

        raw = "\r".join(segments)
        message = hl7.parse(raw)
        return str(message)


registry.register(MindrayBC5150Profile)
