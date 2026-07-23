import json
import math
import unittest
from pathlib import Path

from speed_input.speed_input_base import SpeedBase


class SpeedInputMathTests(unittest.TestCase):
    def test_distance_factor_uses_circumference_not_area(self):
        speed = SpeedBase(radius=13.0)

        expected_miles_per_rev = (2 * math.pi * 13.0) / 12.0 / 5280.0
        self.assertAlmostEqual(speed.dist_factor, expected_miles_per_rev)

    def test_distance_factor_supports_sensor_and_gearing_calibration(self):
        speed = SpeedBase(radius=13.0, pulses_per_rev=2, distance_multiplier=0.5)

        expected_miles_per_pulse = (2 * math.pi * 13.0) / 12.0 / 5280.0 / 4
        self.assertAlmostEqual(speed.dist_factor, expected_miles_per_pulse)

    def test_cadence_uses_configured_sensor_pulses_per_crank_revolution(self):
        speed = SpeedBase(radius=13.0, cadence_pulses_per_rev=5)

        self.assertAlmostEqual(speed._calc_cadence_rpm(25, 6), 50.0)

    def test_default_calibration_maps_observed_easy_speed_to_target(self):
        root = Path(__file__).resolve().parents[1]
        settings = json.loads((root / "settings.json").read_text(encoding="utf-8"))
        multiplier = settings["globals"]["speed_distance_multiplier"]

        self.assertAlmostEqual(20.0 * multiplier, 11.0)
        self.assertEqual(settings["globals"]["sensor_pulses_per_crank_rev"], 5.0)


if __name__ == "__main__":
    unittest.main()
