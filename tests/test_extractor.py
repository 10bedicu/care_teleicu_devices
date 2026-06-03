"""Unit tests for lab_analyzer_device.hl7.extractor module."""

import unittest

import hl7

from lab_analyzer_device.hl7.extractor import ObservationData, ORUData, _str


class TestStrHelper(unittest.TestCase):
    """Tests for the _str() safe field extraction helper."""

    def setUp(self):
        raw = "MSH|^~\\&|SENDER|FAC|||20250101||ORU^R01|1|P|2.3\rPID|1||PAT001|||Doe^John||19900101\rOBX|1|NM|WBC^White Blood Cells^LN||7.2|10^3/uL|4-10|N|||F"
        self.message = hl7.parse(raw)

    def test_extract_simple_field(self):
        msh = self.message.segment("MSH")
        self.assertEqual(_str(msh, 3), "SENDER")
        self.assertEqual(_str(msh, 4), "FAC")

    def test_extract_component(self):
        obx = self.message.segment("OBX")
        self.assertEqual(_str(obx, 3, 1), "WBC")
        self.assertEqual(_str(obx, 3, 2), "White Blood Cells")
        self.assertEqual(_str(obx, 3, 3), "LN")

    def test_out_of_bounds_field_returns_empty(self):
        msh = self.message.segment("MSH")
        self.assertEqual(_str(msh, 99), "")

    def test_out_of_bounds_component_returns_empty(self):
        obx = self.message.segment("OBX")
        self.assertEqual(_str(obx, 3, 10), "")

    def test_empty_field_returns_empty(self):
        pid = self.message.segment("PID")
        self.assertEqual(_str(pid, 4), "")

    def test_numeric_field_as_string(self):
        obx = self.message.segment("OBX")
        self.assertEqual(_str(obx, 1), "1")
        self.assertEqual(_str(obx, 5), "7.2")


class TestORUDataModel(unittest.TestCase):
    """Tests for the ORUData dataclass."""

    def test_default_values(self):
        data = ORUData()
        self.assertIsNone(data.patient_id)
        self.assertIsNone(data.specimen_id)
        self.assertEqual(data.observations, [])

    def test_with_observations(self):
        obs = ObservationData(
            set_id=1,
            value_type="NM",
            code="6690-2",
            display="WBC",
            system="http://loinc.org",
            value="7.2",
            units="10^3/uL",
            reference_range="4-10",
            abnormal_flags="N",
            result_status="F",
        )
        data = ORUData(observations=[obs])
        self.assertEqual(len(data.observations), 1)
        self.assertEqual(data.observations[0].value, "7.2")


if __name__ == "__main__":
    unittest.main()
