import unittest

from effort import echo_machine_calories_per_minute, echo_watts_from_rpm


class EchoStyleEffortTests(unittest.TestCase):
    def test_stopped_bike_has_no_power_or_calories(self):
        self.assertEqual(echo_watts_from_rpm(0), 0.0)
        self.assertEqual(echo_machine_calories_per_minute(0), 0.0)

    def test_easy_effort_matches_echo_style_reference_point(self):
        self.assertAlmostEqual(echo_watts_from_rpm(50), 151.79, places=2)
        self.assertAlmostEqual(echo_machine_calories_per_minute(50), 7.59, places=2)

    def test_calorie_pace_rises_non_linearly_with_cadence(self):
        easy = echo_machine_calories_per_minute(50)
        moderate = echo_machine_calories_per_minute(60)
        hard = echo_machine_calories_per_minute(70)

        self.assertAlmostEqual(moderate, 12.28, places=2)
        self.assertAlmostEqual(hard, 18.61, places=2)
        self.assertGreater(hard - moderate, moderate - easy)


if __name__ == "__main__":
    unittest.main()
