"""Unit tests for ADX AutoChem 200 device profile."""

import unittest

import hl7

from lab_analyzer_device.hl7.devices.adx_autochem_200 import AdxAutoChem200Profile
from lab_analyzer_device.hl7.builder import OrderedTest
from lab_analyzer_device.hl7.extractor import ORUData

# ORU^R01 with integer test ID codes in OBX-3 (e.g. "7^BIL T")
ADX_AUTOCHEM_200_ORU = (
    "MSH|^~\\&|ADX-CHEM-200||||20250115120000||ORU^R01|CHEM001|P|2.3.1||||||UNICODE\r"
    "PID|1||PAT003||Kumar^Ravi||19750320\r"
    "OBR|1|ORD003|000789|BIOCHEM^Biochemistry|||20250115120000\r"
    "OBX|1|NM|7^BIL T||1.2|mg/dL|0.1-1.2|N|||F\r"
    "OBX|2|NM|6^BIL D||0.3|mg/dL|0.0-0.4|N|||F\r"
    "OBX|3|NM|3^ALT||25|U/L|0-40|N|||F\r"
    "OBX|4|NM|5^AST||22|U/L|0-40|N|||F\r"
    "OBX|5|NM|10^GLU||95|mg/dL|70-110|N|||F\r"
    "OBX|6|ST|99^NOTE||Sample hemolyzed\r"
)


class TestProperties(unittest.TestCase):

    def setUp(self):
        self.profile = AdxAutoChem200Profile()

    def test_device_type(self):
        self.assertEqual(self.profile.device_type, "adx_autochem_200")

    def test_display_name(self):
        self.assertIn("ADX AutoChem 200", self.profile.display_name)

    def test_hl7_version(self):
        self.assertEqual(self.profile.hl7_version, "2.3.1")

    def test_communication_mode(self):
        self.assertEqual(self.profile.communication_mode, "host_query")

    def test_supports_query_orders(self):
        self.assertTrue(self.profile.supports_query_orders)

    def test_sending_application(self):
        self.assertEqual(self.profile.sending_application, "LIS")


class TestCodeMappings(unittest.TestCase):

    def setUp(self):
        self.profile = AdxAutoChem200Profile()

    def test_has_28_mappings(self):
        self.assertEqual(len(self.profile.code_mappings), 28)

    def test_code_1_albumin(self):
        system, code, display = self.profile.resolve_code("1", "")
        self.assertEqual(system, "http://loinc.org")
        self.assertEqual(code, "1751-7")
        self.assertIn("Albumin", display)

    def test_code_7_bilirubin_total(self):
        system, code, display = self.profile.resolve_code("7", "")
        self.assertEqual(system, "http://loinc.org")
        self.assertEqual(code, "1975-2")
        self.assertIn("Bilirubin.total", display)

    def test_code_6_bilirubin_direct(self):
        system, code, display = self.profile.resolve_code("6", "")
        self.assertEqual(code, "1968-7")

    def test_code_3_alt_sgpt(self):
        system, code, display = self.profile.resolve_code("3", "")
        self.assertEqual(code, "1742-6")

    def test_code_5_ast_sgot(self):
        system, code, display = self.profile.resolve_code("5", "")
        self.assertEqual(code, "1920-8")

    def test_code_10_glucose(self):
        system, code, display = self.profile.resolve_code("10", "")
        self.assertEqual(code, "2345-7")

    def test_code_14_urea(self):
        system, code, display = self.profile.resolve_code("14", "")
        self.assertEqual(code, "3094-0")

    def test_code_22_creatinine(self):
        system, code, display = self.profile.resolve_code("22", "")
        self.assertEqual(code, "2160-0")

    def test_code_25_ggt(self):
        system, code, display = self.profile.resolve_code("25", "")
        self.assertEqual(code, "2324-2")

    def test_code_27_hba1c(self):
        system, code, display = self.profile.resolve_code("27", "")
        self.assertEqual(code, "4548-4")

    def test_all_codes_1_to_28_mapped(self):
        for i in range(1, 29):
            system, code, display = self.profile.resolve_code(str(i), "")
            self.assertEqual(system, "http://loinc.org", f"Code '{i}' should map to LOINC")
            self.assertNotEqual(code, str(i), f"Code '{i}' should resolve to a LOINC code")

    def test_unknown_code_returns_local(self):
        system, code, display = self.profile.resolve_code("99", "")
        self.assertEqual(system, "local")
        self.assertEqual(code, "99")


