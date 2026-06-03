"""Unit tests for Mindray BC-5000 device profile."""

import unittest

import hl7

from lab_analyzer_device.hl7.devices.mindray_bc_5000 import MindrayBC5000Profile
from lab_analyzer_device.hl7.builder import OrderedTest
from lab_analyzer_device.hl7.extractor import ORUData

# ORU^R01 with 5-part differential CBC results (LOINC codes with LN system)
MINDRAY_BC5000_ORU_5DIFF = (
    "MSH|^~\\&|||||20250115120000||ORU^R01|1|P|2.3.1||||||UNICODE\r"
    "PID|1||7393670^^^^MR||Doe^John||19900804000000|Male\r"
    "PV1|1||ICU^^BedNO1\r"
    "OBR|1||TestSample001|00001^Automated Count^99MRC||20250115100000|20250115120000|||Operator||||20250115110000||||||||||HM||||||||Tester\r"
    "OBX|1|IS|08001^Take Mode^99MRC||O||||||F\r"
    "OBX|2|IS|08002^Blood Mode^99MRC||W||||||F\r"
    "OBX|3|IS|08003^Test Mode^99MRC||CBC+5DIFF||||||F\r"
    "OBX|4|IS|01002^Ref Group^99MRC||Common||||||F\r"
    "OBX|5|NM|30525-0^Age^LN||35|yr|||||F\r"
    "OBX|6|ST|01001^Remark^99MRC||Normal||||||F\r"
    "OBX|7|NM|6690-2^WBC^LN||9.55|10*9/L|4.00-10.00|N|||F\r"
    "OBX|8|NM|731-0^LYM#^LN||2.45|10*9/L|0.80-4.00|N|||F\r"
    "OBX|9|NM|736-9^LYM%^LN||25.7|%|20.0-40.0|N|||F\r"
    "OBX|10|NM|742-7^MON#^LN||0.58|10*9/L|0.12-0.80|N|||F\r"
    "OBX|11|NM|5905-5^MON%^LN||6.1|%|3.0-12.0|N|||F\r"
    "OBX|12|NM|751-8^NEU#^LN||6.20|10*9/L|2.00-7.00|N|||F\r"
    "OBX|13|NM|770-8^NEU%^LN||64.9|%|50.0-70.0|N|||F\r"
    "OBX|14|NM|711-2^EOS#^LN||0.22|10*9/L|0.02-0.50|N|||F\r"
    "OBX|15|NM|713-8^EOS%^LN||2.3|%|0.5-5.0|N|||F\r"
    "OBX|16|NM|704-7^BAS#^LN||0.10|10*9/L|0.00-0.10|N|||F\r"
    "OBX|17|NM|706-2^BAS%^LN||1.0|%|0.0-2.0|N|||F\r"
    "OBX|18|NM|789-8^RBC^LN||4.85|10*12/L|3.50-5.50|N|||F\r"
    "OBX|19|NM|718-7^HGB^LN||145.0|g/L|110.0-160.0|N|||F\r"
    "OBX|20|NM|4544-3^HCT^LN||42.5|%|37.0-54.0|N|||F\r"
    "OBX|21|NM|787-2^MCV^LN||87.6|fL|80.0-100.0|N|||F\r"
    "OBX|22|NM|785-6^MCH^LN||29.9|pg|27.0-34.0|N|||F\r"
    "OBX|23|NM|786-4^MCHC^LN||341|g/L|320-360|N|||F\r"
    "OBX|24|NM|788-0^RDW-CV^LN||12.8|%|11.0-16.0|N|||F\r"
    "OBX|25|NM|21000-5^RDW-SD^LN||42.3|fL|35.0-56.0|N|||F\r"
    "OBX|26|NM|777-3^PLT^LN||245|10*9/L|100-300|N|||F\r"
    "OBX|27|NM|32623-1^MPV^LN||10.2|fL|6.5-12.0|N|||F\r"
    "OBX|28|NM|32207-3^PDW^LN||15.6||15.0-17.0|N|||F\r"
    "OBX|29|NM|10002^PCT^99MRC||0.250|%|0.108-0.282|N|||F\r"
    "OBX|30|NM|10014^PLCR^99MRC||28.5|%|11.0-45.0|N|||F\r"
    "OBX|31|IS|12045^Multiple alerts^99MRC||F||||||F\r"
    "OBX|32|IS|12046^Lym left region alert^99MRC||F||||||F\r"
    "OBX|33|NM|15004^WBC Histogram. Meta Length^99MRC||1||||||F\r"
    "OBX|34|NM|15010^WBC Lym left line.^99MRC||30||||||F\r"
    "OBX|35|ED|15000^WBC Histogram. Binary^99MRC||^Application^Octer-stream^Base64^AAAAAAAAAA==||||||F\r"
    "OBX|36|ED|15050^RBC Histogram. Binary^99MRC||^Application^Octer-stream^Base64^AAAAAAAAAA==||||||F\r"
    "OBX|37|ED|15100^PLT Histogram. Binary^99MRC||^Application^Octer-stream^Base64^AAAAAAAAAA==||||||F\r"
)

