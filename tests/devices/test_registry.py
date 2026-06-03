"""Unit tests for device profile registry."""

import unittest

from lab_analyzer_device.hl7.devices.registry import registry


class TestRegistry(unittest.TestCase):

    def test_get_all_profiles(self):
        profiles = registry.get_profiles()
        self.assertIn("generic", profiles)
        self.assertIn("horiba_yumizen_h500", profiles)
        self.assertIn("adx_heme_340", profiles)
        self.assertIn("adx_autochem_200", profiles)
        self.assertIn("cellquant_bf_6900", profiles)

    def test_get_known_profile(self):
        profile = registry.get_profile("adx_autochem_200")
        self.assertEqual(profile.device_type, "adx_autochem_200")

    def test_get_unknown_falls_back_to_generic(self):
        profile = registry.get_profile("nonexistent_device_xyz")
        self.assertEqual(profile.device_type, "generic")


if __name__ == "__main__":
    unittest.main()
