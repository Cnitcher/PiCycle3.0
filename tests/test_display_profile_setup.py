import unittest
from unittest.mock import patch

from display.base_240x320 import DisplayBase


class DisplayProfileSetupTests(unittest.TestCase):
    def setUp(self):
        self.display = DisplayBase.__new__(DisplayBase)
        self.display._local_ip = lambda: "192.168.1.238"

    @patch("display.base_240x320.read_settings")
    def test_profile_setup_url_uses_configured_web_port(self, read_settings):
        read_settings.return_value = {"globals": {"ui_port": 8000}}

        self.assertEqual(
            self.display._profile_setup_url(),
            "http://192.168.1.238:8000/profiles/new",
        )

    @patch("display.base_240x320.read_settings")
    def test_profile_setup_url_defaults_to_deployed_web_port(self, read_settings):
        read_settings.return_value = {"globals": {}}

        self.assertEqual(
            self.display._profile_setup_url(),
            "http://192.168.1.238:8000/profiles/new",
        )


if __name__ == "__main__":
    unittest.main()
