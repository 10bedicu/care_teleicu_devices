"""Unit tests for Heto AU400 device profile."""

import unittest

import hl7

from lab_analyzer_device.hl7.devices.heto_au400 import HetoAU400Profile
from lab_analyzer_device.hl7.builder import OrderedTest
from lab_analyzer_device.hl7.extractor import ORUData

# ORU^R01 matching documented format — OBX-3 is EMPTY, test name in OBX-4
# Based on the documented example:
#   Item IDs: 2, 5, 6 / Item Names: TBil, ALT, AST
#   OBX format: OBX|n|NM||TestName|value|units|ref_range|flag|||F||original|time||||
HETO_AU400_ORU = (
    "MSH|^~\\&|HETO|AU400|||20070423101830||ORU^R01|1|P|2.5||||0||UNICODE|||\r"
    "PID|1||||Mike||19851001000000|M|||||||||||||||||||||||\r"
    "OBR|1|12345678|10|HETO^AU400|Y||20070413093253||||||||serum|||||||||||||||||||||||||||||||||\r"
    "OBX|1|NM||Tbil|100|umol/L|0-17.1|H|||F||100|20070413093253||||\r"
    "OBX|2|NM||ALT|98.2|U/L|0-40|H|||F||98.2|20070413093253||||\r"
    "OBX|3|NM||AST|26.4|U/L|0-40|N|||F||26.4|20070413093253||||\r"
)

# ORU^R01 with OBX-3 containing channel numbers (alternate format allowed per doc)
HETO_AU400_ORU_WITH_CHANNEL_IDS = (
    "MSH|^~\\&|HETO|AU400|||20070423101830||ORU^R01|2|P|2.5||||0||UNICODE|||\r"
    "PID|1||||Kumar^Ravi||19750320000000|M|||||||||||||||||||||||\r"
    "OBR|1|98765432|20|HETO^AU400|N||20070413093253||||||||serum|||||||||||||||||||||||||||||||||\r"
    "OBX|1|NM|2|Tbil|1.2|mg/dL|0.1-1.2|N|||F||1.2|20070413093253||||\r"
    "OBX|2|NM|5|ALT|25|U/L|0-40|N|||F||25|20070413093253||||\r"
    "OBX|3|NM|6|AST|22|U/L|0-40|N|||F||22|20070413093253||||\r"
    "OBX|4|NM||GLU|95|mg/dL|70-110|N|||F||95|20070413093253||||\r"
)

# ORU with mixed types including ST (qualitative result)
HETO_AU400_ORU_MIXED = (
    "MSH|^~\\&|HETO|AU400|||20070423101830||ORU^R01|3|P|2.5||||0||UNICODE|||\r"
    "PID|1||||Patient^Test||19900101000000|F|||||||||||||||||||||||\r"
    "OBR|1|11223344|30|HETO^AU400|N||20070413093253||||||||serum|||||||||||||||||||||||||||||||||\r"
    "OBX|1|NM||CRP|5.2|mg/L|0-6|N|||F||5.2|20070413093253||||\r"
    "OBX|2|ST||HBsAg|Negative||||N|||F||Negative|20070413093253||||\r"
)

# Calibration result (MSH-16 = 1) — should be handled differently
HETO_AU400_CALIBRATION = (
    "MSH|^~\\&|HETO|AU400|||20070423101830||ORU^R01|4|P|2.5||||1||UNICODE|||\r"
    "OBR|1|1|Tbil|HETO^AU400|||20070413093253||||||||||||||||||||||||||||||||||||||||\r"
)

# QC result (MSH-16 = 2)
HETO_AU400_QC = (
    "MSH|^~\\&|HETO|AU400|||20070423101830||ORU^R01|5|P|2.5||||2||UNICODE|||\r"
    "OBR|1|2|ALT|HETO^AU400|||20070413093253||||||||||||||||||||||||||||||||||||||||\r"
)

# QRY^Q02 — query from analyzer for barcode 123456
HETO_AU400_QRY = (
    "MSH|^~\\&|HETO|AU400|||20070423101830||QRY^Q02|1|P|2.5||||||UNICODE\r"
    "QRD|20070423101830|BC|D|1|||RD|123456|||123456\r"
    "QRF||20070423000000|20070423101830|||RCT|COR|ALL\r"
)


