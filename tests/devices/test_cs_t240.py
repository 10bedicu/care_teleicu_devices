"""Unit tests for the CS-T240 ASTM device profile."""

import unittest
from datetime import datetime, timezone

from lab_analyzer_device.astm.devices.cs_t240 import CST240Profile
from lab_analyzer_device.hl7.builder import OrderedTest
from lab_analyzer_device.hl7.extractor import ORUData


class TestCST240Profile(unittest.TestCase):

    def setUp(self):
        self.profile = CST240Profile()

    def test_properties(self):
        self.assertEqual(self.profile.device_type, "cs_t240")
        self.assertEqual(self.profile.display_name, "Auto-Chemistry Analyzer CS-T240")
        self.assertEqual(self.profile.communication_mode, "host_query")
        self.assertTrue(self.profile.supports_query_orders)

    def test_result_parsing_barcode_mode(self):
        records = [
            r"H|\^&|||Analyzer|||||Host|||1|20090119131415",
            r"P|1||||ZhangDongdong|||M||||||40^Y",
            r"O|1|128123^1^1^2|||R|20090119123027|||||||||1||||||||||O",
            r"R|1|^^^ALT|333|U/L|2^22|1-3s|>+3SD|||||20110104172413",
            r"R|2|^^^AST|444|U/L|2^22|1-3s|>+3SD|||||20110104172413",
            r"L|1|N",
        ]
        data = self.profile.extract_result_data(records)
        self.assertEqual(data.patient_name, "ZhangDongdong")
        self.assertEqual(data.gender, "M")
        self.assertEqual(data.specimen_id, "128123")
        self.assertEqual(data.sample_id, "128123")
        self.assertEqual(data.placer_order_number, "128123")

        self.assertEqual(len(data.observations), 2)
        alt = data.observations[0]
        self.assertEqual(alt.code, "1742-6")  # mapped from ALT
        self.assertEqual(alt.value, "333")
        self.assertEqual(alt.units, "U/L")

        ast = data.observations[1]
        self.assertEqual(ast.code, "1920-8")  # mapped from AST
        self.assertEqual(ast.value, "444")
        self.assertEqual(ast.units, "U/L")

    def test_result_parsing_sample_no_mode(self):
        records = [
            r"H|\^&|||Analyzer|||||Host|||1|20090119131415",
            r"P|1||||ZhangDongdong|||M||||||40^Y",
            r"O|1|^130^1^1^N|||R|20090119123027|||||||||1||||||||||O",
            r"R|1|^^^ALT|333|U/L|2^22|1-3s|>+3SD|||||20110104172413",
            r"L|1|N",
        ]
        data = self.profile.extract_result_data(records)
        self.assertEqual(data.specimen_id, "130")
        self.assertEqual(data.sample_id, "130")

    def test_build_worklist_response_with_matching_query_sno(self):
        orders = [
            ORUData(
                patient_id="PID1",
                patient_name="John Doe",
                date_of_birth="19800101",
                gender="M",
                sample_id="130",
                sample_type="Urine",
                collect_time="2024-01-01T12:00:00Z",
                tests=[OrderedTest(code="ALT"), OrderedTest(code="AST")],
            )
        ]
        # Query in S. No Mode
        raw_query = "H|\\^&\rQ|1|^130^5^45^N||ALL||||||||O\rL|1|N"
        response = self.profile.build_worklist_response(orders, raw_query=raw_query)
        self.assertIsNotNone(response)

        lines = response.split("\n")
        self.assertEqual(lines[0], r"H|\^&")

        # P|seq||patient_id||patient_name|||gender||||||age^age_unit
        current_year = datetime.now(timezone.utc).year
        expected_age = current_year - 1980
        self.assertEqual(lines[1], f"P|1||PID1||John Doe|||M||||||{expected_age}^Y")

        # O records should use the matching specimen ID from query: ^130^5^45^N
        # and specimen descriptor for Urine (2)
        self.assertTrue(lines[2].startswith("O|1|^130^5^45^N||^^^ALT|R|20240101120000|||||||||2"))
        self.assertTrue(lines[3].startswith("O|2|^130^5^45^N||^^^AST|R|20240101120000|||||||||2"))
        self.assertEqual(lines[4], "L|1|N")

    def test_build_worklist_response_with_matching_query_barcode(self):
        orders = [
            ORUData(
                patient_id="PID2",
                patient_name="Jane Doe",
                date_of_birth="19900505",
                gender="F",
                sample_id="BC999",
                sample_type="Serum",
                tests=[OrderedTest(code="TP")],
            )
        ]
        # Query in Barcode ID Mode
        raw_query = "H|\\^&\rQ|1|BC999^^1^12^N||ALL||||||||O\rL|1|N"
        response = self.profile.build_worklist_response(orders, raw_query=raw_query)
        self.assertIsNotNone(response)

        lines = response.split("\n")
        # O record should use matching specimen ID: BC999^^1^12^N
        # and specimen descriptor for Serum (1)
        self.assertTrue(lines[2].startswith("O|1|BC999^^1^12^N||^^^TP|R|"))
        self.assertTrue(lines[2].endswith("|||||||||1||||||||||O"))

    def test_build_worklist_response_fallback(self):
        orders = [
            ORUData(
                patient_id="PID3",
                patient_name="Alex Smith",
                date_of_birth="",
                gender="O",
                sample_id="456",
                sample_type="Other",
                tests=[OrderedTest(code="ALB")],
            )
        ]
        # Empty query
        response = self.profile.build_worklist_response(orders, raw_query=None)
        self.assertIsNotNone(response)

        lines = response.split("\n")
        # Fallback specimen ID for numeric sample_id "456" is "^456^1^1^N"
        self.assertTrue(lines[2].startswith("O|1|^456^1^1^N||^^^ALB|R|"))
        # Descriptor for Other is 7
        self.assertTrue(lines[2].endswith("|||||||||7||||||||||O"))
