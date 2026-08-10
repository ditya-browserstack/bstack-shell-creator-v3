import json
import tempfile
import unittest
import sys
from datetime import date
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL_DIR / "lib"))

import ledger  # noqa: E402


class TestLoadSave(unittest.TestCase):
    """The ledger is a directory of one-fact files so concurrent runs can merge."""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp()) / "ledger"

    def test_load_missing_returns_empty_ledger(self):
        data = ledger.load(self.root)
        self.assertEqual(data["last_run"], None)
        self.assertEqual(data["features"], [])
        self.assertEqual(data["version"], ledger.VERSION)

    def test_save_then_load_round_trips(self):
        ledger.save({"last_run": "2026-08-04", "features": []}, self.root)
        self.assertEqual(ledger.load(self.root)["last_run"], "2026-08-04")

    def test_one_file_per_feature(self):
        """The whole point: two features never share a path, so git cannot conflict."""
        ledger.save({"last_run": "2026-08-04", "features": [
            {"lcam_id": "LCAM-1", "name": "Alpha"},
            {"lcam_id": "LCAM-2", "name": "Beta"},
        ]}, self.root)
        files = sorted(p.name for p in (self.root / ledger.FEATURES_DIR).glob("*.json"))
        self.assertEqual(files, ["lcam-1-alpha.json", "lcam-2-beta.json"])

    def test_one_file_per_run_day(self):
        ledger.save({"last_run": "2026-08-04", "features": []}, self.root)
        ledger.save({"last_run": "2026-08-05", "features": []}, self.root)
        runs = sorted(p.stem for p in (self.root / ledger.RUNS_DIR).glob("*.json"))
        self.assertEqual(runs, ["2026-08-04", "2026-08-05"])

    def test_last_run_is_the_newest_run_file(self):
        for d in ("2026-07-28", "2026-08-05", "2026-08-01"):
            ledger.save({"last_run": d, "features": []}, self.root)
        self.assertEqual(ledger.load(self.root)["last_run"], "2026-08-05")

    def test_a_run_that_ships_nothing_still_advances_the_window(self):
        """Derived-from-features would freeze the window on an empty week."""
        ledger.save({"last_run": "2026-08-05", "features": []}, self.root)
        self.assertEqual(ledger.load(self.root)["last_run"], "2026-08-05")

    def test_recording_the_same_feature_twice_reuses_one_path(self):
        """Two checkouts recording the same feature must not both survive a merge."""
        f = {"lcam_id": "LCAM-1", "name": "Alpha", "run_date": "2026-08-04"}
        ledger.save({"last_run": "2026-08-04", "features": [f]}, self.root)
        ledger.save({"last_run": "2026-08-05", "features": [dict(f, surface="x")]}, self.root)
        files = list((self.root / ledger.FEATURES_DIR).glob("*.json"))
        self.assertEqual(len(files), 1)

    def test_features_load_in_a_deterministic_order(self):
        ledger.save({"last_run": None, "features": [
            {"lcam_id": "LCAM-9", "name": "Zulu"},
            {"lcam_id": "LCAM-1", "name": "Alpha"},
        ]}, self.root)
        names = [f["name"] for f in ledger.load(self.root)["features"]]
        self.assertEqual(names, ["Alpha", "Zulu"])

    def test_filenames_are_filesystem_safe(self):
        ledger.save({"last_run": None, "features": [
            {"lcam_id": "LCAM-2580", "name": 'Service accounts \u2014 "Ran with"/column'},
        ]}, self.root)
        name = next((self.root / ledger.FEATURES_DIR).glob("*.json")).name
        for bad in ('/', '"', '\\', ' '):
            self.assertNotIn(bad, name)


