"""Unit tests for Horiba Yumizen H500 device profile."""

import unittest

import hl7

from lab_analyzer_device.hl7.devices.horiba_yumizen_h500 import HoribaYumizenH500Profile

# OUL^R22 with LOINC-coded CBC results and SPM segment
YUMIZEN_H500_OUL = (
    "MSH|^~\\&|H500/H500E^SIM00001^4.0.0.0|HORIBA_MEDICAL|||20250115120000||OUL^R22^OUL_R22|MSG001|P|2.5||||||UNICODE UTF-8\r"
    "PID|1||PAT001^^^^PI||Doe^John||19900101\r"
    "SPM|1|SPEC001||WB||||||P\r"
    "ORC|NW|ORD001||||||||||DOC001^Smith^Jane\r"
    "OBR|1|ORD001||CBC\r"
    "OBX|1|NM|789-8^RBC^LN||4.85|1E06/mm3^1E06/mm3|4.20 - 6.00^REFERENCE_RANGE|N|||F||20250115120000\r"
    "OBX|2|NM|718-7^HGB^LN||14.2|g/dL^g/dL|12.0 - 17.5^REFERENCE_RANGE|N|||F||20250115120000\r"
    "OBX|3|NM|4544-3^HCT^LN||42.1|%^%|36.0 - 50.0^REFERENCE_RANGE|N|||F||20250115120000\r"
    "OBX|4|NM|787-2^MCV^LN||86.8|fL^fL|80.0 - 100.0^REFERENCE_RANGE|N|||F||20250115120000\r"
    "OBX|5|NM|777-3^PLT^LN||245|1E03/mm3^1E03/mm3|150 - 400^REFERENCE_RANGE|N|||F||20250115120000\r"
    "OBX|6|ED|HISTOGRAM^Histogram^LN||BASE64IMAGEDATA\r"
    "OBX|7|NM|6690-2^WBC^LN||7.2|1E03/mm3^1E03/mm3|4.0 - 10.0^REFERENCE_RANGE|N~|||F||20250115120000\r"
)

# OUL with "Dosage category" OBX (should be skipped)
YUMIZEN_H500_OUL_WITH_DOSAGE = (
    "MSH|^~\\&|H500/H500E^SIM00001^4.0.0.0|HORIBA_MEDICAL|||20250115120000||OUL^R22^OUL_R22|MSG002|P|2.5||||||UNICODE UTF-8\r"
    "PID|1||PAT002^^^^PI||Smith^Alice||19850515\r"
    "SPM|1|SPEC002||WB||||||P\r"
    "OBR|1|ORD002||DIF\r"
    "OBX|1|NM|731-0^LYM#^LN||2.1|1E03/mm3^1E03/mm3|1.0 - 3.5^REFERENCE_RANGE|N|||F\r"
    "OBX|2|ST|Dosage category^Dosage category^LN||NORMAL\r"
    "OBX|3|NM|751-8^NEU#^LN||4.1|1E03/mm3^1E03/mm3|1.5 - 7.0^REFERENCE_RANGE|N|||F\r"
)


class TestProperties(unittest.TestCase):

    def setUp(self):
        self.profile = HoribaYumizenH500Profile()

    def test_device_type(self):
        self.assertEqual(self.profile.device_type, "horiba_yumizen_h500")

    def test_display_name(self):
        self.assertIn("Yumizen H500", self.profile.display_name)

    def test_hl7_version(self):
        self.assertEqual(self.profile.hl7_version, "2.5")

    def test_communication_mode(self):
        self.assertEqual(self.profile.communication_mode, "download")

    def test_result_message_type(self):
        self.assertEqual(self.profile.result_message_type, "OUL^R22^OUL_R22")

    def test_order_message_type(self):
        self.assertEqual(self.profile.order_message_type, "OML^O33^OML_O33")

    def test_does_not_support_query_orders(self):
        self.assertFalse(self.profile.supports_query_orders)


class TestCodeMappings(unittest.TestCase):

    def setUp(self):
        self.profile = HoribaYumizenH500Profile()

    def test_rbc_mapping(self):
        system, code, display = self.profile.resolve_code("RBC", "")
        self.assertEqual(system, "http://loinc.org")
        self.assertEqual(code, "789-8")

    def test_wbc_mapping(self):
        system, code, display = self.profile.resolve_code("WBC", "")
        self.assertEqual(system, "http://loinc.org")
        self.assertEqual(code, "6690-2")

    def test_loinc_passthrough(self):
        system, code, display = self.profile.resolve_code("789-8", "LN")
        self.assertEqual(system, "http://loinc.org")
        self.assertEqual(code, "789-8")

    def test_unknown_code(self):
        system, code, display = self.profile.resolve_code("UNKNOWN", "")
        self.assertEqual(system, "local")
        self.assertEqual(code, "UNKNOWN")


class TestPanelMappings(unittest.TestCase):

    def setUp(self):
        self.profile = HoribaYumizenH500Profile()

    def test_cbc_loinc_maps_to_cbc(self):
        panels = self.profile.panel_mappings
        self.assertEqual(panels["58410-2"], "CBC")

    def test_dif_loinc_maps_to_dif(self):
        panels = self.profile.panel_mappings
        self.assertEqual(panels["69738-3"], "DIF")

    def test_snomed_cbc(self):
        panels = self.profile.panel_mappings
        self.assertEqual(panels["26604007"], "CBC")


class TestExtraction(unittest.TestCase):

    def setUp(self):
        self.profile = HoribaYumizenH500Profile()

    def test_extract_basic_oul(self):
        msg = hl7.parse(YUMIZEN_H500_OUL)
        data = self.profile.extract_result_data(msg)
        self.assertEqual(data.patient_id, "PAT001")
        self.assertEqual(data.specimen_id, "SPEC001")
        self.assertEqual(data.placer_order_number, "ORD001")
        # Should skip ED histogram — 6 NM results remain
        self.assertEqual(len(data.observations), 6)

    def test_skip_dosage_category(self):
        msg = hl7.parse(YUMIZEN_H500_OUL_WITH_DOSAGE)
        data = self.profile.extract_result_data(msg)
        # Should skip "Dosage category" ST OBX — 2 NM results remain
        self.assertEqual(len(data.observations), 2)

    def test_specimen_from_spm(self):
        msg = hl7.parse(YUMIZEN_H500_OUL)
        data = self.profile.extract_result_data(msg)
        self.assertEqual(data.specimen_id, "SPEC001")

    def test_ordering_physician_from_orc(self):
        msg = hl7.parse(YUMIZEN_H500_OUL)
        data = self.profile.extract_result_data(msg)
        self.assertIsNotNone(data.ordering_physician)
        self.assertEqual(data.ordering_physician.id, "DOC001")
        self.assertEqual(data.ordering_physician.family_name, "Smith")
