"""Unit tests for Sysmex XP-300 ASTM device profile."""

import unittest

from lab_analyzer_device.astm.devices.sysmex_xp_300 import SysmexXP300Profile
from lab_analyzer_device.astm.extractor import extract_astm_data

# O-3 component 2 carries the on-screen Sample ID (O-2 is empty on XP-300).
SYSMEX_XP_300_RECORDS = [
    r"H|\^&|||XP-300^00-16^^^^C2524^AK007119||||||||E1394-97",
    "P|1",
    (
        "O|1||^^     12345^|^^^^WBC\\^^^^RBC\\^^^^HGB\\^^^^HCT\\^^^^MCV\\^^^^MCH\\"
        "^^^^MCHC\\^^^^PLT\\^^^^LYM%\\^^^^MXD%\\^^^^NEUT%\\^^^^LYM#\\^^^^MXD#\\^^^^NEUT#\\"
        "^^^^RDW-SD\\^^^^RDW-CV\\^^^^PDW\\^^^^MPV\\^^^^P-LCR\\^^^^PCT|||||||N||||||||||||||F"
    ),
    "R|1|^^^^WBC^1|  8.5|10*3/uL||N||||               ||20260610095105",
    "R|2|^^^^RBC^1| 3.52|10*6/uL||N||||               ||20260610095105",
    "R|3|^^^^HGB^1|  5.4|g/dL||L||||               ||20260610095105",
    "R|4|^^^^HCT^1| 22.0|%||L||||               ||20260610095105",
    "R|5|^^^^MCV^1| 62.5|fL||L||||               ||20260610095105",
    "R|6|^^^^MCH^1| 15.3|pg||L||||               ||20260610095105",
    "R|7|^^^^MCHC^1| 24.5|g/dL||L||||               ||20260610095105",
    "R|8|^^^^PLT^1|  284|10*3/uL||N||||               ||20260610095105",
    "R|9|^^^^LYM%^1| 21.4|%||N||||               ||20260610095105",
    "R|10|^^^^MXD%^1|  6.1|%||N||||               ||20260610095105",
    "R|11|^^^^NEUT%^1| 72.5|%||N||||               ||20260610095105",
    "R|12|^^^^LYM#^1|  1.8|10*3/uL||N||||               ||20260610095105",
    "R|13|^^^^MXD#^1|  0.5|10*3/uL||N||||               ||20260610095105",
    "R|14|^^^^NEUT#^1|  6.2|10*3/uL||N||||               ||20260610095105",
    "R|15|^^^^RDW-SD^1| 39.2|fL||N||||               ||20260610095105",
    "R|16|^^^^RDW-CV^1| 17.2|%||H||||               ||20260610095105",
    "R|17|^^^^PDW^1| 11.0|fL||N||||               ||20260610095105",
    "R|18|^^^^MPV^1|  8.4|fL||L||||               ||20260610095105",
    "R|19|^^^^P-LCR^1| 16.5|%||N||||               ||20260610095105",
    "R|20|^^^^PCT^1| 0.24|%||N||||               ||20260610095105",
    "L|1|N",
]


class TestProperties(unittest.TestCase):
    def setUp(self):
        self.profile = SysmexXP300Profile()

    def test_device_type(self):
        self.assertEqual(self.profile.device_type, "sysmex_xp_300")

    def test_communication_mode(self):
        self.assertEqual(self.profile.communication_mode, "unidirectional")

    def test_astm_connection_mode(self):
        self.assertEqual(self.profile.astm_connection_mode, "inbound")

    def test_default_oru_port(self):
        self.assertEqual(self.profile.default_oru_port, 5006)

    def test_serial_defaults(self):
        self.assertEqual(self.profile.default_baud_rate, 9600)
        self.assertEqual(self.profile.default_data_bits, 8)
        self.assertEqual(self.profile.default_parity, "N")
        self.assertEqual(self.profile.default_stop_bits, 1)
        self.assertEqual(self.profile.default_flow_control, "none")


class TestMetadataExposure(unittest.TestCase):
    def test_serial_default_fields_for_metadata_api(self):
        profile = SysmexXP300Profile()
        fields = profile.serial_default_fields()
        self.assertEqual(fields["default_baud_rate"], 9600)
        self.assertEqual(fields["default_data_bits"], 8)
        self.assertEqual(fields["default_parity"], "N")
        self.assertEqual(fields["default_stop_bits"], 1)
        self.assertEqual(fields["default_flow_control"], "none")


class TestExtraction(unittest.TestCase):
    def test_sample_id_from_o_field_3(self):
        data = extract_astm_data(SYSMEX_XP_300_RECORDS, "sysmex_xp_300")
        self.assertEqual(data.sample_id, "12345")
        self.assertEqual(data.specimen_id, "12345")
        self.assertEqual(data.placer_order_number, "12345")

    def test_numeric_sample_id_from_o_field_2(self):
        records = [
            r"H|\^&|||XP-300",
            "P|1",
            "O|1|12345||^^^^WBC",
            "R|1|^^^^WBC^1|8.5|10*3/uL||N||F",
            "L|1|N",
        ]
        data = extract_astm_data(records, "sysmex_xp_300")
        self.assertEqual(data.sample_id, "12345")
        self.assertEqual(data.specimen_id, "12345")
        self.assertEqual(data.placer_order_number, "12345")

    def test_observation_count(self):
        data = extract_astm_data(SYSMEX_XP_300_RECORDS, "sysmex_xp_300")
        self.assertEqual(len(data.observations), 20)

    def test_wbc_mapped_to_loinc(self):
        data = extract_astm_data(SYSMEX_XP_300_RECORDS, "sysmex_xp_300")
        wbc = data.observations[0]
        self.assertEqual(wbc.code, "6690-2")
        self.assertEqual(wbc.value, "8.5")
        self.assertEqual(wbc.units, "10*3/uL")
        self.assertEqual(wbc.abnormal_flags, "N")
        self.assertEqual(wbc.observation_datetime, "20260610095105")

    def test_abnormal_flags_preserved(self):
        data = extract_astm_data(SYSMEX_XP_300_RECORDS, "sysmex_xp_300")
        by_code = {obs.code: obs for obs in data.observations}
        self.assertEqual(by_code["718-7"].abnormal_flags, "L")
        self.assertEqual(by_code["788-0"].abnormal_flags, "H")

    def test_p_lcr_mapped_to_loinc(self):
        data = extract_astm_data(SYSMEX_XP_300_RECORDS, "sysmex_xp_300")
        plcr = [obs for obs in data.observations if obs.code == "48386-7"]
        self.assertEqual(len(plcr), 1)
        self.assertEqual(plcr[0].value, "16.5")


class TestQCSkip(unittest.TestCase):
    def test_validation_sample_zero_is_skipped(self):
        profile = SysmexXP300Profile()
        records = [
            r"H|\^&|||XP-300",
            "P|1",
            "O|1|0||^^^WBC",
            "R|1|^^^^WBC^1|7.5|10*3/uL||N||F",
            "L|1|N",
        ]
        data = extract_astm_data(records, "sysmex_xp_300")
        self.assertTrue(profile.should_skip_result(data))
