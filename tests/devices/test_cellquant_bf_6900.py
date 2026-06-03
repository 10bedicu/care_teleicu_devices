"""Unit tests for CellQuant BF-6900 device profile."""

import unittest

import hl7

from lab_analyzer_device.hl7.devices.cellquant_bf_6900 import CellQuantBF6900Profile
from lab_analyzer_device.hl7.builder import OrderedTest
from lab_analyzer_device.hl7.extractor import ORUData

# ORU^R01 with numeric OBX-3 codes (2006-2032)
CELLQUANT_BF6900_ORU = (
    "MSH|^~\\&|BF-6900||||20250115120000||ORU^R01|BF001|P|2.3.1||||||UTF-8\r"
    "PID|1||PAT004||Sharma^Priya|||F\r"
    "OBR|1|ORD004|000321|1001^CountResults|||20250115120000\r"
    "OBX|1|NM|2006^WBC||6.8|10^3/uL|4.0-10.0|N|||F\r"
    "OBX|2|NM|2017^RBC||4.2|10^6/uL|3.8-5.8|N|||F\r"
    "OBX|3|NM|2018^HGB||12.5|g/dL|11.5-16.0|N|||F\r"
    "OBX|4|NM|2025^PLT||220|10^3/uL|150-400|N|||F\r"
    "OBX|5|ED|HIST^WBC Histogram||BASE64DATA\r"
    "OBX|6|IS|2001^MODE||0\r"
    "OBX|7|NM|2031^CRP||3.5|mg/L|0-5|N|||F\r"
)


class TestProperties(unittest.TestCase):

    def setUp(self):
        self.profile = CellQuantBF6900Profile()

    def test_device_type(self):
        self.assertEqual(self.profile.device_type, "cellquant_bf_6900")

    def test_communication_mode(self):
        self.assertEqual(self.profile.communication_mode, "host_query")

    def test_supports_query_orders(self):
        self.assertTrue(self.profile.supports_query_orders)

    def test_hl7_version(self):
        self.assertEqual(self.profile.hl7_version, "2.3.1")


class TestCodeMappings(unittest.TestCase):

    def setUp(self):
        self.profile = CellQuantBF6900Profile()

    def test_code_2006_wbc(self):
        system, code, display = self.profile.resolve_code("2006", "")
        self.assertEqual(system, "http://loinc.org")
        self.assertEqual(code, "6690-2")

    def test_code_2017_rbc(self):
        system, code, display = self.profile.resolve_code("2017", "")
        self.assertEqual(code, "789-8")

    def test_code_2018_hgb(self):
        system, code, display = self.profile.resolve_code("2018", "")
        self.assertEqual(code, "718-7")

    def test_code_2025_plt(self):
        system, code, display = self.profile.resolve_code("2025", "")
        self.assertEqual(code, "777-3")

    def test_all_codes_2006_to_2032_mapped(self):
        for i in range(2006, 2033):
            system, code, display = self.profile.resolve_code(str(i), "")
            self.assertEqual(system, "http://loinc.org", f"Code '{i}' should map to LOINC")

    def test_unknown_code(self):
        system, code, display = self.profile.resolve_code("9999", "")
        self.assertEqual(system, "local")
        self.assertEqual(code, "9999")


class TestPanelMappings(unittest.TestCase):

    def setUp(self):
        self.profile = CellQuantBF6900Profile()

    def test_cbc_maps_to_count_results(self):
        panels = self.profile.panel_mappings
        self.assertEqual(panels["58410-2"], "1001")

    def test_all_panels_map_to_1001(self):
        """All panel codes resolve to the single CountResults (1001) profile."""
        panels = self.profile.panel_mappings
        for key, value in panels.items():
            self.assertEqual(value, "1001", f"Panel {key} should map to 1001")

    def test_validate_tests_cbc(self):
        tests = [OrderedTest(code="58410-2", display="CBC")]
        resolved = self.profile.validate_tests(tests)
        self.assertEqual(len(resolved), 1)
        self.assertEqual(resolved[0].code, "1001")

    def test_validate_tests_invalid(self):
        tests = [OrderedTest(code="INVALID", display="Bad")]
        with self.assertRaises(ValueError):
            self.profile.validate_tests(tests)


class TestExtraction(unittest.TestCase):

    def setUp(self):
        self.profile = CellQuantBF6900Profile()

    def test_extract_oru(self):
        msg = hl7.parse(CELLQUANT_BF6900_ORU)
        data = self.profile.extract_result_data(msg)
        # 4 NM + 1 CRP (NM) = 5, skipping ED and IS
        self.assertEqual(len(data.observations), 5)

    def test_skip_ed_and_is(self):
        msg = hl7.parse(CELLQUANT_BF6900_ORU)
        data = self.profile.extract_result_data(msg)
        value_types = [obs.value_type for obs in data.observations]
        self.assertNotIn("ED", value_types)
        self.assertNotIn("IS", value_types)

    def test_patient_id(self):
        msg = hl7.parse(CELLQUANT_BF6900_ORU)
        data = self.profile.extract_result_data(msg)
        self.assertEqual(data.patient_id, "PAT004")

    def test_observation_codes_resolved_to_loinc(self):
        """Raw device codes (2006, 2017, etc.) are resolved to LOINC."""
        msg = hl7.parse(CELLQUANT_BF6900_ORU)
        data = self.profile.extract_result_data(msg)
        codes = [obs.code for obs in data.observations]
        self.assertIn("6690-2", codes)  # 2006 → WBC
        self.assertIn("789-8", codes)  # 2017 → RBC
        self.assertIn("777-3", codes)  # 2025 → PLT


class TestWorklistResponse(unittest.TestCase):

    def setUp(self):
        self.profile = CellQuantBF6900Profile()

    def test_builds_orr_response(self):
        orders = [
            {
                "sample_id": "123",
                "patient_id": "P1",
                "patient_name": "Test",
                "gender": "M",
                "department": "ICU",
                "collect_time": "20250115",
                "tests": [],
            }
        ]
        result = self.profile.build_worklist_response([ORUData(**o) for o in orders], "CTRL001")
        self.assertIsInstance(result, str)
        self.assertIn("ORR^O02", result)
        self.assertIn("MSA|AA|CTRL001", result)
        self.assertIn("ORC|AF|123", result)

    def test_includes_pid_segment(self):
        orders = [
            {
                "sample_id": "456",
                "patient_id": "PAT_ID",
                "patient_name": "Doe^John",
                "gender": "F",
                "department": "",
                "collect_time": "",
                "tests": [],
            }
        ]
        result = self.profile.build_worklist_response([ORUData(**o) for o in orders], "CTRL002")
        self.assertIn("PID|", result)
        self.assertIn("PAT_ID", result)

    def test_empty_orders_still_builds_response(self):
        """CellQuant builds ORR^O02 even with no orders (MSH + MSA only)."""
        result = self.profile.build_worklist_response([], "CTRL003")
        self.assertIsInstance(result, str)
        self.assertIn("ORR^O02", result)
        self.assertIn("MSA|AA|CTRL003", result)
