"""Unit tests for the External HL7 proxy device profile."""

import unittest

from lab_analyzer_device.hl7.devices.external_hl7 import ExternalHL7Profile
from lab_analyzer_device.hl7.devices.registry import registry
from lab_analyzer_device.hl7.builder import ORMData, OrderedTest


class TestProperties(unittest.TestCase):

    def setUp(self):
        self.profile = ExternalHL7Profile()

    def test_device_type(self):
        self.assertEqual(self.profile.device_type, "external_hl7")

    def test_display_name(self):
        self.assertIn("External HL7", self.profile.display_name)

    def test_hl7_version(self):
        self.assertEqual(self.profile.hl7_version, "2.3")

    def test_result_message_type(self):
        self.assertEqual(self.profile.result_message_type, "ORU^R01")

    def test_order_message_type(self):
        self.assertEqual(self.profile.order_message_type, "ORM^O01")

    def test_communication_mode(self):
        self.assertEqual(self.profile.communication_mode, "download")

    def test_does_not_support_query_orders(self):
        self.assertFalse(self.profile.supports_query_orders)

    def test_no_code_or_panel_mappings(self):
        # LOINC-native: codes pass through unchanged.
        self.assertEqual(self.profile.code_mappings, {})
        self.assertEqual(self.profile.panel_mappings, {})


class TestRegistry(unittest.TestCase):

    def test_registered(self):
        profile = registry.get_profile("external_hl7")
        self.assertIsInstance(profile, ExternalHL7Profile)


class TestBuildOrderMessage(unittest.TestCase):

    def setUp(self):
        self.profile = ExternalHL7Profile()
        self.order = ORMData(
            patient_id="PT123",
            placer_order_number="PLAC1",
            filler_order_number="90001",
            patient_name="Jane Doe",
            date_of_birth="19900101",
            gender="F",
            tests=[
                OrderedTest(
                    code="58410-2",
                    display="CBC panel",
                    system="http://loinc.org",
                )
            ],
            specimen_id="90001",
        )

    def test_message_type_is_orm_o01(self):
        msg = self.profile.build_order_message(self.order)
        self.assertEqual(str(msg.segment("MSH")(9)), "ORM^O01")

    def test_pid_carries_name_dob_and_gender(self):
        msg = self.profile.build_order_message(self.order)
        pid = msg.segment("PID")
        self.assertEqual(str(pid(5)), "Doe^Jane")
        self.assertEqual(str(pid(7)), "19900101")
        self.assertEqual(str(pid(8)), "F")

    def test_obr_carries_loinc_code_and_sample_id(self):
        msg = self.profile.build_order_message(self.order)
        obr = msg.segment("OBR")
        self.assertEqual(str(obr(4)), "58410-2^CBC panel^http://loinc.org")
        self.assertEqual(str(obr(15)), "90001")

    def test_loinc_code_passes_through_unchanged(self):
        # No panel mappings: an arbitrary LOINC code must not raise.
        order = self.order.model_copy(
            update={"tests": [OrderedTest(code="789-8", display="RBC")]}
        )
        msg = self.profile.build_order_message(order)
        self.assertIn("789-8", str(msg.segment("OBR")(4)))


if __name__ == "__main__":
    unittest.main()