class TestProperties(unittest.TestCase):

    def setUp(self):
        self.profile = HetoAU400Profile()

    def test_device_type(self):
        self.assertEqual(self.profile.device_type, "heto_au400")

    def test_display_name(self):
        self.assertIn("Heto AU400", self.profile.display_name)

    def test_hl7_version(self):
        self.assertEqual(self.profile.hl7_version, "2.5")

    def test_communication_mode(self):
        self.assertEqual(self.profile.communication_mode, "host_query")

    def test_supports_query_orders(self):
        self.assertTrue(self.profile.supports_query_orders)

    def test_sending_application(self):
        self.assertEqual(self.profile.sending_application, "LIS")


class TestCodeMappings(unittest.TestCase):

    def setUp(self):
        self.profile = HetoAU400Profile()

    def test_documented_channel_2_tbil(self):
        """Channel 2 = TBil per documented example."""
        system, code, display = self.profile.resolve_code("2", "")
        self.assertEqual(system, "http://loinc.org")
        self.assertEqual(code, "1975-2")
        self.assertIn("Bilirubin.total", display)

    def test_documented_channel_5_alt(self):
        """Channel 5 = ALT per documented example."""
        system, code, display = self.profile.resolve_code("5", "")
        self.assertEqual(system, "http://loinc.org")
        self.assertEqual(code, "1742-6")

    def test_documented_channel_6_ast(self):
        """Channel 6 = AST per documented example."""
        system, code, display = self.profile.resolve_code("6", "")
        self.assertEqual(system, "http://loinc.org")
        self.assertEqual(code, "1920-8")

    def test_test_name_tbil(self):
        """Test name 'Tbil' resolves to bilirubin total LOINC."""
        system, code, display = self.profile.resolve_code("Tbil", "")
        self.assertEqual(system, "http://loinc.org")
        self.assertEqual(code, "1975-2")

    def test_test_name_alt(self):
        """Test name 'ALT' resolves to ALT LOINC."""
        system, code, display = self.profile.resolve_code("ALT", "")
        self.assertEqual(code, "1742-6")

    def test_test_name_ast(self):
        """Test name 'AST' resolves to AST LOINC."""
        system, code, display = self.profile.resolve_code("AST", "")
        self.assertEqual(code, "1920-8")

    def test_test_name_tp(self):
        """Test name 'TP' (from DSP example 'ALT,TP') resolves to total protein."""
        system, code, display = self.profile.resolve_code("TP", "")
        self.assertEqual(code, "2885-2")

    def test_test_name_glu(self):
        system, code, display = self.profile.resolve_code("GLU", "")
        self.assertEqual(code, "2345-7")

    def test_test_name_crp(self):
        system, code, display = self.profile.resolve_code("CRP", "")
        self.assertEqual(code, "1988-5")

    def test_test_name_bun(self):
        system, code, display = self.profile.resolve_code("BUN", "")
        self.assertEqual(code, "3094-0")

    def test_test_name_crea(self):
        system, code, display = self.profile.resolve_code("CREA", "")
        self.assertEqual(code, "2160-0")

    def test_unknown_code_returns_local(self):
        """Unknown test name falls back to local system."""
        system, code, display = self.profile.resolve_code("UNKNOWN_TEST", "")
        self.assertEqual(system, "local")
        self.assertEqual(code, "UNKNOWN_TEST")

    def test_only_documented_channel_ids_are_mapped(self):
        """Channels not in documentation (e.g. 1, 3, 4) are NOT mapped."""
        # Channel 1 is not documented — should return local
        system, code, display = self.profile.resolve_code("1", "")
        self.assertEqual(system, "local")
        self.assertEqual(code, "1")

        # Channel 3 is not documented
        system, code, display = self.profile.resolve_code("3", "")
        self.assertEqual(system, "local")
        self.assertEqual(code, "3")


