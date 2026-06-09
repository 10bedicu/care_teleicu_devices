"""Unit tests for Mindray BC-5150 device profile."""

import unittest

import hl7

from lab_analyzer_device.hl7.devices.mindray_bc_5150 import MindrayBC5150Profile
from lab_analyzer_device.hl7.builder import OrderedTest
from lab_analyzer_device.hl7.extractor import ORUData

# Real ORU^R01 from BC-5150 device (51 OBX segments, CBC+DIFF)
MINDRAY_BC5150_ORU_REAL = (
    "MSH|^~\\&|||||20260608160436||ORU^R01|3|P|2.3.1||||||UNICODE\r"
    "PID|1||A966^^^^MR||^USHA K S|||Female\r"
    "PV1|1\r"
    "OBR|1||31|00001^Automated Count^99MRC|||20260608151657|||||||||||||||||HM||||||||Administrator\r"
    "OBX|1|IS|08001^Take Mode^99MRC||O||||||F\r"
    "OBX|2|IS|08002^Blood Mode^99MRC||W||||||F\r"
    "OBX|3|IS|08003^Test Mode^99MRC||CBC+DIFF||||||F\r"
    "OBX|4|IS|01002^Ref Group^99MRC||Adult female||||||F\r"
    "OBX|5|NM|30525-0^Age^LN||26|yr|||||F\r"
    "OBX|6|NM|6690-2^WBC^LN||10.57|10*9/L|4.00-10.00|H~N|||F\r"
    "OBX|7|NM|704-7^BAS#^LN||0.00|10*9/L|0.00-0.10|N|||F\r"
    "OBX|8|NM|706-2^BAS%^LN||0.0|%|0.0-1.0|N|||F\r"
    "OBX|9|NM|751-8^NEU#^LN||7.80|10*9/L|2.00-7.00|H~N|||F\r"
    "OBX|10|NM|770-8^NEU%^LN||73.8|%|50.0-70.0|H~N|||F\r"
    "OBX|11|NM|711-2^EOS#^LN||0.35|10*9/L|0.02-0.50|N|||F\r"
    "OBX|12|NM|713-8^EOS%^LN||3.3|%|0.5-5.0|N|||F\r"
    "OBX|13|NM|731-0^LYM#^LN||1.59|10*9/L|0.80-4.00|N|||F\r"
    "OBX|14|NM|736-9^LYM%^LN||15.0|%|20.0-40.0|L~N|||F\r"
    "OBX|15|NM|742-7^MON#^LN||0.83|10*9/L|0.12-1.20|N|||F\r"
    "OBX|16|NM|5905-5^MON%^LN||7.9|%|3.0-12.0|N|||F\r"
    "OBX|17|NM|26477-0^*ALY#^LN||0.01|10*9/L|0.00-0.00|H~N|||F\r"
    "OBX|18|NM|13046-8^*ALY%^LN||0.001||0.000-0.000|H~N|||F\r"
    "OBX|19|NM|10000^*LIC#^99MRC||0.02|10*9/L|0.00-0.00|H~N|||F\r"
    "OBX|20|NM|10001^*LIC%^99MRC||0.002||0.000-0.000|H~N|||F\r"
    "OBX|21|NM|30376-8^Blast#^LN||0.01|10*9/L|0.00-0.00|H~N|||F\r"
    "OBX|22|NM|10049^Blast%^99MRC||0.001||0.000-0.000|H~N|||F\r"
    "OBX|23|NM|10094^Pltclump#^99MRC||0.00|10*9/L|0.00-0.00|N|||F\r"
    "OBX|24|NM|10095^Pltclump%^99MRC||0.000||0.000-0.000|N|||F\r"
    "OBX|25|NM|10096^Lip#^99MRC||0.00|10*9/L|0.00-0.00|N|||F\r"
    "OBX|26|NM|10097^Lip%^99MRC||0.000||0.000-0.000|N|||F\r"
    "OBX|27|NM|10069^Neu-X^99MRC||123.6||0.0-0.0|H~N|||F\r"
    "OBX|28|NM|10070^Neu-Y^99MRC||143.1||0.0-0.0|H~N|||F\r"
    "OBX|29|NM|10071^Neu-Z^99MRC||31.6||0.0-0.0|H~N|||F\r"
    "OBX|30|NM|10072^Lym-X^99MRC||43.9||0.0-0.0|H~N|||F\r"
    "OBX|31|NM|10073^Lym-Y^99MRC||98.4||0.0-0.0|H~N|||F\r"
    "OBX|32|NM|10074^Lym-Z^99MRC||18.3||0.0-0.0|H~N|||F\r"
    "OBX|33|NM|10075^Mon-X^99MRC||64.2||0.0-0.0|H~N|||F\r"
    "OBX|34|NM|10076^Mon-Y^99MRC||163.1||0.0-0.0|H~N|||F\r"
    "OBX|35|NM|10077^Mon-Z^99MRC||25.4||0.0-0.0|H~N|||F\r"
    "OBX|36|NM|789-8^RBC^LN||3.90|10*12/L|3.50-5.00|N|||F\r"
    "OBX|37|NM|718-7^HGB^LN||12.4|g/dL|11.0-15.0|N|||F\r"
    "OBX|38|NM|787-2^MCV^LN||87.8|fL|80.0-100.0|N|||F\r"
    "OBX|39|NM|785-6^MCH^LN||31.8|pg|27.0-34.0|N|||F\r"
    "OBX|40|NM|786-4^MCHC^LN||36.2|g/dL|32.0-36.0|H~N|||F\r"
    "OBX|41|NM|788-0^RDW-CV^LN||13.8|%|11.0-16.0|N|||F\r"
    "OBX|42|NM|21000-5^RDW-SD^LN||45.8|fL|35.0-56.0|N|||F\r"
    "OBX|43|NM|4544-3^HCT^LN||34.3|%|37.0-47.0|L~N|||F\r"
    "OBX|44|NM|777-3^PLT^LN||172|10*9/L|150-450|N|||F\r"
    "OBX|45|NM|32623-1^MPV^LN||10.8|fL|6.5-12.0|N|||F\r"
    "OBX|46|NM|32207-3^PDW^LN||16.7||9.0-17.0|N|||F\r"
    "OBX|47|NM|10002^PCT^99MRC||0.187|%|0.108-0.282|N|||F\r"
    "OBX|48|NM|30392-5^NRBC#^LN||0.00|10*9/L|0.00-0.00|N|||F\r"
    "OBX|49|NM|26461-4^NRBC%^LN||0.000||0.000-0.000|N|||F\r"
    "OBX|50|NM|10013^PLCC^99MRC||57|10*9/L|30-90|N|||F\r"
    "OBX|51|NM|10014^PLCR^99MRC||33.3|%|11.0-45.0|N|||F\r"
)