# ORU^R01 with 3-part differential (MID/GRAN codes)
MINDRAY_BC5000_ORU_3DIFF = (
    "MSH|^~\\&|||||20250115130000||ORU^R01|2|P|2.3.1||||||UNICODE\r"
    "PID|1||PAT002^^^^MR||Smith^Jane||19850304000000|Female\r"
    "PV1|1||Hema^^BN2\r"
    "OBR|1||TestSample002|00001^Automated Count^99MRC||20250115120000|20250115130000\r"
    "OBX|1|IS|08003^Test Mode^99MRC||CBC||||||F\r"
    "OBX|2|NM|6690-2^WBC^LN||7.20|10*9/L|4.00-10.00|N|||F\r"
    "OBX|3|NM|731-0^LYM#^LN||2.10|10*9/L|0.80-4.00|N|||F\r"
    "OBX|4|NM|736-9^LYM%^LN||29.2|%|20.0-40.0|N|||F\r"
    "OBX|5|NM|10027^MID#^99MRC||0.50|10*9/L|0.10-1.50|N|||F\r"
    "OBX|6|NM|10029^MID%^99MRC||6.9|%|3.0-15.0|N|||F\r"
    "OBX|7|NM|10028^GRAN#^99MRC||4.60|10*9/L|2.00-7.00|N|||F\r"
    "OBX|8|NM|10030^GRAN%^99MRC||63.9|%|50.0-70.0|N|||F\r"
    "OBX|9|NM|789-8^RBC^LN||4.50|10*12/L|3.50-5.50|N|||F\r"
    "OBX|10|NM|718-7^HGB^LN||130.0|g/L|110.0-160.0|N|||F\r"
    "OBX|11|NM|777-3^PLT^LN||220|10*9/L|100-300|N|||F\r"
)

# ORU with abnormal flags (H and L)
MINDRAY_BC5000_ORU_ABNORMAL = (
    "MSH|^~\\&|||||20250115140000||ORU^R01|3|P|2.3.1||||||UNICODE\r"
    "PID|1||PAT003^^^^MR||Kumar^Raj||19700101000000|Male\r"
    "OBR|1||TestSample003|00001^Automated Count^99MRC||20250115130000|20250115140000\r"
    "OBX|1|NM|6690-2^WBC^LN||15.20|10*9/L|4.00-10.00|H|||F\r"
    "OBX|2|NM|718-7^HGB^LN||85.0|g/L|110.0-160.0|L|||F\r"
    "OBX|3|NM|777-3^PLT^LN||45|10*9/L|100-300|L~A|||F\r"
)