class TestPanelMappings(unittest.TestCase):

    def setUp(self):
        self.profile = HetoAU400Profile()

    def test_lft_panel_uses_test_names(self):
        """LFT panel expands to test names the AU400 recognizes."""
        panels = self.profile.panel_mappings
        lft = panels["26958001"]
        self.assertIsInstance(lft, list)
        self.assertIn("Tbil", lft)
        self.assertIn("DBil", lft)
        self.assertIn("ALT", lft)
        self.assertIn("AST", lft)
        self.assertIn("ALP", lft)
        self.assertIn("TP", lft)
        self.assertIn("GGT", lft)
        self.assertIn("ALB", lft)

    def test_kft_panel_uses_test_names(self):
        """KFT panel expands to renal function test names."""
        panels = self.profile.panel_mappings
        kft = panels["54610007"]
        self.assertIn("BUN", kft)
        self.assertIn("CREA", kft)
        self.assertIn("UA", kft)
        self.assertIn("K", kft)
        self.assertIn("NA", kft)
        self.assertIn("CA", kft)

    def test_lipid_panel(self):
        panels = self.profile.panel_mappings
        lipid = panels["24331-1"]
        self.assertIn("CHOL", lipid)
        self.assertIn("TG", lipid)
        self.assertIn("HDL", lipid)
        self.assertIn("LDL", lipid)

    def test_validate_tests_lft(self):
        """validate_tests resolves LFT panel to individual test names."""
        tests = [OrderedTest(code="26958001", display="LFT")]
        resolved = self.profile.validate_tests(tests)
        self.assertEqual(len(resolved), 8)
        codes = [t.code for t in resolved]
        self.assertIn("Tbil", codes)
        self.assertIn("ALT", codes)
        self.assertIn("AST", codes)

    def test_validate_tests_invalid_code(self):
        tests = [OrderedTest(code="INVALID", display="Bad")]
        with self.assertRaises(ValueError):
            self.profile.validate_tests(tests)


class TestObservationExtraction(unittest.TestCase):
    """Test the overridden extract_observation that handles empty OBX-3."""

    def setUp(self):
        self.profile = HetoAU400Profile()

    def test_extract_with_empty_obx3(self):
        """Primary case: OBX-3 empty, test name in OBX-4."""
        msg = hl7.parse(HETO_AU400_ORU)
        obx_segments = [seg for seg in msg if str(seg[0][0]) == "OBX"]
        # OBX|1|NM||Tbil|100|... → code from OBX-4 "Tbil"
        code, display = self.profile.extract_observation_id(obx_segments[0])
        self.assertEqual(code, "Tbil")
        self.assertEqual(display, "Tbil")

    def test_extract_with_channel_id_in_obx3(self):
        """Alternate case: OBX-3 has channel number."""
        msg = hl7.parse(HETO_AU400_ORU_WITH_CHANNEL_IDS)
        obx_segments = [seg for seg in msg if str(seg[0][0]) == "OBX"]
        # OBX|1|NM|2|Tbil|1.2|... → code="2", display="Tbil"
        code, display = self.profile.extract_observation_id(obx_segments[0])
        self.assertEqual(code, "2")
        self.assertEqual(display, "Tbil")

    def test_extract_observation_resolves_test_name_to_loinc(self):
        """Full observation extraction resolves OBX-4 name to LOINC."""
        msg = hl7.parse(HETO_AU400_ORU)
        obx_segments = [seg for seg in msg if str(seg[0][0]) == "OBX"]
        obs = self.profile.extract_observation(obx_segments[0])
        self.assertIsNotNone(obs)
        # "Tbil" → LOINC 1975-2
        self.assertEqual(obs.code, "1975-2")
        self.assertEqual(obs.system, "http://loinc.org")
        self.assertEqual(obs.value, "100")
        self.assertEqual(obs.units, "umol/L")

    def test_extract_observation_resolves_channel_id_to_loinc(self):
        """When OBX-3 has channel ID, resolves via channel mapping."""
        msg = hl7.parse(HETO_AU400_ORU_WITH_CHANNEL_IDS)
        obx_segments = [seg for seg in msg if str(seg[0][0]) == "OBX"]
        obs = self.profile.extract_observation(obx_segments[0])
        # Channel "2" → LOINC 1975-2
        self.assertEqual(obs.code, "1975-2")
        self.assertEqual(obs.display, "Tbil")

    def test_extract_observation_unknown_name_stays_local(self):
        """Unknown test name becomes local code."""
        msg = hl7.parse(HETO_AU400_ORU_MIXED)
        obx_segments = [seg for seg in msg if str(seg[0][0]) == "OBX"]
        # OBX with "HBsAg" — not in code_mappings
        obs = self.profile.extract_observation(obx_segments[1])
        self.assertIsNotNone(obs)
        self.assertEqual(obs.code, "HBsAg")
        self.assertEqual(obs.system, "local")
        self.assertEqual(obs.value, "Negative")
        self.assertEqual(obs.value_type, "ST")


class TestSkipObx(unittest.TestCase):

    def setUp(self):
        self.profile = HetoAU400Profile()

    def test_keeps_nm_type(self):
        msg = hl7.parse(HETO_AU400_ORU)
        obx_segments = [seg for seg in msg if str(seg[0][0]) == "OBX"]
        self.assertFalse(self.profile.should_skip_obx(obx_segments[0]))

    def test_keeps_st_type(self):
        msg = hl7.parse(HETO_AU400_ORU_MIXED)
        obx_segments = [seg for seg in msg if str(seg[0][0]) == "OBX"]
        # Second OBX is ST type — should NOT be skipped
        self.assertFalse(self.profile.should_skip_obx(obx_segments[1]))


