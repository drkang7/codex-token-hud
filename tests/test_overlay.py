import copy
from pathlib import Path
import tempfile
import time
import unittest

from dashboard import Dashboard
from metrics import atomic_json
from overlay_state import OverlayState, choose_thread, display_number, presentation
from test_history import all_time, response, write_log


def snapshot():
    now = time.time() * 1000
    return {"thread": {"id": "one", "title": "Synthetic conversation", "model": "demo-model"},
            "threads": [{"id": "one"}], "pinned_thread_id": "one",
            "live": {"source": {"state": "ok"}, "metrics": {"model": "demo-model", "stage": "idle",
                     "last": {"model": "demo-model", "rate": 125, "cache_percent": 75, "measured_at_ms": now}}}}


class OverlayTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.runtime = self.root / "runtime"
        self.service = Dashboard(self.root, self.runtime, native_enabled=True,
                                 native_follow_mode="activity", native_label="Linux 悬浮条")
        self.state = OverlayState(self.service)

    def tearDown(self):
        self.temp.cleanup()

    def test_latest_activity_and_exact_pin_and_unpin(self):
        write_log(self.root / "sessions/one.jsonl", response(0, 5, "a"), thread="one")
        write_log(self.root / "sessions/two.jsonl", response(10, 15, "b"), thread="two")
        self.assertEqual(self.state.snapshot()["thread"]["id"], "two")
        self.assertEqual(self.state.command("pin", "one")["thread"]["id"], "one")
        self.assertEqual(self.state.command("follow")["thread"]["id"], "two")

    def test_missing_pin_never_falls_back_and_can_be_unpinned(self):
        write_log(self.root / "sessions/one.jsonl", response(0, 5, "a"), thread="one")
        atomic_json(self.runtime / "manual-binding.json", {"thread_id": "removed"})
        result = self.state.snapshot()
        self.assertIsNone(result["thread"])
        self.assertEqual(presentation(result)["kind"], "missing")
        self.assertEqual(self.state.command("follow")["thread"]["id"], "one")

    def test_equal_activity_times_are_explicitly_ambiguous(self):
        threads = [{"id": "one", "updated_at_ms": 5}, {"id": "two", "updated_at_ms": 5}]
        self.assertIsNone(choose_thread(threads, None))
        self.assertEqual(choose_thread(threads, "two")["id"], "two")

    def test_external_dashboard_pin_and_range_sync_and_clear(self):
        write_log(self.root / "sessions/one.jsonl", response(0, 5, "a"), thread="one")
        self.service.post("pin", {"thread_id": "one"})
        self.service.post("range", {"thread_id": "one", "selection": all_time()})
        result = self.state.snapshot()
        view = presentation(result)
        self.assertTrue(view["range"])
        self.assertEqual((view["rate"], view["cache"]), ("20.0", "75.0"))
        self.assertFalse(presentation(self.state.command("latest", "one"))["range"])

    def test_force_refresh_rereads_existing_log_without_database(self):
        path = self.root / "sessions/one.jsonl"
        write_log(path, response(0, 5, "a"), thread="one")
        self.assertEqual(self.state.snapshot()["live"]["metrics"]["last"]["rate"], 20)
        write_log(path, response(0, 5, "b", output=200), thread="one")
        result = self.state.command("refresh")
        self.assertEqual(result["live"]["metrics"]["last"]["rate"], 40)

    def test_platform_metadata_keeps_windows_default(self):
        self.assertEqual(self.service.get("threads", {})["native_follow_mode"], "activity")
        self.assertEqual(self.service.get("threads", {})["native_label"], "Linux 悬浮条")
        win = Dashboard(self.root, self.runtime, native_enabled=True)
        self.assertEqual(win.get("threads", {})["native_follow_mode"], "desktop")
        self.assertEqual(win.get("threads", {})["native_label"], "Windows 状态栏")

    def test_previous_turn_and_model_and_unreadable_values_are_hidden(self):
        for change in ("model", "turn", "source"):
            data = snapshot()
            if change == "model":
                data["live"]["metrics"]["model"] = "other-model"
            elif change == "turn":
                data["live"]["metrics"].update(stage="generating", turn_started_at_ms=time.time() * 1000 + 1)
            else:
                data["live"]["source"]["state"] = "missing"
            view = presentation(data)
            self.assertEqual((view["rate"], view["cache"]), ("—", "—"), change)

    def test_stale_and_future_samples_are_hidden_but_confirmed_range_is_retained(self):
        data = snapshot()
        sample = data["live"]["metrics"]["last"]
        self.assertEqual(presentation(data, sample["measured_at_ms"])["rate"], "125.0")
        for offset in (900000, -61000):
            self.assertEqual(presentation(data, sample["measured_at_ms"] + offset)["rate"], "—")
        data["live"]["range"] = {"thread_id": "one", "rate": 20, "cache_percent": 50, "sample_count": 2}
        self.assertEqual(presentation(data, sample["measured_at_ms"] + 900000)["rate"], "20.0")
        data["live"]["range"]["thread_id"] = "different"
        self.assertFalse(presentation(data)["range"])

    def test_invalid_numbers_and_error_snapshots_never_look_measured(self):
        for value in (None, "75", True, float("nan"), float("inf")):
            self.assertEqual(display_number(value), "—")
        data = copy.deepcopy(snapshot())
        data["error"] = "synthetic error"
        self.assertEqual(presentation(data)["rate"], "—")


if __name__ == "__main__":
    unittest.main()
