import tempfile
import unittest
from pathlib import Path

import app as picycle_web
import storage


class ProfileRouteTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmpdir.name) / "picycle.sqlite3"
        picycle_web.app.config.update(TESTING=True, PICYCLE_DB_PATH=self.db_path)
        self.client = picycle_web.app.test_client()

    def tearDown(self):
        picycle_web.app.config.pop("PICYCLE_DB_PATH", None)
        self.tmpdir.cleanup()

    def test_profiles_page_lists_active_profiles(self):
        with storage.open_database(self.db_path) as connection:
            storage.create_rider_profile(connection, "Eric")

        response = self.client.get("/profiles")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Eric", response.data)

    def test_new_profile_form_creates_profile(self):
        response = self.client.post(
            "/profiles/new",
            data={"display_name": "  Eric   P  "},
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Eric P", response.data)
        with storage.open_database(self.db_path) as connection:
            profiles = storage.list_rider_profiles(connection)
        self.assertEqual(profiles[0]["display_name"], "Eric P")

    def test_new_profile_rejects_blank_name(self):
        response = self.client.post("/profiles/new", data={"display_name": "   "})

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"cannot be blank", response.data)

    def test_new_profile_rejects_duplicate_active_name(self):
        with storage.open_database(self.db_path) as connection:
            storage.create_rider_profile(connection, "Eric")

        response = self.client.post("/profiles/new", data={"display_name": "eric"})

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"already exists", response.data)


if __name__ == "__main__":
    unittest.main()