# ORU^R01 with 3-part differential (MID/GRAN codes)
MINDRAY_BC5150_ORU_3DIFF = (
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
MINDRAY_BC5150_ORU_ABNORMAL = (
    "MSH|^~\\&|||||20250115140000||ORU^R01|3|P|2.3.1||||||UNICODE\r"
    "PID|1||PAT003^^^^MR||Kumar^Raj||19700101000000|Male\r"
    "OBR|1||TestSample003|00001^Automated Count^99MRC||20250115130000|20250115140000\r"
    "OBX|1|NM|6690-2^WBC^LN||15.20|10*9/L|4.00-10.00|H|||F\r"
    "OBX|2|NM|718-7^HGB^LN||85.0|g/L|110.0-160.0|L|||F\r"
    "OBX|3|NM|777-3^PLT^LN||45|10*9/L|100-300|L~A|||F\r"
)

# QC message (MSH-11 = Q)
MINDRAY_BC5150_QC = (
    "MSH|^~\\&|||||20250115120000||ORU^R01|5|Q|2.3.1||||||UNICODE\r"
    "PID|1||LOT001^^^^MR||||20260101000000|\r"
    "OBR|1||QC_FILE_01|00001^Automated Count^99MRC||20250115120000|20250115120000|||||||||||||||||||HM||||||||Operator1\r"
    "OBX|1|NM|6690-2^WBC^LN||6.50|10*9/L|6.00-7.00|N|||F\r"
    "OBX|2|NM|789-8^RBC^LN||4.20|10*12/L|4.00-4.40|N|||F\r"
    "OBX|3|NM|718-7^HGB^LN||135.0|g/L|130.0-140.0|N|||F\r"
)


class TestProperties(unittest.TestCase):

    def setUp(self):
        self.profile = MindrayBC5150Profile()

    def test_device_type(self):
        self.assertEqual(self.profile.device_type, "mindray_bc_5150")

    def test_display_name(self):
        self.assertEqual(self.profile.display_name, "Mindray BC-5150 Auto Hematology Analyzer")

    def test_communication_mode(self):
        self.assertEqual(self.profile.communication_mode, "host_query")

    def test_hl7_connection_mode(self):
        self.assertEqual(self.profile.hl7_connection_mode, "outbound")

    def test_default_oru_port(self):
        self.assertEqual(self.profile.default_oru_port, 5100)

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
        self.profile = MindrayBC5150Profile()

    def test_wbc_loinc_passthrough(self):
        system, code, _ = self.profile.resolve_code("6690-2", "LN")
        self.assertEqual(system, "http://loinc.org")
        self.assertEqual(code, "6690-2")

    def test_wbc_without_system(self):
        system, code, _ = self.profile.resolve_code("6690-2", "")
        self.assertEqual(system, "http://loinc.org")
        self.assertEqual(code, "6690-2")

    def test_pct_99mrc_code(self):
        system, code, _ = self.profile.resolve_code("10002", "99MRC")
        self.assertEqual(system, "http://loinc.org")
        self.assertEqual(code, "51637-7")

    def test_plcc_99mrc_code(self):
        system, code, _ = self.profile.resolve_code("10013", "99MRC")
        self.assertEqual(system, "http://loinc.org")
        self.assertEqual(code, "96354-6")

    def test_plcr_99mrc_code(self):
        system, code, _ = self.profile.resolve_code("10014", "99MRC")
        self.assertEqual(system, "http://loinc.org")
        self.assertEqual(code, "48386-7")

    def test_blast_percent_99mrc(self):
        system, code, _ = self.profile.resolve_code("10049", "99MRC")
        self.assertEqual(system, "http://loinc.org")
        self.assertEqual(code, "26446-5")

    def test_lic_ruo_code(self):
        system, code, _ = self.profile.resolve_code("10000", "99MRC")
        self.assertEqual(system, "http://loinc.org")
        self.assertEqual(code, "55432-9")

    def test_mid_number_99mrc(self):
        system, code, _ = self.profile.resolve_code("10027", "99MRC")
        self.assertEqual(system, "http://loinc.org")
        self.assertEqual(code, "26484-6")

    def test_gran_number_99mrc(self):
        system, code, _ = self.profile.resolve_code("10028", "99MRC")
        self.assertEqual(system, "http://loinc.org")
        self.assertEqual(code, "751-8")

    def test_5part_diff_codes(self):
        diff_codes = ["704-7", "751-8", "711-2", "731-0", "742-7",
                      "706-2", "770-8", "713-8", "736-9", "5905-5"]
        for code in diff_codes:
            system, resolved_code, _ = self.profile.resolve_code(code, "LN")
            self.assertEqual(system, "http://loinc.org", f"Code {code} should resolve to LOINC")
            self.assertEqual(resolved_code, code)

    def test_unknown_code(self):
        system, code, _ = self.profile.resolve_code("UNKNOWN", "")
        self.assertEqual(system, "local")
        self.assertEqual(code, "UNKNOWN")


class TestPanelMappings(unittest.TestCase):

    def setUp(self):
        self.profile = MindrayBC5150Profile()

    def test_cbc_panel_loinc(self):
        self.assertEqual(self.profile.panel_mappings["58410-2"], "00001")

    def test_all_panels_map_to_00001(self):
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
        self.profile = MindrayBC5150Profile()

    def test_real_sample_observation_count(self):
        msg = hl7.parse(MINDRAY_BC5150_ORU_REAL)
        data = self.profile.extract_result_data(msg)
        # 51 OBX - 4 IS - 1 Age NM - 9 scatter NM = 37 clinical NM results
        self.assertEqual(len(data.observations), 37)

    def test_skip_is_type(self):
        msg = hl7.parse(MINDRAY_BC5150_ORU_REAL)
        data = self.profile.extract_result_data(msg)
        codes = [obs.code for obs in data.observations]
        self.assertNotIn("08001", codes)
        self.assertNotIn("08002", codes)
        self.assertNotIn("08003", codes)
        self.assertNotIn("01002", codes)

    def test_skip_age(self):
        msg = hl7.parse(MINDRAY_BC5150_ORU_REAL)
        data = self.profile.extract_result_data(msg)
        codes = [obs.code for obs in data.observations]
        self.assertNotIn("30525-0", codes)

    def test_skip_scattergram_coords(self):
        msg = hl7.parse(MINDRAY_BC5150_ORU_REAL)
        data = self.profile.extract_result_data(msg)
        codes = [obs.code for obs in data.observations]
        for code in ("10069", "10070", "10071", "10072", "10073", "10074", "10075", "10076", "10077"):
            self.assertNotIn(code, codes)

    def test_keep_numeric_result_obx(self):
        msg = hl7.parse(MINDRAY_BC5150_ORU_REAL)
        data = self.profile.extract_result_data(msg)
        for obs in data.observations:
            self.assertEqual(obs.value_type, "NM")

    def test_3diff_observation_count(self):
        msg = hl7.parse(MINDRAY_BC5150_ORU_3DIFF)
        data = self.profile.extract_result_data(msg)
        self.assertEqual(len(data.observations), 10)


class TestExtraction(unittest.TestCase):

    def setUp(self):
        self.profile = MindrayBC5150Profile()

    def test_patient_id_from_real_sample(self):
        msg = hl7.parse(MINDRAY_BC5150_ORU_REAL)
        data = self.profile.extract_result_data(msg)
        self.assertEqual(data.patient_id, "A966")

    def test_patient_name_from_real_sample(self):
        msg = hl7.parse(MINDRAY_BC5150_ORU_REAL)
        data = self.profile.extract_result_data(msg)
        self.assertEqual(data.patient_name, "USHA K S")

    def test_specimen_from_real_sample(self):
        msg = hl7.parse(MINDRAY_BC5150_ORU_REAL)
        data = self.profile.extract_result_data(msg)
        self.assertEqual(data.specimen_id, "31")

    def test_observation_values_real_sample(self):
        msg = hl7.parse(MINDRAY_BC5150_ORU_REAL)
        data = self.profile.extract_result_data(msg)
        obs_map = {obs.code: obs for obs in data.observations}
        self.assertEqual(obs_map["6690-2"].value, "10.57")
        self.assertEqual(obs_map["6690-2"].units, "10*9/L")
        self.assertEqual(obs_map["718-7"].value, "12.4")
        self.assertEqual(obs_map["718-7"].units, "g/dL")
        self.assertEqual(obs_map["777-3"].value, "172")

    def test_composite_abnormal_flags(self):
        msg = hl7.parse(MINDRAY_BC5150_ORU_REAL)
        data = self.profile.extract_result_data(msg)
        obs_map = {obs.code: obs for obs in data.observations}
        self.assertEqual(obs_map["6690-2"].abnormal_flags, "H~N")
        self.assertEqual(obs_map["736-9"].abnormal_flags, "L~N")
        self.assertEqual(obs_map["4544-3"].abnormal_flags, "L~N")

    def test_blast_codes_resolved(self):
        msg = hl7.parse(MINDRAY_BC5150_ORU_REAL)
        data = self.profile.extract_result_data(msg)
        codes = [obs.code for obs in data.observations]
        self.assertIn("30376-8", codes)
        self.assertIn("26446-5", codes)

    def test_nrbc_codes_passthrough(self):
        msg = hl7.parse(MINDRAY_BC5150_ORU_REAL)
        data = self.profile.extract_result_data(msg)
        codes = [obs.code for obs in data.observations]
        self.assertIn("30392-5", codes)
        self.assertIn("26461-4", codes)

    def test_pltclump_lip_local_codes(self):
        msg = hl7.parse(MINDRAY_BC5150_ORU_REAL)
        data = self.profile.extract_result_data(msg)
        local_obs = [obs for obs in data.observations if obs.system == "local"]
        local_codes = {obs.code for obs in local_obs}
        self.assertEqual(local_codes, {"10094", "10095", "10096", "10097"})

    def test_abnormal_flags_simple(self):
        msg = hl7.parse(MINDRAY_BC5150_ORU_ABNORMAL)
        data = self.profile.extract_result_data(msg)
        obs_map = {obs.code: obs for obs in data.observations}
        self.assertEqual(obs_map["6690-2"].abnormal_flags, "H")
        self.assertEqual(obs_map["718-7"].abnormal_flags, "L")
        self.assertEqual(obs_map["777-3"].abnormal_flags, "L~A")

    def test_3diff_codes_resolved(self):
        msg = hl7.parse(MINDRAY_BC5150_ORU_3DIFF)
        data = self.profile.extract_result_data(msg)
        codes = [obs.code for obs in data.observations]
        self.assertIn("26484-6", codes)
        self.assertIn("751-8", codes)

    def test_qc_message_extraction(self):
        msg = hl7.parse(MINDRAY_BC5150_QC)
        data = self.profile.extract_result_data(msg)
        self.assertEqual(len(data.observations), 3)
        self.assertEqual(data.patient_id, "LOT001")


class TestWorklistResponse(unittest.TestCase):

    def setUp(self):
        self.profile = MindrayBC5150Profile()

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
                "test_mode": "CBC+DIFF",
                "blood_mode": "W",
            }
        ]
        result = self.profile.build_worklist_response([ORUData(**o) for o in orders], "60")
        self.assertIsInstance(result, str)
        self.assertIn("ORR^O02", result)
        self.assertIn("MSA|AA|60", result)

    def test_response_contains_orc_af(self):
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
                "test_mode": "CBC+DIFF",
                "blood_mode": "W",
            }
        ]
        result = self.profile.build_worklist_response([ORUData(**o) for o in orders], "CTRL2")
        self.assertIn("ORC|AF|BARCODE456", result)

    def test_response_contains_test_mode_obx(self):
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
                "test_mode": "CBC+DIFF",
                "blood_mode": "P",
            }
        ]
        result = self.profile.build_worklist_response([ORUData(**o) for o in orders], "CTRL4")
        self.assertIn("08003^Test Mode^99MRC||CBC+DIFF", result)
        self.assertIn("08002^Blood Mode^99MRC||P", result)

    def test_empty_orders_returns_none(self):
        result = self.profile.build_worklist_response([], "CTRL5")
        self.assertIsNone(result)

    def test_response_is_valid_hl7(self):
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
                "test_mode": "CBC+DIFF",
                "blood_mode": "W",
            }
        ]
        result = self.profile.build_worklist_response([ORUData(**o) for o in orders], "CTRL7")
        parsed = hl7.parse(result)
        self.assertIsNotNone(parsed)
        self.assertEqual(str(parsed.segment("MSH")(0)), "MSH")


class TestRegistration(unittest.TestCase):

    def test_registered_in_registry(self):
        from lab_analyzer_device.hl7.devices.registry import registry
        profiles = registry.get_profiles()
        self.assertIn("mindray_bc_5150", profiles)

    def test_registry_returns_correct_profile(self):
        from lab_analyzer_device.hl7.devices.registry import registry
        profile = registry.get_profile("mindray_bc_5150")
        self.assertIsInstance(profile, MindrayBC5150Profile)


if __name__ == "__main__":
    unittest.main()