# ORM^O01 worklist query message
MINDRAY_BC5000_ORM = (
    "MSH|^~\\&|||||20250115100000||ORM^O01|60|P|2.3.1||||||UNICODE\r"
    "ORC|RF||SampleBarcode123||IP\r"
)

# QC message (MSH-11 = Q)
MINDRAY_BC5000_QC = (
    "MSH|^~\\&|||||20250115120000||ORU^R01|5|Q|2.3.1||||||UNICODE\r"
    "PID|1||LOT001^^^^MR||||20260101000000|\r"
    "OBR|1||QC_FILE_01|00001^Automated Count^99MRC||20250115120000|20250115120000|||||||||||||||||||HM||||||||Operator1\r"
    "OBX|1|NM|6690-2^WBC^LN||6.50|10*9/L|6.00-7.00|N|||F\r"
    "OBX|2|NM|789-8^RBC^LN||4.20|10*12/L|4.00-4.40|N|||F\r"
    "OBX|3|NM|718-7^HGB^LN||135.0|g/L|130.0-140.0|N|||F\r"
)


class TestProperties(unittest.TestCase):

    def setUp(self):
        self.profile = MindrayBC5000Profile()

    def test_device_type(self):
        self.assertEqual(self.profile.device_type, "mindray_bc_5000")

    def test_display_name(self):
        self.assertEqual(self.profile.display_name, "Mindray BC-5000 Auto Hematology Analyzer")

    def test_communication_mode(self):
        self.assertEqual(self.profile.communication_mode, "host_query")

    def test_supports_query_orders(self):
        self.assertTrue(self.profile.supports_query_orders)

    def test_hl7_version(self):
        self.assertEqual(self.profile.hl7_version, "2.3.1")

    def test_result_message_type(self):
        self.assertEqual(self.profile.result_message_type, "ORU^R01")

    def test_order_response_message_type(self):
        self.assertEqual(self.profile.order_response_message_type, "ORR^O02")

    def test_sending_application(self):
        self.assertEqual(self.profile.sending_application, "LIS")


class TestCodeMappings(unittest.TestCase):

    def setUp(self):
        self.profile = MindrayBC5000Profile()

    def test_wbc_loinc_passthrough(self):
        """WBC comes with system=LN, should pass through as-is."""
        system, code, display = self.profile.resolve_code("6690-2", "LN")
        self.assertEqual(system, "http://loinc.org")
        self.assertEqual(code, "6690-2")

    def test_wbc_without_system(self):
        """WBC code without system should resolve via code_mappings."""
        system, code, display = self.profile.resolve_code("6690-2", "")
        self.assertEqual(system, "http://loinc.org")
        self.assertEqual(code, "6690-2")

    def test_rbc_mapping(self):
        system, code, display = self.profile.resolve_code("789-8", "LN")
        self.assertEqual(system, "http://loinc.org")
        self.assertEqual(code, "789-8")

    def test_hgb_mapping(self):
        system, code, display = self.profile.resolve_code("718-7", "LN")
        self.assertEqual(system, "http://loinc.org")
        self.assertEqual(code, "718-7")

    def test_plt_mapping(self):
        system, code, display = self.profile.resolve_code("777-3", "LN")
        self.assertEqual(system, "http://loinc.org")
        self.assertEqual(code, "777-3")

    def test_pct_99mrc_code(self):
        """PCT uses 99MRC system — should resolve to LOINC via code_mappings."""
        system, code, display = self.profile.resolve_code("10002", "99MRC")
        self.assertEqual(system, "http://loinc.org")
        self.assertEqual(code, "51637-7")

    def test_plcr_99mrc_code(self):
        system, code, display = self.profile.resolve_code("10014", "99MRC")
        self.assertEqual(system, "http://loinc.org")
        self.assertEqual(code, "48386-7")

    def test_mid_number_99mrc(self):
        """MID# (3-part diff) maps to Monocytes."""
        system, code, display = self.profile.resolve_code("10027", "99MRC")
        self.assertEqual(system, "http://loinc.org")
        self.assertEqual(code, "26484-6")

    def test_gran_number_99mrc(self):
        """GRAN# (3-part diff) maps to Neutrophils."""
        system, code, display = self.profile.resolve_code("10028", "99MRC")
        self.assertEqual(system, "http://loinc.org")
        self.assertEqual(code, "751-8")

    def test_lic_ruo_code(self):
        """*LIC# (RUO) maps to Large Immature Cells."""
        system, code, display = self.profile.resolve_code("10000", "99MRC")
        self.assertEqual(system, "http://loinc.org")
        self.assertEqual(code, "55432-9")

    def test_5part_diff_codes(self):
        """All 5-part differential codes should resolve."""
        diff_codes = ["704-7", "751-8", "711-2", "731-0", "742-7",
                      "706-2", "770-8", "713-8", "736-9", "5905-5"]
        for code in diff_codes:
            system, resolved_code, _ = self.profile.resolve_code(code, "LN")
            self.assertEqual(system, "http://loinc.org", f"Code {code} should resolve to LOINC")
            self.assertEqual(resolved_code, code)

    def test_unknown_code(self):
        system, code, display = self.profile.resolve_code("UNKNOWN", "")
        self.assertEqual(system, "local")
        self.assertEqual(code, "UNKNOWN")


