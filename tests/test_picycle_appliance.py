import unittest

from picycle_appliance import PROGRAMS, PiCycleAppliance


class PiCycleApplianceTests(unittest.TestCase):
    def flush_press(self, app, now):
        app.update_metrics({}, now=now + 0.31)

    def test_program_menu_only_contains_current_programs(self):
        self.assertEqual(PROGRAMS, ["Tabata", "Swedish 4x4"])

    def test_tabata_setup_uses_ten_second_steps_and_twenty_round_max(self):
        app = PiCycleAppliance()
        app.view = "tabata_setup"
        app.selected = 0
        app.tabata_config["warmupSec"] = 0
        app.rotate(-1)
        self.assertEqual(app.tabata_config["warmupSec"], 0)

        app.selected = 1
        app.tabata_config["hotSec"] = 10
        app.rotate(-1)
        self.assertEqual(app.tabata_config["hotSec"], 10)
        app.rotate(1)
        self.assertEqual(app.tabata_config["hotSec"], 20)

        app.selected = 3
        app.tabata_config["rounds"] = 16
        app.rotate(1)
        self.assertEqual(app.tabata_config["rounds"], 20)

    def test_tabata_warmup_is_round_zero(self):
        app = PiCycleAppliance()
        app.tabata_config["warmupSec"] = 30
        app.elapsed = 5
        phase = app.tabata_phase()
        self.assertEqual(phase.name, "Warmup")
        self.assertEqual(phase.round, 0)

    def test_swedish_four_by_four_phase_timing(self):
        app = PiCycleAppliance()
        app.swedish_config["warmupSec"] = 10
        app.elapsed = 10
        phase = app.swedish_phase()
        self.assertEqual(phase.name, "Hard")
        self.assertEqual(phase.round, 1)
        self.assertEqual(phase.remaining, 240)

        app.elapsed = 250
        phase = app.swedish_phase()
        self.assertEqual(phase.name, "Recover")
        self.assertEqual(phase.round, 1)

        app.elapsed = 430
        phase = app.swedish_phase()
        self.assertEqual(phase.name, "Hard")
        self.assertEqual(phase.round, 2)

    def test_review_single_press_returns_to_history(self):
        app = PiCycleAppliance(rides=[{"id": "ride-1", "durationSec": 10}])
        app.view = "review"
        app.active_review_id = "ride-1"
        app.press(now=1.0)
        self.assertEqual(app.view, "history")

    def test_review_delete_no_returns_to_ride_review(self):
        app = PiCycleAppliance(rides=[{"id": "ride-1", "durationSec": 10}])
        app.view = "review"
        app.active_review_id = "ride-1"
        app.selected = 1

        app.press(now=1.0)
        self.assertEqual(app.view, "delete_confirm")
        self.assertEqual(app.selected_label(), "No")

        app.press(now=1.1)
        self.assertEqual(app.view, "review")
        self.assertEqual(app.active_review()["id"], "ride-1")
        self.assertEqual(app.rides[0]["id"], "ride-1")
        self.assertIsNone(app.pop_deleted_ride_id())

    def test_review_delete_yes_removes_ride_and_returns_to_history(self):
        app = PiCycleAppliance(
            rides=[
                {"id": "ride-1", "durationSec": 10},
                {"id": "ride-2", "durationSec": 20},
            ]
        )
        app.view = "review"
        app.active_review_id = "ride-1"
        app.selected = 1

        app.press(now=1.0)
        app.rotate(1)
        app.press(now=1.1)

        self.assertEqual(app.view, "history")
        self.assertEqual([ride["id"] for ride in app.rides], ["ride-2"])
        self.assertEqual(app.pop_deleted_ride_id(), "ride-1")

    def test_save_and_end_records_ride_and_returns_to_menu(self):
        app = PiCycleAppliance()
        app._start_ride("Swedish 4x4", "swedish")
        app.elapsed = 60
        app.distance = 0.2
        app.avg_speed = 12.0
        app.calories = 5.5
        app.pace_history = [0, 4, 5]
        app.speed_history = [0, 12, 13]
        app.view = "pause"
        app.selected = 1
        app.press(now=1.0)
        self.flush_press(app, 1.0)

        self.assertEqual(app.view, "menu")
        self.assertEqual(app.rides[0]["label"], "Swedish 4x4")
        self.assertEqual(app.rides[0]["structure"]["hardSec"], 240)
        self.assertIsNotNone(app.pop_saved_ride())


if __name__ == "__main__":
    unittest.main()
