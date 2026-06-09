"""Unit tests for lab_analyzer_device.hl7.builder module."""

import unittest

import hl7

from lab_analyzer_device.hl7.builder import ORMData, OrderedTest, OrderingPhysician, build_orm_message


class TestORMDataModel(unittest.TestCase):

    def test_minimal_creation(self):
        data = ORMData(
            patient_id="PAT001",
            placer_order_number="PLAC001",
            filler_order_number="FILL001",
        )
        self.assertEqual(data.patient_id, "PAT001")
        self.assertEqual(data.placer_order_number, "PLAC001")
        self.assertEqual(data.tests, [])

    def test_full_creation(self):
        data = ORMData(
            patient_id="PAT001",
            placer_order_number="PLAC001",
            filler_order_number="FILL001",
            patient_name="John Doe",
            date_of_birth="19900101",
            ordering_physician=OrderingPhysician(
                id="DOC001", family_name="Smith", given_name="Jane"
            ),
            tests=[OrderedTest(code="CBC", display="Complete Blood Count")],
            specimen_id="SPEC001",
        )
        self.assertEqual(data.patient_name, "John Doe")
        self.assertEqual(len(data.tests), 1)
        self.assertEqual(data.ordering_physician.family_name, "Smith")


class TestOrderedTestModel(unittest.TestCase):

    def test_default_system(self):
        test = OrderedTest(code="CBC", display="Complete Blood Count")
        self.assertEqual(test.system, "http://loinc.org")

    def test_custom_system(self):
        test = OrderedTest(code="1001", display="Count", system="local")
        self.assertEqual(test.system, "local")


class TestBuildOrmMessage(unittest.TestCase):

    def test_build_generic_orm(self):
        data = ORMData(
            patient_id="PAT001",
            placer_order_number="PLAC001",
            filler_order_number="FILL001",
            patient_name="John Doe",
            tests=[OrderedTest(code="CBC", display="Complete Blood Count")],
        )
        msg = build_orm_message(data)
        self.assertIsInstance(msg, hl7.Message)
        msh = msg.segment("MSH")
        self.assertIn("ORM", str(msh(9)))

    def test_build_with_ordering_physician(self):
        data = ORMData(
            patient_id="PAT001",
            placer_order_number="PLAC001",
            filler_order_number="FILL001",
            ordering_physician=OrderingPhysician(
                id="DOC001", family_name="Smith", given_name="Jane"
            ),
            tests=[OrderedTest(code="CBC", display="Complete Blood Count")],
        )
        msg = build_orm_message(data)
        orc = msg.segment("ORC")
        self.assertIn("DOC001", str(orc))

    def test_build_with_multiple_tests(self):
        data = ORMData(
            patient_id="PAT001",
            placer_order_number="PLAC001",
            filler_order_number="FILL001",
            tests=[
                OrderedTest(code="CBC", display="CBC"),
                OrderedTest(code="BMP", display="Basic Metabolic Panel"),
            ],
        )
        msg = build_orm_message(data)
        raw = str(msg)
        self.assertEqual(raw.count("OBR|"), 2)


class TestDeviceSpecificBuild(unittest.TestCase):

    def test_cellquant_orm(self):
        data = ORMData(
            patient_id="PAT001",
            placer_order_number="PLAC001",
            filler_order_number="FILL001",
            tests=[OrderedTest(code="58410-2", display="CBC")],
        )
        msg = build_orm_message(data, device_type="cellquant_bf_6900")
        self.assertIsInstance(msg, hl7.Message)
        # Should resolve 58410-2 to 1001 via panel mappings
        raw = str(msg)
        self.assertIn("1001", raw)


if __name__ == "__main__":
    unittest.main()