class TestResultDataExtraction(unittest.TestCase):
    """Integration test for full extract_result_data flow."""

    def setUp(self):
        self.profile = HetoAU400Profile()

    def test_extract_documented_example(self):
        """Extract data from message matching documented ORU format."""
        msg = hl7.parse(HETO_AU400_ORU)
        data = self.profile.extract_result_data(msg)
        # Patient
        self.assertEqual(data.patient_name, "Mike")
        # Specimen from OBR-2 (barcode)
        self.assertEqual(data.specimen_id, "12345678")
        # 3 observations (Tbil, ALT, AST)
        self.assertEqual(len(data.observations), 3)

    def test_observation_codes_resolved_to_loinc(self):
        """All known test names resolve to LOINC codes."""
        msg = hl7.parse(HETO_AU400_ORU)
        data = self.profile.extract_result_data(msg)
        codes = [obs.code for obs in data.observations]
        self.assertIn("1975-2", codes)  # Tbil
        self.assertIn("1742-6", codes)  # ALT
        self.assertIn("1920-8", codes)  # AST

    def test_observation_values_and_units(self):
        """Verify values and units are correctly extracted."""
        msg = hl7.parse(HETO_AU400_ORU)
        data = self.profile.extract_result_data(msg)
        # Tbil: 100 umol/L
        tbil = next(obs for obs in data.observations if obs.code == "1975-2")
        self.assertEqual(tbil.value, "100")
        self.assertEqual(tbil.units, "umol/L")
        self.assertEqual(tbil.abnormal_flags, "H")
        # ALT: 98.2 U/L
        alt = next(obs for obs in data.observations if obs.code == "1742-6")
        self.assertEqual(alt.value, "98.2")
        self.assertEqual(alt.units, "U/L")

    def test_observation_reference_range(self):
        msg = hl7.parse(HETO_AU400_ORU)
        data = self.profile.extract_result_data(msg)
        tbil = next(obs for obs in data.observations if obs.code == "1975-2")
        self.assertEqual(tbil.reference_range, "0-17.1")

    def test_extract_with_channel_ids(self):
        """Extraction works when OBX-3 has channel IDs."""
        msg = hl7.parse(HETO_AU400_ORU_WITH_CHANNEL_IDS)
        data = self.profile.extract_result_data(msg)
        self.assertEqual(data.patient_name, "Ravi Kumar")
        self.assertEqual(data.specimen_id, "98765432")
        # 4 observations: 3 with channel IDs + 1 with name only
        self.assertEqual(len(data.observations), 4)
        codes = [obs.code for obs in data.observations]
        self.assertIn("1975-2", codes)  # Channel 2 → Tbil
        self.assertIn("1742-6", codes)  # Channel 5 → ALT
        self.assertIn("1920-8", codes)  # Channel 6 → AST
        self.assertIn("2345-7", codes)  # GLU (name-based)

    def test_mixed_nm_and_st_types(self):
        """Both NM and ST observations are extracted."""
        msg = hl7.parse(HETO_AU400_ORU_MIXED)
        data = self.profile.extract_result_data(msg)
        self.assertEqual(len(data.observations), 2)
        crp = next(obs for obs in data.observations if obs.code == "1988-5")
        self.assertEqual(crp.value, "5.2")
        self.assertEqual(crp.value_type, "NM")
        hbsag = next(obs for obs in data.observations if obs.code == "HBsAg")
        self.assertEqual(hbsag.value, "Negative")
        self.assertEqual(hbsag.value_type, "ST")


