import math
import unittest

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


if __name__ == "__main__":
    unittest.main()