class TestPanelMappings(unittest.TestCase):

    def setUp(self):
        self.profile = AdxAutoChem200Profile()

    def test_lft_panel_expansion(self):
        """LFT (26958001) expands to individual test IDs."""
        panels = self.profile.panel_mappings
        lft = panels["26958001"]
        self.assertIsInstance(lft, list)
        # Should include Bilirubin Total (7), Bilirubin Direct (6), ALT (3), AST (5), ALP (2)
        self.assertIn("7", lft)
        self.assertIn("6", lft)
        self.assertIn("3", lft)
        self.assertIn("5", lft)
        self.assertIn("2", lft)
        self.assertIn("25", lft)  # GGT
        self.assertIn("12", lft)  # Total Protein
        self.assertIn("1", lft)  # Albumin

    def test_kft_panel_expansion(self):
        """KFT (54610007) expands to renal function test IDs."""
        panels = self.profile.panel_mappings
        kft = panels["54610007"]
        self.assertIsInstance(kft, list)
        self.assertIn("14", kft)  # Urea
        self.assertIn("22", kft)  # Creatinine
        self.assertIn("15", kft)  # Potassium
        self.assertIn("16", kft)  # Sodium

    def test_cmp_panel_expansion(self):
        """CMP (24320-4) includes both LFT and KFT tests."""
        panels = self.profile.panel_mappings
        cmp = panels["24320-4"]
        self.assertIsInstance(cmp, list)
        self.assertGreater(len(cmp), 10)

    def test_bmp_panel(self):
        panels = self.profile.panel_mappings
        bmp = panels["24321-2"]
        self.assertIsInstance(bmp, list)
        self.assertIn("10", bmp)  # Glucose
        self.assertIn("14", bmp)  # Urea
        self.assertIn("22", bmp)  # Creatinine

    def test_lipid_panel(self):
        panels = self.profile.panel_mappings
        lipid = panels["24331-1"]
        self.assertIsInstance(lipid, list)
        self.assertIn("9", lipid)  # Cholesterol
        self.assertIn("11", lipid)  # Triglyceride
        self.assertIn("26", lipid)  # HDL

    def test_validate_tests_lft(self):
        """validate_tests resolves LFT panel to individual test IDs."""
        tests = [OrderedTest(code="26958001", display="LFT")]
        resolved = self.profile.validate_tests(tests)
        # Each test ID in the LFT list becomes a separate OrderedTest
        self.assertEqual(len(resolved), 8)
        codes = [t.code for t in resolved]
        self.assertIn("7", codes)
        self.assertIn("6", codes)
        self.assertIn("3", codes)

    def test_validate_tests_invalid_code(self):
        tests = [OrderedTest(code="INVALID", display="Bad")]
        with self.assertRaises(ValueError):
            self.profile.validate_tests(tests)


class TestObservationIdExtraction(unittest.TestCase):

    def setUp(self):
        self.profile = AdxAutoChem200Profile()

    def test_extract_id_and_name(self):
        """OBX-3 format: <test_id>^<test_name> → returns (id, name)."""
        msg = hl7.parse(ADX_AUTOCHEM_200_ORU)
        # Get first OBX segment
        obx = None
        for segment in msg:
            if str(segment[0][0]) == "OBX":
                obx = segment
                break
        code, display = self.profile.extract_observation_id(obx)
        self.assertEqual(code, "7")
        self.assertEqual(display, "BIL T")

    def test_extract_glucose(self):
        """Verify GLU OBX extraction."""
        msg = hl7.parse(ADX_AUTOCHEM_200_ORU)
        obx_segments = [seg for seg in msg if str(seg[0][0]) == "OBX"]
        # OBX|5|NM|10^GLU|| → code="10", display="GLU"
        code, display = self.profile.extract_observation_id(obx_segments[4])
        self.assertEqual(code, "10")
        self.assertEqual(display, "GLU")


class TestSkipObx(unittest.TestCase):

    def setUp(self):
        self.profile = AdxAutoChem200Profile()

    def test_keeps_nm_type(self):
        msg = hl7.parse(ADX_AUTOCHEM_200_ORU)
        obx_segments = [seg for seg in msg if str(seg[0][0]) == "OBX"]
        # First OBX is NM — should not be skipped
        self.assertFalse(self.profile.should_skip_obx(obx_segments[0]))

    def test_keeps_st_type(self):
        """ADX AutoChem 200 keeps ST results (notes/flags)."""
        msg = hl7.parse(ADX_AUTOCHEM_200_ORU)
        obx_segments = [seg for seg in msg if str(seg[0][0]) == "OBX"]
        # Last OBX is ST type — should NOT be skipped
        self.assertFalse(self.profile.should_skip_obx(obx_segments[-1]))


