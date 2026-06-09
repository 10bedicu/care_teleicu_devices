"""Unit tests for Generic device profile."""

import unittest

import hl7

from lab_analyzer_device.hl7.devices.generic import GenericDeviceProfile

# Standard HL7 2.3 ORU^R01 with LOINC-coded results
GENERIC_ORU = (
    "MSH|^~\\&|ANALYZER||||20250115120000||ORU^R01|GEN001|P|2.3\r"
    "PID|1||PAT005^^^^MR||Patel^Amit||19800101|M\r"
    "OBR|1|ORD005|FILL005|CBC^Complete Blood Count^LN|||20250115\r"
    "OBX|1|NM|6690-2^WBC^LN||7.0|10^3/uL|4-10|N|||F\r"
    "OBX|2|NM|789-8^RBC^LN||5.0|10^6/uL|4-6|N|||F\r"
    "OBX|3|NM|718-7^HGB^LN||15.0|g/dL|12-17|N|||F\r"
    "OBX|4|ED|CURVE^WBC Curve^LN||BASE64\r"
)

# ORU with ORC segment containing ordering physician
GENERIC_ORU_WITH_ORC = (
    "MSH|^~\\&|ANALYZER||||20250115120000||ORU^R01|GEN002|P|2.3\r"
    "PID|1||PAT006^^^^MR||Singh^Deepak||19950615|M\r"
    "ORC|RE|ORD006|FILL006|||||||||DOC002^Kumar^Anita\r"
    "OBR|1|ORD006|FILL006|CBC^Complete Blood Count^LN|||20250115\r"
    "OBX|1|NM|6690-2^WBC^LN||8.5|10^3/uL|4-10|N|||F\r"
    "OBX|2|NM|789-8^RBC^LN||4.8|10^6/uL|4-6|N|||F\r"
)


class TestProperties(unittest.TestCase):

    def setUp(self):
        self.profile = GenericDeviceProfile()

    def test_device_type(self):
        self.assertEqual(self.profile.device_type, "generic")

    def test_communication_mode(self):
        self.assertEqual(self.profile.communication_mode, "download")

    def test_does_not_support_query_orders(self):
        self.assertFalse(self.profile.supports_query_orders)

    def test_worklist_response_returns_none(self):
        result = self.profile.build_worklist_response([], "CTRL")
        self.assertIsNone(result)

    def test_no_panel_mappings(self):
        self.assertEqual(self.profile.panel_mappings, {})


class TestCodeMappings(unittest.TestCase):

    def setUp(self):
        self.profile = GenericDeviceProfile()

    def test_wbc_mapping(self):
        system, code, display = self.profile.resolve_code("WBC", "")
        self.assertEqual(system, "http://loinc.org")
        self.assertEqual(code, "6690-2")

    def test_rbc_mapping(self):
        system, code, display = self.profile.resolve_code("RBC", "")
        self.assertEqual(system, "http://loinc.org")
        self.assertEqual(code, "789-8")

    def test_hgb_mapping(self):
        system, code, display = self.profile.resolve_code("HGB", "")
        self.assertEqual(system, "http://loinc.org")
        self.assertEqual(code, "718-7")

    def test_unknown_code(self):
        system, code, display = self.profile.resolve_code("ZZZZZ", "")
        self.assertEqual(system, "local")
        self.assertEqual(code, "ZZZZZ")


class TestExtraction(unittest.TestCase):

    def setUp(self):
        self.profile = GenericDeviceProfile()

    def test_extract_basic(self):
        msg = hl7.parse(GENERIC_ORU)
        data = self.profile.extract_result_data(msg)
        self.assertEqual(data.patient_id, "PAT005")
        self.assertEqual(data.placer_order_number, "ORD005")
        self.assertEqual(data.filler_order_number, "FILL005")
        # 3 NM + 1 ED (skipped) = 3
        self.assertEqual(len(data.observations), 3)

    def test_extract_with_orc(self):
        msg = hl7.parse(GENERIC_ORU_WITH_ORC)
        data = self.profile.extract_result_data(msg)
        self.assertEqual(data.patient_id, "PAT006")
        self.assertIsNotNone(data.ordering_physician)
        self.assertEqual(data.ordering_physician.id, "DOC002")
        self.assertEqual(data.ordering_physician.family_name, "Kumar")

    def test_observation_values(self):
        msg = hl7.parse(GENERIC_ORU)
        data = self.profile.extract_result_data(msg)
        wbc = data.observations[0]
        self.assertEqual(wbc.value, "7.0")

    def test_observation_units(self):
        msg = hl7.parse(GENERIC_ORU)
        data = self.profile.extract_result_data(msg)
        hgb = next(obs for obs in data.observations if obs.code == "718-7")
        self.assertEqual(hgb.units, "g/dL")