class TestPanelMappings(unittest.TestCase):

    def setUp(self):
        self.profile = MindrayBC5000Profile()

    def test_cbc_panel_loinc(self):
        panels = self.profile.panel_mappings
        self.assertEqual(panels["58410-2"], "00001")

    def test_cbc_diff_panel(self):
        panels = self.profile.panel_mappings
        self.assertEqual(panels["57021-8"], "00001")

    def test_cbc_snomed(self):
        panels = self.profile.panel_mappings
        self.assertEqual(panels["26604007"], "00001")

    def test_all_panels_map_to_00001(self):
        """BC-5000 uses single service type for all panels."""
        for key, value in self.profile.panel_mappings.items():
            self.assertEqual(value, "00001", f"Panel {key} should map to 00001")

    def test_validate_tests_cbc(self):
        tests = [OrderedTest(code="58410-2", display="CBC")]
        resolved = self.profile.validate_tests(tests)
        self.assertEqual(len(resolved), 1)
        self.assertEqual(resolved[0].code, "00001")

    def test_validate_tests_invalid_raises(self):
        tests = [OrderedTest(code="INVALID_PANEL", display="Bad")]
        with self.assertRaises(ValueError):
            self.profile.validate_tests(tests)


class TestOBXFiltering(unittest.TestCase):

    def setUp(self):
        self.profile = MindrayBC5000Profile()

    def test_keep_numeric_result_obx(self):
        """NM type OBX with clinical result code should be kept."""
        msg = hl7.parse(MINDRAY_BC5000_ORU_5DIFF)
        data = self.profile.extract_result_data(msg)
        for obs in data.observations:
            self.assertEqual(obs.value_type, "NM")

    def test_skip_is_type(self):
        """IS type OBX (mode/flags) should be skipped."""
        msg = hl7.parse(MINDRAY_BC5000_ORU_5DIFF)
        data = self.profile.extract_result_data(msg)
        codes = [obs.code for obs in data.observations]
        # IS-type codes should not appear
        self.assertNotIn("08001", codes)
        self.assertNotIn("08002", codes)
        self.assertNotIn("08003", codes)
        self.assertNotIn("01002", codes)
        self.assertNotIn("12045", codes)
        self.assertNotIn("12046", codes)

    def test_skip_st_type(self):
        """ST type OBX (remarks) should be skipped."""
        msg = hl7.parse(MINDRAY_BC5000_ORU_5DIFF)
        data = self.profile.extract_result_data(msg)
        codes = [obs.code for obs in data.observations]
        self.assertNotIn("01001", codes)

    def test_skip_ed_type(self):
        """ED type OBX (histograms/scattergrams) should be skipped."""
        msg = hl7.parse(MINDRAY_BC5000_ORU_5DIFF)
        data = self.profile.extract_result_data(msg)
        codes = [obs.code for obs in data.observations]
        self.assertNotIn("15000", codes)
        self.assertNotIn("15050", codes)
        self.assertNotIn("15100", codes)

    def test_skip_histogram_metadata_nm(self):
        """NM type OBX with histogram metadata codes (15xxx) should be skipped."""
        msg = hl7.parse(MINDRAY_BC5000_ORU_5DIFF)
        data = self.profile.extract_result_data(msg)
        codes = [obs.code for obs in data.observations]
        self.assertNotIn("15004", codes)
        self.assertNotIn("15010", codes)

    def test_5diff_observation_count(self):
        """5-part diff message should yield exactly the clinical result OBX segments."""
        msg = hl7.parse(MINDRAY_BC5000_ORU_5DIFF)
        data = self.profile.extract_result_data(msg)
        # OBX 5 (Age) + OBX 7-30 (24 clinical NM results) = 25 kept
        # Skipped: IS(4), ST(1), histogram NM(2), ED(3) = 10 skipped
        self.assertEqual(len(data.observations), 25)

    def test_3diff_observation_count(self):
        """3-part diff message should keep all NM clinical results."""
        msg = hl7.parse(MINDRAY_BC5000_ORU_3DIFF)
        data = self.profile.extract_result_data(msg)
        # OBX 2-11 are NM (10 segments), OBX 1 is IS (skipped)
        self.assertEqual(len(data.observations), 10)