class TestExtraction(unittest.TestCase):

    def setUp(self):
        self.profile = AdxAutoChem200Profile()

    def test_extract_oru(self):
        msg = hl7.parse(ADX_AUTOCHEM_200_ORU)
        data = self.profile.extract_result_data(msg)
        self.assertEqual(data.patient_id, "PAT003")
        # 5 NM + 1 ST = 6 observations (ADX keeps both NM and ST)
        self.assertEqual(len(data.observations), 6)

    def test_observation_codes_resolved_to_loinc(self):
        """Extracted observation codes are resolved to LOINC via code_mappings."""
        msg = hl7.parse(ADX_AUTOCHEM_200_ORU)
        data = self.profile.extract_result_data(msg)
        codes = [obs.code for obs in data.observations]
        # Raw codes (7, 6, 3, 5, 10) resolve to LOINC
        self.assertIn("1975-2", codes)  # 7 → BIL T
        self.assertIn("1968-7", codes)  # 6 → BIL D
        self.assertIn("1742-6", codes)  # 3 → ALT
        self.assertIn("1920-8", codes)  # 5 → AST
        self.assertIn("2345-7", codes)  # 10 → GLU
        # Code 99 is unknown — stays as-is with system="local"
        self.assertIn("99", codes)

    def test_observation_values(self):
        msg = hl7.parse(ADX_AUTOCHEM_200_ORU)
        data = self.profile.extract_result_data(msg)
        # BIL T (code 7) resolves to LOINC 1975-2
        bil_t = next(obs for obs in data.observations if obs.code == "1975-2")
        self.assertEqual(bil_t.value, "1.2")
        self.assertEqual(bil_t.units, "mg/dL")

    def test_observation_reference_range(self):
        msg = hl7.parse(ADX_AUTOCHEM_200_ORU)
        data = self.profile.extract_result_data(msg)
        # GLU (code 10) resolves to LOINC 2345-7
        glu = next(obs for obs in data.observations if obs.code == "2345-7")
        self.assertEqual(glu.reference_range, "70-110")


class TestWorklistResponse(unittest.TestCase):

    def setUp(self):
        self.profile = AdxAutoChem200Profile()

    def test_returns_two_messages(self):
        orders = [
            {
                "sample_id": "BAR001",
                "patient_id": "P1",
                "patient_name": "Test User",
                "date_of_birth": "19900101000000",
                "gender": "M",
                "sample_type": "Serum",
                "tests": [{"code": "7", "display": "BIL T", "system": "local"}],
            }
        ]
        result = self.profile.build_worklist_response([ORUData(**o) for o in orders], "CTRL001")
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 2)

    def test_first_message_is_qck(self):
        orders = [
            {
                "sample_id": "BAR001",
                "patient_id": "P1",
                "patient_name": "Test",
                "date_of_birth": "",
                "gender": "M",
                "sample_type": "",
                "tests": [{"code": "7"}],
            }
        ]
        result = self.profile.build_worklist_response([ORUData(**o) for o in orders], "CTRL001")
        self.assertIn("QCK^Q02", result[0])
        self.assertIn("MSA|AA|CTRL001", result[0])
        self.assertIn("ERR|0", result[0])

    def test_second_message_is_dsr(self):
        orders = [
            {
                "sample_id": "BAR001",
                "patient_id": "P1",
                "patient_name": "Test User",
                "date_of_birth": "19900101",
                "gender": "F",
                "sample_type": "Serum",
                "tests": [
                    {"code": "7", "display": "BIL T", "system": "local"},
                    {"code": "6", "display": "BIL D", "system": "local"},
                ],
            }
        ]
        result = self.profile.build_worklist_response([ORUData(**o) for o in orders], "CTRL002")
        dsr = result[1]
        self.assertIn("DSR^Q03", dsr)
        self.assertIn("QAK|CTRL002|OK", dsr)
        # Patient name at DSP|3|
        self.assertIn("Test User", dsr)
        # Gender at DSP|5|
        self.assertIn("F", dsr)
        # Test orders as "TestID^^^"
        self.assertIn("7^^^", dsr)
        self.assertIn("6^^^", dsr)

    def test_dsr_contains_sample_id(self):
        orders = [
            {
                "sample_id": "SAMPLE123",
                "patient_id": "P1",
                "patient_name": "Patient",
                "date_of_birth": "",
                "gender": "",
                "sample_type": "",
                "tests": [{"code": "10"}],
            }
        ]
        result = self.profile.build_worklist_response([ORUData(**o) for o in orders], "CTRL003")
        dsr = result[1]
        # Sample ID appears at DSP|21| and DSP|22|
        self.assertIn("SAMPLE123", dsr)

    def test_returns_none_for_empty_orders(self):
        result = self.profile.build_worklist_response([], "CTRL004")
        self.assertIsNone(result)

    def test_multiple_orders(self):
        orders = [
            {
                "sample_id": "S1",
                "patient_id": "P1",
                "patient_name": "Patient One",
                "date_of_birth": "",
                "gender": "M",
                "sample_type": "",
                "tests": [{"code": "1"}],
            },
            {
                "sample_id": "S2",
                "patient_id": "P2",
                "patient_name": "Patient Two",
                "date_of_birth": "",
                "gender": "F",
                "sample_type": "",
                "tests": [{"code": "9"}],
            },
        ]
        result = self.profile.build_worklist_response([ORUData(**o) for o in orders], "CTRL005")
        dsr = result[1]
        self.assertIn("Patient One", dsr)
        self.assertIn("Patient Two", dsr)
        self.assertIn("1^^^", dsr)
        self.assertIn("9^^^", dsr)
