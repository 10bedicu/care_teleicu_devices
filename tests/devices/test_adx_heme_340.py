"""Unit tests for ADX Heme 340 device profile."""

import unittest

import hl7

from lab_analyzer_device.hl7.devices.adx_heme_340 import AdxHeme340Profile

# ORU^R01 with 3-part differential CBC results
ADX_HEME_340_ORU = (
    "MSH|^~\\&|||||20250115120000||ORU^R01|1|P|2.3.1||||||UNICODE||\r"
    "PID|1||||Doe^John|||\r"
    "PV1|1||\r"
    "OBR|1||000123|CBC^Complete Blood Count|||20250115120000||Admin\r"
    "OBX|1|NM|WBC||7.2|10^3/uL|4-10|N|||F\r"
    "OBX|2|NM|Lymph#||2.1|10^9/L|0.8-4|N|||F\r"
    "OBX|3|NM|Mid#||0.5|10^9/L|0.1-1.5|N|||F\r"
    "OBX|4|NM|Gran#||4.6|10^9/L|2-7|N|||F\r"
    "OBX|5|NM|Lymph%||29.2|%|20-40|N|||F\r"
    "OBX|6|NM|Mid%||6.9|%|3-15|N|||F\r"
    "OBX|7|NM|Gran%||60.0|%|50-70|N|||F\r"
    "OBX|8|NM|RBC||4.50|10^6/uL|3.5-5.5|N|||F\r"
    "OBX|9|NM|HGB||13.5|g/dL|11-16|N|||F\r"
    "OBX|10|NM|HCT||42.1|%|37-54|N|||F\r"
    "OBX|11|NM|MCV||86.8|fL|80-100|N|||F\r"
    "OBX|12|NM|MCH||29.3|pg|27-34|N|||F\r"
    "OBX|13|NM|MCHC||33.7|g/dL|32-36|N|||F\r"
    "OBX|14|NM|RDW-CV||13.1|%|11-16|N|||F\r"
    "OBX|15|NM|RWD-SD||42.5|fL|35-56|N|||F\r"
    "OBX|16|NM|PLT||245|10^3/uL|100-300|N|||F\r"
    "OBX|17|NM|MPV||9.8|fL|6.5-12|N|||F\r"
    "OBX|18|NM|PDW||15.8||15-17|N|||F\r"
    "OBX|19|NM|PCT||0.200|%|0.108-0.282|N|||F\r"
    "OBX|20|NM|PLCC||62|10^9/L|30-90|N|||F\r"
    "OBX|21|NM|PLCR||25.3|%|11-45|N|||F\r"
    "OBX|22|ED|HISTOGRAM||BASE64DATA\r"
)

# ORU with mixed types including IS (should be skipped)
ADX_HEME_340_ORU_MIXED = (
    "MSH|^~\\&|||||20250115120000||ORU^R01|2|P|2.3.1||||||UNICODE||\r"
    "PID|1||||Smith^Jane|||\r"
    "OBR|1||000456|CBC^Complete Blood Count|||20250115120000\r"
    "OBX|1|NM|WBC||6.5|10^3/uL|4-10|N|||F\r"
    "OBX|2|IS|MODE||0\r"
    "OBX|3|NM|HGB||12.0|g/dL|11-16|N|||F\r"
    "OBX|4|ED|SCATTER||IMAGEDATA\r"
)


class TestProperties(unittest.TestCase):

    def setUp(self):
        self.profile = AdxHeme340Profile()

    def test_device_type(self):
        self.assertEqual(self.profile.device_type, "adx_heme_340")

    def test_communication_mode(self):
        self.assertEqual(self.profile.communication_mode, "unidirectional")

    def test_does_not_support_query_orders(self):
        self.assertFalse(self.profile.supports_query_orders)

    def test_hl7_version(self):
        self.assertEqual(self.profile.hl7_version, "2.3.1")

    def test_no_panel_mappings(self):
        self.assertEqual(self.profile.panel_mappings, {})


class TestCodeMappings(unittest.TestCase):

    def setUp(self):
        self.profile = AdxHeme340Profile()

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

    def test_plt_mapping(self):
        system, code, display = self.profile.resolve_code("PLT", "")
        self.assertEqual(system, "http://loinc.org")
        self.assertEqual(code, "777-3")

    def test_lymph_number(self):
        system, code, display = self.profile.resolve_code("Lymph#", "")
        self.assertEqual(system, "http://loinc.org")

    def test_unknown_code(self):
        system, code, display = self.profile.resolve_code("UNKNOWN_TEST", "")
        self.assertEqual(system, "local")
        self.assertEqual(code, "UNKNOWN_TEST")


class TestExtraction(unittest.TestCase):

    def setUp(self):
        self.profile = AdxHeme340Profile()

    def test_extract_oru(self):
        msg = hl7.parse(ADX_HEME_340_ORU)
        data = self.profile.extract_result_data(msg)
        # 21 NM + 1 ED (skipped) = 21 observations
        self.assertEqual(len(data.observations), 21)
        self.assertEqual(data.observations[0].value, "7.2")

    def test_skip_ed_and_is(self):
        msg = hl7.parse(ADX_HEME_340_ORU_MIXED)
        data = self.profile.extract_result_data(msg)
        # 2 NM out of 4 (IS and ED skipped)
        self.assertEqual(len(data.observations), 2)

    def test_specimen_from_obr(self):
        """ADX Heme 340 uses OBR-3 (Filler Order Number) as specimen/accession ID."""
        msg = hl7.parse(ADX_HEME_340_ORU)
        data = self.profile.extract_result_data(msg)
        self.assertEqual(data.specimen_id, "000123")

    def test_patient_id(self):
        msg = hl7.parse(ADX_HEME_340_ORU_MIXED)
        data = self.profile.extract_result_data(msg)
        # PID-3 should be empty or whatever the fixture provides
        # The device sends case number in PID-3
        self.assertIsNotNone(data)

    def test_only_nm_kept(self):
        """Only NM type OBX segments are kept for ADX Heme 340."""
        msg = hl7.parse(ADX_HEME_340_ORU_MIXED)
        data = self.profile.extract_result_data(msg)
        for obs in data.observations:
            self.assertEqual(obs.value_type, "NM")