class TestExtraction(unittest.TestCase):

    def setUp(self):
        self.profile = MindrayBC5000Profile()

    def test_patient_id_from_pid3(self):
        """PID-3 format: 7393670^^^^MR → patient ID = 7393670."""
        msg = hl7.parse(MINDRAY_BC5000_ORU_5DIFF)
        data = self.profile.extract_result_data(msg)
        self.assertEqual(data.patient_id, "7393670")

    def test_patient_id_3diff(self):
        msg = hl7.parse(MINDRAY_BC5000_ORU_3DIFF)
        data = self.profile.extract_result_data(msg)
        self.assertEqual(data.patient_id, "PAT002")

    def test_specimen_from_obr3(self):
        """OBR-3 (Filler Order Number) = sample ID."""
        msg = hl7.parse(MINDRAY_BC5000_ORU_5DIFF)
        data = self.profile.extract_result_data(msg)
        self.assertEqual(data.specimen_id, "TestSample001")

    def test_specimen_3diff(self):
        msg = hl7.parse(MINDRAY_BC5000_ORU_3DIFF)
        data = self.profile.extract_result_data(msg)
        self.assertEqual(data.specimen_id, "TestSample002")

    def test_observation_values(self):
        """Verify specific observation values are extracted correctly."""
        msg = hl7.parse(MINDRAY_BC5000_ORU_5DIFF)
        data = self.profile.extract_result_data(msg)
        obs_map = {obs.code: obs for obs in data.observations}
        # WBC
        self.assertEqual(obs_map["6690-2"].value, "9.55")
        self.assertEqual(obs_map["6690-2"].units, "10*9/L")
        # HGB
        self.assertEqual(obs_map["718-7"].value, "145.0")
        self.assertEqual(obs_map["718-7"].units, "g/L")
        # PLT
        self.assertEqual(obs_map["777-3"].value, "245")
        self.assertEqual(obs_map["777-3"].units, "10*9/L")

    def test_observation_reference_range(self):
        """Verify reference range extraction."""
        msg = hl7.parse(MINDRAY_BC5000_ORU_5DIFF)
        data = self.profile.extract_result_data(msg)
        obs_map = {obs.code: obs for obs in data.observations}
        self.assertEqual(obs_map["6690-2"].reference_range, "4.00-10.00")
        self.assertEqual(obs_map["777-3"].reference_range, "100-300")

    def test_abnormal_flags(self):
        """Verify abnormal flag extraction (H, L, L~A)."""
        msg = hl7.parse(MINDRAY_BC5000_ORU_ABNORMAL)
        data = self.profile.extract_result_data(msg)
        obs_map = {obs.code: obs for obs in data.observations}
        self.assertEqual(obs_map["6690-2"].abnormal_flags, "H")
        self.assertEqual(obs_map["718-7"].abnormal_flags, "L")
        self.assertEqual(obs_map["777-3"].abnormal_flags, "L~A")

    def test_3diff_codes_resolved(self):
        """3-part diff proprietary codes (10027, 10028) resolve to LOINC."""
        msg = hl7.parse(MINDRAY_BC5000_ORU_3DIFF)
        data = self.profile.extract_result_data(msg)
        codes = [obs.code for obs in data.observations]
        # MID# (10027) → 26484-6
        self.assertIn("26484-6", codes)
        # GRAN# (10028) → 751-8
        self.assertIn("751-8", codes)

    def test_loinc_codes_passthrough(self):
        """LOINC codes with LN system pass through unchanged."""
        msg = hl7.parse(MINDRAY_BC5000_ORU_5DIFF)
        data = self.profile.extract_result_data(msg)
        codes = [obs.code for obs in data.observations]
        self.assertIn("6690-2", codes)
        self.assertIn("789-8", codes)
        self.assertIn("718-7", codes)
        self.assertIn("777-3", codes)

    def test_qc_message_extraction(self):
        """QC messages (MSH-11=Q) should still extract results."""
        msg = hl7.parse(MINDRAY_BC5000_QC)
        data = self.profile.extract_result_data(msg)
        self.assertEqual(len(data.observations), 3)
        self.assertEqual(data.patient_id, "LOT001")


