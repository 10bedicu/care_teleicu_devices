"""Unit tests for ASTM record parsing and device profiles."""

import unittest

from lab_analyzer_device.astm import codec
from lab_analyzer_device.astm.devices.registry import registry
from lab_analyzer_device.astm.extractor import extract_astm_data


class TestASTMCodec(unittest.TestCase):
    def test_split_lines_handles_mixed_separators(self):
        raw = "H|\\^&\r\nP|1\rR|1|^^^WBC\nL|1|N"
        self.assertEqual(
            codec.split_lines(raw), ["H|\\^&", "P|1", "R|1|^^^WBC", "L|1|N"]
        )

    def test_detect_delimiters(self):
        self.assertEqual(
            codec.detect_delimiters("H|\\^&|||X"), ("|", "\\", "^", "&")
        )

    def test_field_and_component_access(self):
        parts = codec.fields("R|1|^^^WBC^Leukocytes|7.5")
        self.assertEqual(codec.field_at(parts, 0), "R")
        self.assertEqual(codec.field_at(parts, 99), "")
        self.assertEqual(codec.component_at(parts[2], 3), "WBC")
        self.assertEqual(codec.component_at(parts[2], 4), "Leukocytes")


class TestASTMRegistry(unittest.TestCase):
    def test_generic_profile_registered(self):
        profiles = registry.get_profiles()
        self.assertIn("generic", profiles)

    def test_unknown_type_falls_back_to_generic(self):
        profile = registry.get_profile("does_not_exist")
        self.assertEqual(profile.device_type, "generic")


class TestASTMExtraction(unittest.TestCase):
    def setUp(self):
        self.records = [
            r"H|\^&|||Analyzer|||||||P||E1394-97|20240101",
            "P|1||PID123||Doe^John||19800101|M",
            "O|1|SAMPLE001||^^^CBC|R||20240101120000",
            "R|1|^^^WBC|7.5|10*9/L|4.0-10.0|N||F||||20240101120500",
            "R|2|^^^HGB|14.2|g/dL|12.0-16.0|N||F",
            "L|1|N",
        ]

    def test_patient_fields(self):
        oru = extract_astm_data(self.records, "generic")
        self.assertEqual(oru.patient_id, "PID123")
        self.assertEqual(oru.patient_name, "John Doe")
        self.assertEqual(oru.date_of_birth, "19800101")
        self.assertEqual(oru.gender, "M")

    def test_order_specimen(self):
        oru = extract_astm_data(self.records, "generic")
        self.assertEqual(oru.specimen_id, "SAMPLE001")
        self.assertEqual(oru.sample_id, "SAMPLE001")

    def test_observations_mapped_to_loinc(self):
        oru = extract_astm_data(self.records, "generic")
        self.assertEqual(len(oru.observations), 2)
        wbc = oru.observations[0]
        # WBC -> LOINC 6690-2 via generic code mappings
        self.assertEqual(wbc.code, "6690-2")
        self.assertEqual(wbc.value, "7.5")
        self.assertEqual(wbc.units, "10*9/L")
        self.assertEqual(wbc.reference_range, "4.0-10.0")
        self.assertEqual(wbc.observation_datetime, "20240101120500")
        hgb = oru.observations[1]
        self.assertEqual(hgb.code, "718-7")

    def test_unknown_code_stays_local(self):
        records = [
            r"H|\^&|||Analyzer",
            "P|1||PID1||A^B",
            "R|1|^^^ZZZ|1.0|u|0-1|N||F",
            "L|1|N",
        ]
        oru = extract_astm_data(records, "generic")
        obs = oru.observations[0]
        self.assertEqual(obs.system, "local")
        self.assertEqual(obs.code, "ZZZ")


class TestASTMWorklistBuilder(unittest.TestCase):
    def test_build_worklist_response(self):
        from lab_analyzer_device.hl7.builder import OrderedTest
        from lab_analyzer_device.hl7.extractor import ORUData

        profile = registry.get_profile("generic")
        order = ORUData(
            patient_id="PID1",
            patient_name="John Doe",
            sample_id="S001",
            tests=[OrderedTest(code="CBC", display="CBC")],
        )
        response = profile.build_worklist_response([order], control_id="1")
        self.assertIsNotNone(response)
        lines = response.split("\n")
        self.assertTrue(lines[0].startswith("H|"))
        self.assertTrue(any(line.startswith("P|") for line in lines))
        self.assertTrue(any("O|" in line and "S001" in line for line in lines))
        self.assertTrue(lines[-1].startswith("L|"))

    def test_empty_orders_returns_none(self):
        profile = registry.get_profile("generic")
        self.assertIsNone(profile.build_worklist_response([], control_id="1"))


if __name__ == "__main__":
    unittest.main()
