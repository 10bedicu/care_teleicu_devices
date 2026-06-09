"""
CellQuant BF-6900 Automatic Hematology Analyzer HL7 profile.

5-part differential hematology analyzer with CRP.
Communication: Host Query (analyzer sends ORM^O01 to request worklist,
receives ORR^O02, then sends ORU^R01 results).

Key characteristics:
- HL7 v2.3.1
- Results: ORU^R01 with custom numeric OBX-3 codes (2006-2032)
- Orders: ORM^O01 worklist query with ORC|RF||<barcode>||IP
- Response: ORR^O02 with MSA, PID, PV1, ORC(AF), OBR, OBX (analysis settings)
- OBR-4: 1001^CountResults (sample count)
- OBX-2 = NM: numeric results (keep)
- OBX-2 = ED: histograms/scattergrams (skip — codes 2101, 2102, 2033, 2034)
- OBX-2 = IS: analysis mode metadata (skip — codes 2001-2005)
- MSH-3: BF-6900
- MSH-11: P = sample/worklist query, Q = QC count results
- MSH-18: UTF-8
- PID-3: Case number (patient ID)
- PID-31: Age with unit (e.g. 25^Y)
"""

from __future__ import annotations

from datetime import datetime, timezone

import hl7

from lab_analyzer_device.hl7.devices.base import CommunicationMode, DeviceHL7Profile, LoincMapping
from lab_analyzer_device.hl7.devices.registry import registry
from lab_analyzer_device.hl7.extractor import ORUData, hl7_to_str