class TestLegacyFallback(unittest.TestCase):
    """A teammate who has not pulled the migration still gets a readable ledger."""

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.root = self.dir / "ledger"
        (self.dir / ledger.LEGACY_NAME).write_text(json.dumps({
            "version": 1, "last_run": "2026-08-04",
            "features": [{"lcam_id": "LCAM-1", "name": "Alpha"}],
        }), encoding="utf-8")

    def test_reads_a_legacy_single_file_ledger(self):
        data = ledger.load(self.root)
        self.assertEqual(data["last_run"], "2026-08-04")
        self.assertEqual(len(data["features"]), 1)
        self.assertTrue(data["legacy"])

    def test_migrate_converts_without_deleting_the_original(self):
        result = ledger.migrate(self.root)
        self.assertEqual(result["features"], 1)
        self.assertTrue((self.dir / ledger.LEGACY_NAME).is_file())
        self.assertEqual(ledger.load(self.root)["last_run"], "2026-08-04")

    def test_the_new_layout_wins_once_it_exists(self):
        ledger.save({"last_run": "2026-08-09", "features": []}, self.root)
        self.assertEqual(ledger.load(self.root)["last_run"], "2026-08-09")

    def test_migrate_is_a_noop_without_a_legacy_file(self):
        self.assertIsNone(ledger.migrate(Path(tempfile.mkdtemp()) / "ledger"))


class TestShipped(unittest.TestCase):
    """The ledger on *this* machine, whatever it happens to hold.

    A fresh install has no ledger at all, which is the correct state and not a
    failure -- so this checks the file is readable and internally consistent
    rather than asserting anybody's feature count.
    """

    def test_installed_ledger_loads(self):
        data = ledger.load()
        self.assertIn("features", data)
        self.assertIsInstance(data["features"], list)

    def test_a_populated_ledger_records_when_it_last_ran(self):
        data = ledger.load()
        if not data["features"]:
            self.skipTest("no features recorded yet — nothing has been synced here")
        self.assertTrue(data["last_run"])


class TestWindow(unittest.TestCase):
    def test_first_run_uses_default_window(self):
        data = {"version": 1, "last_run": None, "features": []}
        self.assertEqual(
            ledger.window_start(data, 7, date(2026, 8, 4)), "2026-07-28"
        )

    def test_subsequent_run_uses_last_run(self):
        data = {"version": 1, "last_run": "2026-07-30", "features": []}
        self.assertEqual(
            ledger.window_start(data, 7, date(2026, 8, 4)), "2026-07-30"
        )

    def test_window_is_not_negative_when_last_run_is_future(self):
        data = {"version": 1, "last_run": "2026-09-01", "features": []}
        self.assertEqual(
            ledger.window_start(data, 7, date(2026, 8, 4)), "2026-08-04"
        )


class TestRecord(unittest.TestCase):
    def test_record_appends_feature(self):
        data = {"version": 1, "last_run": None, "features": []}
        ledger.record(data, {
            "lcam_id": "LCAM-2580",
            "name": "Service accounts",
            "surface": "list",
            "insertion": "catalog:Device",
            "run_date": "2026-08-04",
        })
        self.assertEqual(len(data["features"]), 1)
        self.assertEqual(data["features"][0]["lcam_id"], "LCAM-2580")

    def test_record_is_idempotent_per_lcam_and_name(self):
        data = {"version": 1, "last_run": None, "features": []}
        feature = {
            "lcam_id": "LCAM-2580",
            "name": "Service accounts",
            "surface": "list",
            "insertion": "catalog:Device",
            "run_date": "2026-08-04",
        }
        ledger.record(data, feature)
        ledger.record(data, dict(feature))
        self.assertEqual(len(data["features"]), 1)

    def test_added_feature_keys(self):
        data = {"version": 1, "last_run": None, "features": [
            {"lcam_id": "LCAM-1", "name": "Alpha"},
            {"lcam_id": "LCAM-2", "name": "Beta"},
        ]}
        self.assertEqual(
            ledger.added_feature_keys(data), ["LCAM-1:alpha", "LCAM-2:beta"]
        )


if __name__ == "__main__":
    unittest.main()