class TestWorklistResponse(unittest.TestCase):

    def setUp(self):
        self.profile = MindrayBC5000Profile()

    def test_builds_orr_response(self):
        orders = [
            {
                "sample_id": "SampleBarcode123",
                "patient_id": "7393670",
                "patient_name": "Doe^John",
                "date_of_birth": "19900804000000",
                "gender": "Male",
                "department": "ICU",
                "bed": "BedNO1",
                "collect_time": "20250115100000",
                "test_mode": "CBC+5DIFF",
                "blood_mode": "W",
            }
        ]
        result = self.profile.build_worklist_response([ORUData(**o) for o in orders], "60")
        self.assertIsInstance(result, str)
        self.assertIn("ORR^O02", result)
        self.assertIn("MSA|AA|60", result)

    def test_response_contains_pid(self):
        orders = [
            {
                "sample_id": "ABC123",
                "patient_id": "PAT001",
                "patient_name": "Test^Patient",
                "date_of_birth": "19850101000000",
                "gender": "Female",
                "department": "Hema",
                "bed": "B5",
                "collect_time": "20250115",
                "test_mode": "CBC",
                "blood_mode": "W",
            }
        ]
        result = self.profile.build_worklist_response([ORUData(**o) for o in orders], "CTRL1")
        self.assertIn("PID|", result)
        self.assertIn("PAT001^^^^MR", result)
        self.assertIn("Test^Patient", result)

    def test_response_contains_orc_af(self):
        """ORR response must have ORC with AF (affirm) and sample ID."""
        orders = [
            {
                "sample_id": "BARCODE456",
                "patient_id": "P2",
                "patient_name": "",
                "date_of_birth": "",
                "gender": "",
                "department": "",
                "bed": "",
                "collect_time": "",
                "test_mode": "CBC+5DIFF",
                "blood_mode": "W",
            }
        ]
        result = self.profile.build_worklist_response([ORUData(**o) for o in orders], "CTRL2")
        self.assertIn("ORC|AF|BARCODE456", result)

    def test_response_contains_obr(self):
        """ORR response must have OBR with 00001^Automated Count^99MRC."""
        orders = [
            {
                "sample_id": "S1",
                "patient_id": "P1",
                "patient_name": "",
                "date_of_birth": "",
                "gender": "",
                "department": "",
                "bed": "",
                "collect_time": "",
                "test_mode": "CBC",
                "blood_mode": "W",
            }
        ]
        result = self.profile.build_worklist_response([ORUData(**o) for o in orders], "CTRL3")
        self.assertIn("00001^Automated Count^99MRC", result)

    def test_response_contains_test_mode_obx(self):
        """ORR response must include OBX with test mode setting."""
        orders = [
            {
                "sample_id": "S2",
                "patient_id": "P2",
                "patient_name": "",
                "date_of_birth": "",
                "gender": "",
                "department": "",
                "bed": "",
                "collect_time": "",
                "test_mode": "CBC+5DIFF",
                "blood_mode": "P",
            }
        ]
        result = self.profile.build_worklist_response([ORUData(**o) for o in orders], "CTRL4")
        self.assertIn("08003^Test Mode^99MRC||CBC+5DIFF", result)
        self.assertIn("08002^Blood Mode^99MRC||P", result)

    def test_empty_orders_returns_none(self):
        result = self.profile.build_worklist_response([], "CTRL5")
        self.assertIsNone(result)

    def test_multiple_orders(self):
        """Multiple orders should produce multiple PID/ORC/OBR groups."""
        orders = [
            {
                "sample_id": "S1",
                "patient_id": "P1",
                "patient_name": "A^B",
                "date_of_birth": "",
                "gender": "Male",
                "department": "ICU",
                "bed": "B1",
                "collect_time": "",
                "test_mode": "CBC",
                "blood_mode": "W",
            },
            {
                "sample_id": "S2",
                "patient_id": "P2",
                "patient_name": "C^D",
                "date_of_birth": "",
                "gender": "Female",
                "department": "Ward",
                "bed": "B2",
                "collect_time": "",
                "test_mode": "CBC+5DIFF",
                "blood_mode": "W",
            },
        ]
        result = self.profile.build_worklist_response([ORUData(**o) for o in orders], "CTRL6")
        self.assertIn("ORC|AF|S1", result)
        self.assertIn("ORC|AF|S2", result)
        # Should have two PID segments
        self.assertEqual(result.count("PID|"), 2)

    def test_response_is_valid_hl7(self):
        """Built response should be parseable as HL7."""
        orders = [
            {
                "sample_id": "S1",
                "patient_id": "P1",
                "patient_name": "Test^User",
                "date_of_birth": "19900101000000",
                "gender": "Male",
                "department": "Lab",
                "bed": "B1",
                "collect_time": "20250115100000",
                "test_mode": "CBC+5DIFF",
                "blood_mode": "W",
            }
        ]
        result = self.profile.build_worklist_response([ORUData(**o) for o in orders], "CTRL7")
        # Should not raise
        parsed = hl7.parse(result)
        self.assertIsNotNone(parsed)
        # First segment should be MSH
        self.assertEqual(str(parsed.segment("MSH")(0)), "MSH")


class TestRegistration(unittest.TestCase):

    def test_registered_in_registry(self):
        from lab_analyzer_device.hl7.devices.registry import registry
        profiles = registry.get_profiles()
        self.assertIn("mindray_bc_5000", profiles)

    def test_registry_returns_correct_profile(self):
        from lab_analyzer_device.hl7.devices.registry import registry
        profile = registry.get_profile("mindray_bc_5000")
        self.assertIsInstance(profile, MindrayBC5000Profile)


if __name__ == "__main__":
    unittest.main()
