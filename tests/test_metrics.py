import datetime as dt
import json
from pathlib import Path
import sys
import tempfile
import unittest
import sqlite3
import subprocess
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from metrics import Measurements, SessionTail, TailCache, ThreadRepository, cache_percent


def event(seconds, kind, payload):
    at = dt.datetime.fromtimestamp(1700000000 + seconds, dt.timezone.utc).isoformat()
    return {"timestamp": at, "type": kind, "payload": payload}


def usage(output=100, cached=750, input_tokens=1000):
    return {"input_tokens": input_tokens, "cached_input_tokens": cached,
            "output_tokens": output, "reasoning_output_tokens": 30}


class MeasurementsTest(unittest.TestCase):
    def test_model_stream_timing_excludes_prefill_and_tools(self):
        m = Measurements("example-model")
        m.feed(event(0, "event_msg", {"type": "task_started", "turn_id": "t"}))
        m.feed(event(5, "event_msg", {"type": "item_completed", "item": {"type": "Reasoning"},
                "started_at_ms": 1700000002000, "completed_at_ms": 1700000005000}))
        m.feed(event(6, "response_item", {"type": "custom_tool_call", "call_id": "c"}))
        m.feed(event(7, "token_usage_record", {"response_id": "r", "usage": usage(100)}))
        self.assertEqual(m.last["rate"], 20)
        self.assertEqual(m.last["basis"], "stream")
        m.feed(event(107, "response_item", {"type": "custom_tool_call_output", "call_id": "c"}))
        m.feed(event(110, "event_msg", {"type": "item_completed", "item": {"type": "AgentMessage"},
                "started_at_ms": 1700000108000, "completed_at_ms": 1700000110000}))
        m.feed(event(112, "token_usage_record", {"response_id": "r2", "usage": usage(80)}))
        self.assertEqual(m.last["rate"], 20)
        self.assertEqual(m.output_total, 180)
        self.assertEqual(m.last["cache_percent"], 75)

    def test_record_followed_by_token_count_does_not_double_count(self):
        m = Measurements()
        m.feed(event(0, "event_msg", {"type": "task_started"}))
        p = {"response_id": "r", "usage": usage(), "thread_token_usage": {"output_tokens": 100}}
        m.feed(event(5, "token_usage_record", p))
        m.feed(event(7, "event_msg", {"type": "token_count", "info": {
            "last_token_usage": usage(), "total_token_usage": {"output_tokens": 100},
            "model_context_window": 2000}}))
        self.assertEqual(m.sample_count, 1)
        self.assertEqual(m.last["rate"], 20)

    def test_equal_usage_in_distinct_responses_counts_twice(self):
        m = Measurements()
        m.feed(event(0, "event_msg", {"type": "task_started"}))
        m.feed(event(5, "token_usage_record", {"response_id": "r1", "usage": usage()}))
        m.feed(event(10, "token_usage_record", {"response_id": "r2", "usage": usage()}))
        self.assertEqual(m.output_total, 200)
        self.assertEqual(m.sample_count, 2)

    def test_duplicate_response_id_is_ignored(self):
        m = Measurements()
        m.feed(event(0, "event_msg", {"type": "task_started"}))
        p = {"response_id": "r", "usage": usage()}
        m.feed(event(5, "token_usage_record", p))
        m.feed(event(6, "token_usage_record", p))
        self.assertEqual(m.output_total, 100)

    def test_delayed_legacy_notification_with_different_totals_is_not_a_new_sample(self):
        m = Measurements()
        m.feed(event(0, "event_msg", {"type": "task_started"}))
        m.feed(event(5, "token_usage_record", {"response_id": "r", "usage": usage(),
                "thread_token_usage": {"output_tokens": 10000}}))
        m.feed(event(25, "event_msg", {"type": "token_count", "info": {
            "last_token_usage": usage(), "total_token_usage": {"output_tokens": 1000}}}))
        self.assertEqual(m.sample_count, 1)
        self.assertEqual(m.last["rate"], 20)

    def test_legacy_counter_reset_after_resume_keeps_updating(self):
        m = Measurements()
        m.feed(event(0, "event_msg", {"type": "task_started"}))
        m.feed(event(5, "token_usage_record", {"response_id": "r", "usage": usage(),
                "thread_token_usage": {"output_tokens": 10000}}))
        m.feed(event(6, "event_msg", {"type": "token_count", "info": {
            "last_token_usage": usage(), "total_token_usage": {"output_tokens": 1000}}}))
        m.feed(event(10, "event_msg", {"type": "task_started", "turn_id": "new"}))
        m.feed(event(15, "event_msg", {"type": "token_count", "info": {
            "last_token_usage": usage(200), "total_token_usage": {"output_tokens": 200}}}))
        self.assertEqual(m.last["rate"], 40)
        self.assertEqual(m.last["turn_id"], "new")

    def test_identical_legacy_usage_with_increased_total_is_a_new_response(self):
        m = Measurements()
        m.feed(event(0, "event_msg", {"type": "task_started"}))
        for seconds, output in ((3, 100), (6, 200)):
            m.feed(event(seconds, "event_msg", {"type": "token_count", "info": {
                "last_token_usage": usage(), "total_token_usage": {"output_tokens": output}}}))
        self.assertEqual(m.sample_count, 2)
        self.assertEqual(m.output_total, 200)

    def test_missing_timing_stays_unknown(self):
        m = Measurements()
        m.feed(event(5, "token_usage_record", {"response_id": "r", "usage": usage()}))
        self.assertIsNone(m.last["rate"])
        self.assertEqual(m.last["cache_percent"], 75)

    def test_cache_has_correct_denominator_and_missing_is_unknown(self):
        self.assertIsNone(cache_percent({"input_tokens": 1000, "cached_input_tokens": None}))
        self.assertEqual(cache_percent(usage(input_tokens=200, cached=150)), 75)
        self.assertEqual(cache_percent(usage(input_tokens=100, cached=0)), 0)
        self.assertIsNone(cache_percent(usage(input_tokens=0)))
        self.assertIsNone(cache_percent(usage(input_tokens=100, cached=110)))
        self.assertIsNone(cache_percent({"input_tokens": 100}))

    def test_tail_handles_split_utf8_and_partial_json_without_replaying(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "session.jsonl"
            start = (json.dumps(event(0, "event_msg", {"type": "task_started"})) + "\n").encode()
            end = (json.dumps(event(5, "token_usage_record", {"response_id": "r", "usage": usage(),
                                "ignored": "中文"}), ensure_ascii=False) + "\n").encode()
            split = end.index("中".encode()) + 1
            path.write_bytes(start + end[:split])
            tail = SessionTail(str(path))
            tail.update()
            self.assertIsNone(tail.measurements.last)
            with path.open("ab") as f:
                f.write(end[split:])
            tail.update()
            tail.update()
            self.assertEqual(tail.measurements.output_total, 100)
            self.assertEqual(tail.measurements.last["rate"], 20)

    def test_visible_chat_name_is_used_and_duplicate_names_are_not_guessed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with sqlite3.connect(root / "state_5.sqlite") as c:
                c.execute("CREATE TABLE threads (id TEXT, title TEXT, name TEXT, rollout_path TEXT, model TEXT, updated_at INT, archived INT)")
                c.executemany("INSERT INTO threads VALUES (?,?,?,?,?,?,?)", [
                    ("a", "long first user message", "当前对话", "a.jsonl", "model-a", 1, 0),
                    ("b", "another first user message", "同名对话", "b.jsonl", "model-b", 2, 0),
                    ("c", "third first user message", "同名对话", "c.jsonl", "model-c", 3, 0),
                ])
            c.close()
            repo = ThreadRepository(root)
            repo.refresh()
            self.assertEqual(repo.title_matches("当前对话")[0]["id"], "a")
            self.assertEqual(len(repo.title_matches("同名对话")), 2)
            self.assertEqual(repo.title_matches("long first user message"), [])

    def test_database_version_discovery_and_legacy_optional_columns(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for version in (4, 6):
                with sqlite3.connect(root / f"state_{version}.sqlite") as c:
                    c.execute("CREATE TABLE threads (id TEXT, title TEXT, rollout_path TEXT)")
                    c.execute("INSERT INTO threads VALUES (?,?,?)", (str(version), "old layout", "fixture.jsonl"))
                c.close()
            repo = ThreadRepository(root); repo.refresh()
            self.assertEqual(repo.database.name, "state_6.sqlite")
            self.assertEqual(repo.title_matches("old layout")[0]["id"], "6")
            self.assertIsNone(repo.rows["6"]["model"])

    def test_database_migration_is_detected_while_repository_is_running(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repo = ThreadRepository(root); repo.refresh()
            self.assertEqual(repo.state, "missing")
            for version in (5, 7):
                with sqlite3.connect(root / f"state_{version}.sqlite") as c:
                    c.execute("CREATE TABLE threads (id TEXT, title TEXT, rollout_path TEXT)")
                    c.execute("INSERT INTO threads VALUES (?,?,?)", (str(version), "chat", "fixture.jsonl"))
                c.close()
                repo.refresh()
                self.assertEqual(repo.database.name, f"state_{version}.sqlite")
                self.assertEqual(repo.state, "ok")

    def test_incompatible_newer_database_does_not_fall_back_to_stale_metadata(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with sqlite3.connect(root / "state_5.sqlite") as c:
                c.execute("CREATE TABLE threads (id TEXT, title TEXT, rollout_path TEXT)")
                c.execute("INSERT INTO threads VALUES ('t', 'chat', 'old.jsonl')")
            c.close()
            with sqlite3.connect(root / "state_7.sqlite") as c:
                c.execute("CREATE TABLE threads (incompatible TEXT)")
            c.close()
            repo = ThreadRepository(root); repo.refresh()
            self.assertEqual(repo.state, "unsupported")
            self.assertEqual(repo.title_matches("chat"), [])

    def test_missing_and_incompatible_database_clear_previous_rows_without_creating_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            db = root / "state_5.sqlite"
            with sqlite3.connect(db) as c:
                c.execute("CREATE TABLE threads (id TEXT, title TEXT, rollout_path TEXT)")
                c.execute("INSERT INTO threads VALUES ('t', 'chat', 'fixture.jsonl')")
            c.close()
            repo = ThreadRepository(root); repo.refresh()
            self.assertEqual(len(repo.rows), 1)
            db.unlink(); repo.refresh()
            self.assertEqual(repo.state, "missing")
            self.assertEqual(repo.title_matches("chat"), [])
            self.assertFalse(db.exists())
            with sqlite3.connect(root / "state_7.sqlite") as c:
                c.execute("CREATE TABLE threads (unrelated TEXT)")
            c.close()
            repo.refresh()
            self.assertEqual(repo.state, "unsupported")
            self.assertEqual(repo.rows, {})

    @staticmethod
    def write_log(path, response_id, output=100, padding=""):
        events = [event(0, "event_msg", {"type": "task_started"}),
                  event(5, "token_usage_record", {"response_id": response_id, "usage": usage(output), "padding": padding})]
        path.write_text("".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")

    def test_active_rollout_path_change_for_same_thread_is_followed(self):
        with tempfile.TemporaryDirectory() as temporary:
            old, new = Path(temporary) / "old.jsonl", Path(temporary) / "new.jsonl"
            self.write_log(old, "old", 100)
            self.write_log(new, "new", 200)
            cache = TailCache()
            row = {"id": "same-thread", "rollout_path": str(old), "model": "m"}
            self.assertEqual(cache.update(row).measurements.last["rate"], 20)
            row["rollout_path"] = str(new)
            tail = cache.update(row)
            self.assertEqual(tail.path, new)
            self.assertEqual(tail.measurements.last["rate"], 40)

    def test_log_replaced_with_a_larger_file_resets_read_offset(self):
        with tempfile.TemporaryDirectory() as temporary:
            path, replacement = Path(temporary) / "log.jsonl", Path(temporary) / "replacement.jsonl"
            self.write_log(path, "old", 100)
            tail = SessionTail(str(path)); tail.update()
            self.write_log(replacement, "new", 200, "longer" * 100)
            replacement.replace(path)
            tail.update()
            self.assertEqual(tail.measurements.output_total, 200)
            self.assertEqual(tail.measurements.last["rate"], 40)

    def test_log_rewritten_in_place_and_regrown_resets_partial_data(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "log.jsonl"
            self.write_log(path, "old", 100)
            tail = SessionTail(str(path)); tail.update()
            self.write_log(path, "new", 200, "longer" * 100)
            tail.update()
            self.assertEqual(tail.measurements.output_total, 200)

    def test_missing_log_is_reported_unavailable(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "log.jsonl"
            self.write_log(path, "old", 100)
            tail = SessionTail(str(path)); tail.update()
            path.unlink(); tail.update()
            self.assertEqual(tail.source()["state"], "unavailable")

    def test_forced_refresh_reopens_even_the_same_path(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "log.jsonl"
            self.write_log(path, "r", 100)
            cache = TailCache()
            row = {"id": "t", "rollout_path": str(path)}
            first = cache.update(row)
            refreshed = cache.update(row, force=True)
            self.assertIsNot(first, refreshed)
            self.assertEqual(refreshed.measurements.last["rate"], 20)

    def test_running_collector_follows_resumed_path_and_publishes_append_promptly(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runtime = root / "runtime"; runtime.mkdir()
            old, new = root / "old.jsonl", root / "new.jsonl"
            self.write_log(old, "old", 100)
            self.write_log(new, "new", 300)
            database = root / "state_5.sqlite"
            with sqlite3.connect(database) as c:
                c.execute("CREATE TABLE threads (id TEXT, title TEXT, name TEXT, rollout_path TEXT, model TEXT, updated_at INT, archived INT)")
                c.execute("INSERT INTO threads VALUES (?,?,?,?,?,?,?)", ("t", "first message", "current", str(old), "m", 1, 0))
            c.close()
            (runtime / "selection.json").write_text(json.dumps({"title": "current"}), encoding="utf-8")
            process = subprocess.Popen([sys.executable, str(Path(__file__).resolve().parents[1] / "metrics.py"),
                "--codex-home", str(root), "--runtime", str(runtime)], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
            def wait_for(predicate, limit=5):
                start = time.monotonic()
                while time.monotonic() - start < limit:
                    try:
                        payload = json.loads((runtime / "metrics.json").read_text("utf-8"))
                        if predicate(payload):
                            return time.monotonic() - start
                    except (OSError, ValueError, TypeError, KeyError):
                        pass
                    time.sleep(0.01)
                self.fail("running collector did not publish expected stats")
            try:
                wait_for(lambda p: p["metrics"]["last"]["output_tokens"] == 100)
                with sqlite3.connect(database) as c:
                    c.execute("UPDATE threads SET rollout_path=?", (str(new),))
                c.close()
                changed = wait_for(lambda p: p["source"]["path"] == str(new) and p["metrics"]["last"]["output_tokens"] == 300)
                self.assertLess(changed, 1.2)
                with new.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(event(10, "token_usage_record", {"response_id": "append", "usage": usage(200)})) + "\n")
                updated = wait_for(lambda p: p["metrics"]["last"]["output_tokens"] == 200)
                self.assertLess(updated, 0.7)
            finally:
                process.terminate()
                process.communicate(timeout=3)


if __name__ == "__main__":
    unittest.main()