class CellQuantBF6900Profile(DeviceHL7Profile):

    @property
    def device_type(self) -> str:
        return "cellquant_bf_6900"

    @property
    def display_name(self) -> str:
        return "CellQuant BF-6900"

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
        BF-6900 OBX-3 codes (2006-2032) mapped to LOINC.
        Codes are numeric strings without a coding system component.
        Example: OBX|5|NM|2006^V_WBC||4.63|10^9/L|4-10||||F||
        """
        return {
            # White blood cells
            "2006": LoincMapping("6690-2", "Leukocytes [#/volume] in Blood by Automated count"),
            # 5-part differential — percentages
            "2007": LoincMapping("770-8", "Neutrophils/100 leukocytes in Blood by Automated count"),
            "2008": LoincMapping("736-9", "Lymphocytes/100 leukocytes in Blood by Automated count"),
            "2009": LoincMapping("5905-5", "Monocytes/100 leukocytes in Blood by Automated count"),
            "2010": LoincMapping("713-8", "Eosinophils/100 leukocytes in Blood by Automated count"),
            "2011": LoincMapping("706-2", "Basophils/100 leukocytes in Blood by Automated count"),
            # 5-part differential — absolute counts
            "2012": LoincMapping("751-8", "Neutrophils [#/volume] in Blood by Automated count"),
            "2013": LoincMapping("731-0", "Lymphocytes [#/volume] in Blood by Automated count"),
            "2014": LoincMapping("742-7", "Monocytes [#/volume] in Blood by Automated count"),
            "2015": LoincMapping("711-2", "Eosinophils [#/volume] in Blood by Automated count"),
            "2016": LoincMapping("704-7", "Basophils [#/volume] in Blood by Automated count"),
            # Red blood cells
            "2017": LoincMapping("789-8", "Erythrocytes [#/volume] in Blood by Automated count"),
            "2018": LoincMapping("718-7", "Hemoglobin [Mass/volume] in Blood"),
            "2019": LoincMapping("787-2", "MCV [Entitic volume] by Automated count"),
            "2020": LoincMapping("4544-3", "Hematocrit [Volume Fraction] of Blood by Automated count"),
            "2021": LoincMapping("785-6", "MCH [Entitic mass] by Automated count"),
            "2022": LoincMapping("786-4", "MCHC [Mass/volume] by Automated count"),
            "2023": LoincMapping("21000-5", "Erythrocyte distribution width [Entitic volume] by Automated count"),
            "2024": LoincMapping("788-0", "Erythrocyte distribution width [Ratio] by Automated count"),
            # Platelets
            "2025": LoincMapping("777-3", "Platelets [#/volume] in Blood by Automated count"),
            "2026": LoincMapping("32623-1", "Platelet mean volume [Entitic volume] in Blood by Automated count"),
            "2027": LoincMapping("61928-3", "Plateletcrit [Volume Fraction] in Blood"),
            "2028": LoincMapping("32207-3", "Platelet distribution width [Entitic volume] in Blood by Automated count"),
            "2029": LoincMapping("51632-0", "Platelets Large [Ratio] in Blood"),
            "2030": LoincMapping("74464-9", "Platelets Large [#/volume] in Blood"),
            # CRP
            "2031": LoincMapping("1988-5", "C reactive protein [Mass/volume] in Serum or Plasma"),
            "2032": LoincMapping("30522-7", "C reactive protein [Mass/volume] in Serum or Plasma by High sensitivity method"),
        }

    @property
    def panel_mappings(self) -> dict[str, str]:
        """
        LOINC panel codes → BF-6900 OBR-4 service type codes.
        The BF-6900 uses a single "CountResults" service (1001) for all CBC/DIFF/CRP.
        """
        return {
            "58410-2": "1001",   # CBC panel
            "69738-3": "1001",   # CBC w/ Differential
            "57021-8": "1001",   # CBC w/ Differential panel (alternate)
        }

    def should_skip_obx(self, segment) -> bool:
        """
        Skip non-result OBX segments:
        - ED type: histograms/scattergrams (2101, 2102, 2033, 2034)
        - IS type: analysis mode metadata (2001–2005)
        """
        value_type = hl7_to_str(segment, 2)
        if value_type == "ED":
            return True
        if value_type == "IS":
            return True
        return False

    def extract_patient_id(self, pid_segment) -> str | None:
        """
        BF-6900 PID-3: Case number (single value, no type code).
        Example: PID|1||7393670||Liu Jia|||F|...|25^Y
        """
        return hl7_to_str(pid_segment, 3) or None

    def build_worklist_response(
        self, orders: list[ORUData], original_control_id: str
    ) -> str | None:
        """
        Build a CellQuant BF-6900 specific ORR^O02 worklist response.

        The BF-6900 expects:
        - MSH with ORR^O02, Processing ID P^S, HL7 v2.3.1
        - MSA|AA|{control_id}||||0
        - Per order: PID, PV1, ORC(AF), OBR, OBX (analysis settings)

        Uses hl7.parse() to validate the constructed message structure.
        """
        now = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")

        segments = []

        # MSH
        segments.append(
            f"MSH|^~\\&|LIS||||{now}||ORR^O02"
            f"|{original_control_id}|P^S|2.3.1||||||UTF-8"
        )

        # MSA
        segments.append(f"MSA|AA|{original_control_id}||||0")

        for order in orders:
            patient_id = order.patient_id or ""
            patient_name = order.patient_name or ""
            gender = order.gender or ""
            sample_id = order.sample_id or ""
            department = order.department or ""
            collect_time = order.collect_time or ""
            tests = order.tests

            # PID — BF-6900 format: PID|1||{case_number}||{name}|||{gender}
            segments.append(
                f"PID|1||{patient_id}||{patient_name}|||{gender}"
            )

            # PV1
            segments.append(f"PV1|1||{department}")

            # ORC — AF = Affirm/Fill (order acknowledged), barcode in ORC-2
            segments.append(f"ORC|AF|{sample_id}|||")

            # OBR — service type from tests or default to 1001^CountResults
            service_code = "1001^CountResults"
            if tests:
                test = tests[0]
                code = test.code or "1001"
                display = test.display or "CountResults"
                service_code = f"{code}^{display}"

            segments.append(
                f"OBR|1|{sample_id}||{service_code}"
                f"||{collect_time}||||||||{collect_time}"
            )

            # OBX — analysis settings (defaults for CBC+DIFF)
            # MODE: 0=Whole blood, 1=Trace whole blood, 2=Pre-dilution
            segments.append("OBX|1|IS|2001^MODE||0||||||||")
            # MODE_EX: 0=CBC, 1=CBC+DIFF, 2=CBC+DIFF+CRP, 3=CRP
            segments.append("OBX|2|IS|2002^MODE_EX||1||||||||")
            # Ref: 0=Normal, 1=Male, 2=Female, 3=Child, 4=Newborn
            ref_group = "0"
            if gender == "M":
                ref_group = "1"
            elif gender == "F":
                ref_group = "2"
            segments.append(f"OBX|3|IS|2003^Ref||{ref_group}||||||||")
            # Note
            segments.append("OBX|4|ST|2004^Note||||||||||")

        raw = "\r".join(segments)
        # Parse to validate HL7 structure, then serialize back
        message = hl7.parse(raw)
        return str(message)


registry.register(CellQuantBF6900Profile)