class TestWorklistResponse(unittest.TestCase):

    def setUp(self):
        self.profile = HetoAU400Profile()

    def test_returns_two_messages(self):
        orders = [
            {
                "sample_id": "BAR001",
                "barcode": "BAR001",
                "patient_name": "Test User",
                "date_of_birth": "19900101000000",
                "gender": "M",
                "sample_type": "serum",
                "tests": [{"code": "ALT", "display": "ALT"}],
            }
        ]
        result = self.profile.build_worklist_response([ORUData(**o) for o in orders], "CTRL001")
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 2)

    def test_first_message_is_qck(self):
        orders = [
            {
                "sample_id": "BAR001",
                "barcode": "BAR001",
                "patient_name": "Test",
                "date_of_birth": "",
                "gender": "M",
                "sample_type": "serum",
                "tests": [{"code": "ALT", "display": "ALT"}],
            }
        ]
        result = self.profile.build_worklist_response([ORUData(**o) for o in orders], "CTRL001")
        qck = result[0]
        self.assertIn("QCK^Q02", qck)
        self.assertIn("MSA|AA|CTRL001", qck)
        self.assertIn("ERR|0", qck)
        self.assertIn("QAK|SR|OK", qck)
        # LIS sends to HETO|AU400 per doc
        self.assertIn("HETO", qck)
        self.assertIn("AU400", qck)

    def test_second_message_is_dsr(self):
        orders = [
            {
                "sample_id": "BAR001",
                "barcode": "BAR001",
                "patient_name": "Test User",
                "date_of_birth": "19900101",
                "gender": "F",
                "sample_type": "Serum",
                "tests": [
                    {"code": "ALT", "display": "ALT"},
                    {"code": "TP", "display": "TP"},
                ],
            }
        ]
        result = self.profile.build_worklist_response([ORUData(**o) for o in orders], "CTRL002")
        dsr = result[1]
        self.assertIn("DSR^Q03", dsr)
        self.assertIn("QAK|SR|OK", dsr)
        # Patient name at DSP|3|
        self.assertIn("Test User", dsr)
        # Test orders as comma-separated names (per doc: "ALT,TP")
        self.assertIn("ALT,TP", dsr)

    def test_dsr_contains_barcode(self):
        """DSP|21| must contain barcode (required per doc)."""
        orders = [
            {
                "sample_id": "10",
                "barcode": "SAMPLE123",
                "patient_name": "Patient",
                "date_of_birth": "",
                "gender": "",
                "sample_type": "",
                "tests": [{"code": "Tbil", "display": "Tbil"}],
            }
        ]
        result = self.profile.build_worklist_response([ORUData(**o) for o in orders], "CTRL003")
        dsr = result[1]
        self.assertIn("SAMPLE123", dsr)

    def test_returns_none_for_empty_orders(self):
        result = self.profile.build_worklist_response([], "CTRL004")
        self.assertIsNone(result)

    def test_multiple_orders_with_dsc(self):
        """Multiple orders: DSC non-empty for all except last."""
        orders = [
            {
                "sample_id": "S1",
                "barcode": "S1",
                "patient_name": "Patient One",
                "date_of_birth": "",
                "gender": "M",
                "sample_type": "serum",
                "tests": [{"code": "ALT", "display": "ALT"}],
            },
            {
                "sample_id": "S2",
                "barcode": "S2",
                "patient_name": "Patient Two",
                "date_of_birth": "",
                "gender": "F",
                "sample_type": "serum",
                "tests": [{"code": "AST", "display": "AST"}],
            },
        ]
        result = self.profile.build_worklist_response([ORUData(**o) for o in orders], "CTRL005")
        dsr = result[1]
        self.assertIn("Patient One", dsr)
        self.assertIn("Patient Two", dsr)

    def test_dsr_version_is_2_5(self):
        """DSR message uses HL7 v2.5 per device spec."""
        orders = [
            {
                "sample_id": "S1",
                "barcode": "S1",
                "patient_name": "Test",
                "date_of_birth": "",
                "gender": "",
                "sample_type": "",
                "tests": [{"code": "GLU", "display": "GLU"}],
            }
        ]
        result = self.profile.build_worklist_response([ORUData(**o) for o in orders], "CTRL006")
        self.assertIn("2.5", result[0])
        self.assertIn("2.5", result[1])


class TestSpecimenExtraction(unittest.TestCase):

    def setUp(self):
        self.profile = HetoAU400Profile()

    def test_specimen_from_obr2_barcode(self):
        """OBR-2 is the sample barcode per doc."""
        msg = hl7.parse(HETO_AU400_ORU)
        data = self.profile.extract_result_data(msg)
        self.assertEqual(data.specimen_id, "12345678")

    def test_placer_order_is_barcode(self):
        """Placer order number = barcode per doc."""
        msg = hl7.parse(HETO_AU400_ORU)
        data = self.profile.extract_result_data(msg)
        self.assertEqual(data.placer_order_number, "12345678")

    def test_filler_order_is_sample_id(self):
        """Filler order number = internal sample ID per doc."""
        msg = hl7.parse(HETO_AU400_ORU)
        data = self.profile.extract_result_data(msg)
        self.assertEqual(data.filler_order_number, "10")


if __name__ == "__main__":
    unittest.main()
