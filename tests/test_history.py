import datetime as dt
from contextlib import closing
import http.client
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dashboard import Dashboard, LocalServer
from history import History, HistoryCache, SessionCatalog
from metrics import atomic_json, monitor, SessionTail
from test_metrics import event, usage


def write_log(path, records, thread="t", start=0):
    path.parent.mkdir(parents=True, exist_ok=True)
    meta = event(start, "session_meta", {"id": thread, "timestamp": event(start, "", {})["timestamp"], "cwd": "/demo"})
    path.write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in [meta] + records), encoding="utf8")


def user(seconds, text):
    return event(seconds, "response_item", {"type": "message", "role": "user", "content": [{"type": "input_text", "text": text}]})


def response(start, finish, name, output=100, cached=750, input_tokens=1000):
    return [event(start, "event_msg", {"type": "task_started", "turn_id": name}),
            event(finish, "token_usage_record", {"response_id": name, "usage": usage(output, cached, input_tokens)})]


def all_time():
    return {"mode": "time", "start": event(-1, "", {})["timestamp"], "end": event(100, "", {})["timestamp"]}


class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.path = self.root / "sessions/a.jsonl"

    def tearDown(self):
        self.temp.cleanup()

    def history(self, records):
        write_log(self.path, records)
        return History([self.path], "demo-model")

    def test_weighted_means_use_generation_seconds_and_input_tokens(self):
        h = self.history(response(0, 1, "a", 100, 100, 100) + response(1, 10, "b", 100, 0, 900))
        r = h.calculate(all_time())
        self.assertEqual((r["rate"], r["cache_percent"], r["sample_count"]), (20, 10, 2))

    def test_message_range_includes_last_answer_and_distinguishes_repeated_text(self):
        h = self.history([user(0, "相同消息")] + response(0, 5, "a") + [user(10, "相同消息")] +
                         response(10, 15, "b") + [user(20, "停止边界")] + response(20, 25, "c"))
        m = h.find_messages("相同消息")
        self.assertEqual(len(m), 2)
        self.assertNotEqual(m[0]["id"], m[1]["id"])
        r = h.calculate({"mode": "messages", "first_id": m[0]["id"], "last_id": m[1]["id"]})
        self.assertEqual((r["sample_count"], r["output_tokens"]), (2, 200))
        r = h.calculate({"mode": "messages", "first_id": m[0]["id"], "last_id": m[0]["id"]})
        self.assertEqual(r["sample_count"], 1)
        with self.assertRaises(ValueError):
            h.calculate({"mode": "messages", "first_id": m[1]["id"], "last_id": m[0]["id"]})

    def test_time_bounds_include_exact_completion_and_reject_bad_order(self):
        h = self.history(response(0, 5, "a") + response(5, 10, "b"))
        at = event(5, "", {})["timestamp"]
        self.assertEqual(h.calculate({"mode": "time", "start": at, "end": at})["sample_count"], 1)
        with self.assertRaises(ValueError):
            h.calculate({"mode": "time", "start": event(10, "", {})["timestamp"], "end": at})

    def test_missing_data_is_excluded_instead_of_zero_and_response_ids_dedup(self):
        h = self.history([event(0, "token_usage_record", {"response_id": "unknown-time", "usage": {"output_tokens": 50}})] +
                         response(1, 6, "a") + [event(7, "event_msg", {"type": "token_count", "info": {
                             "last_token_usage": usage(), "total_token_usage": {"output_tokens": 150}}}),
                         event(8, "token_usage_record", {"response_id": "a", "usage": usage()})])
        r = h.calculate(all_time())
        self.assertEqual((r["sample_count"], r["timed_samples"], r["cache_samples"]), (2, 1, 1))
        self.assertEqual((r["rate"], r["cache_percent"]), (20, 75))

    def test_context_records_and_canonical_message_copy_are_not_double_counted(self):
        h = self.history([user(0, "<environment_context>fake</environment_context>"), user(1, "真实提问"),
                         event(1.5, "event_msg", {"type": "user_message", "message": "真实提问"})] + response(2, 5, "a"))
        self.assertEqual(len(h.messages), 1)
        self.assertEqual(h.messages[0]["text"], "真实提问")

    def test_database_free_title_index_and_complete_offline_line_without_newline(self):
        write_log(self.path, [user(0, "离线提问")] + response(0, 5, "a"))
        self.path.write_bytes(self.path.read_bytes().rstrip(b"\n"))
        (self.root / "session_index.jsonl").write_text(json.dumps({"id": "t", "thread_name": "CLI 对话"}), encoding="utf8")
        c = SessionCatalog(self.root)
        c.refresh(force=True)
        self.assertEqual(c.rows["t"]["title"], "CLI 对话")
        self.assertEqual(HistoryCache().load(c, "t").calculate(all_time())["sample_count"], 1)

    def test_resumed_segments_are_merged_without_duplicate_usage_or_day_long_timing(self):
        write_log(self.path, [user(0, "第一条")] + response(0, 5, "a"))
        second = self.root / "sessions/b.jsonl"
        write_log(second, [event(5, "token_usage_record", {"response_id": "a", "usage": usage()}),
                          event(50, "token_usage_record", {"response_id": "b", "usage": usage(200)})], start=40)
        r = History([self.path, second]).calculate(all_time())
        self.assertEqual((r["sample_count"], r["timed_samples"], r["output_tokens"]), (2, 1, 300))

    def test_full_history_not_limited_to_live_tail_and_message_ids_stay_stable(self):
        h = self.history([user(0, "早期提问")] + response(0, 5, "a") +
                         [event(6, "response_item", {"type": "function_call_output", "output": "x" * (9 * 1024 * 1024)})] +
                         [user(10, "后期提问")] + response(10, 15, "b"))
        first_id = h.messages[0]["id"]
        self.assertEqual(h.calculate(all_time())["sample_count"], 2)
        with self.path.open("a", encoding="utf8") as f:
            f.write(json.dumps(user(20, "新消息")) + "\n")
        self.assertEqual(History([self.path]).messages[0]["id"], first_id)

    def test_catalog_tracks_resume_even_when_database_rollout_path_is_stale(self):
        write_log(self.path, response(0, 5, "a"))
        with closing(sqlite3.connect(self.root / "state_6.sqlite")) as db, db:
            db.execute("CREATE TABLE threads (id TEXT, title TEXT, rollout_path TEXT)")
            db.execute("INSERT INTO threads VALUES ('t', '标题', ?)", (str(self.path),))
        catalog = SessionCatalog(self.root)
        catalog.refresh(force=True)
        newer = self.root / "sessions/b.jsonl"
        write_log(newer, response(10, 15, "b"), start=10)
        catalog.refresh(force=True)
        self.assertTrue(Path(catalog.title_matches("标题")[0]["rollout_path"]).samefile(newer))
        self.assertEqual(len(catalog.segments("t")), 2)
        self.assertEqual(HistoryCache().load(catalog, "t").calculate(all_time())["sample_count"], 2)

    def test_manual_binding_uses_exact_id_without_a_database_and_fails_closed(self):
        write_log(self.path, response(0, 5, "a"))
        runtime = self.root / "runtime"
        atomic_json(runtime / "selection.json", {"title": "旧标题", "thread_id": "t", "binding_mode": "manual"})
        r = monitor(self.root, runtime, once=True)
        self.assertEqual((r["binding"], r["thread_id"], r["metrics"]["last"]["rate"]), ("ok", "t", 20))
        atomic_json(runtime / "selection.json", {"title": "demo", "thread_id": "missing-id", "binding_mode": "manual"})
        self.assertIsNone(monitor(self.root, runtime, once=True)["thread_id"])

    def test_live_tail_rereads_same_length_timestamp_rewrite(self):
        import os
        write_log(self.path, response(0, 5, "a"))
        tail = SessionTail(str(self.path))
        tail.update()
        previous = tail.measurements.last["measured_at_ms"]
        before = self.path.stat()
        data = self.path.read_bytes().replace(event(5, "", {})["timestamp"].encode(), event(6, "", {})["timestamp"].encode())
        self.path.write_bytes(data)
        self.assertEqual(self.path.stat().st_size, before.st_size)
        os.utime(self.path, ns=(before.st_atime_ns, before.st_mtime_ns + 10000000))
        tail.update()
        self.assertEqual(tail.measurements.last["measured_at_ms"], previous + 1000)

    def test_local_server_requires_token_and_rejects_foreign_origin_and_host(self):
        import threading
        write_log(self.path, [user(0, "本地消息")] + response(0, 5, "a"))
        runtime = self.root / "runtime"
        server = LocalServer(Dashboard(self.root, runtime))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        def request(path, headers=None, body=None):
            connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=3)
            connection.request("POST" if body else "GET", path, body=body, headers=headers or {})
            r = connection.getresponse()
            result = r.status, r.read()
            connection.close()
            return result
        try:
            self.assertEqual(request("/api/threads")[0], 403)
            headers = {"X-Hud-Token": server.token}
            self.assertEqual(request("/api/threads", headers)[0], 200)
            self.assertEqual(request("/api/threads", dict(headers, Origin="https://example.com"))[0], 403)
            self.assertEqual(request("/api/threads", dict(headers, Host="example.com"))[0], 403)
            self.assertEqual(request("/../../auth.json", headers)[0], 404)
            status, body = request("/api/range", dict(headers, **{"Content-Type": "application/json"}),
                                   json.dumps({"thread_id": "t", "selection": all_time()}))
            self.assertEqual(status, 200)
            self.assertEqual(json.loads(body)["rate"], 20)
            self.assertEqual(json.loads((runtime / "range-result.json").read_text())["sample_count"], 1)
        finally:
            server.shutdown()
            server.server_close()

    def test_refresh_ack_is_published_and_rebinds_stale_database_source(self):
        write_log(self.path, response(0, 5, "a"))
        with closing(sqlite3.connect(self.root / "state_6.sqlite")) as db, db:
            db.execute("CREATE TABLE threads (id TEXT, title TEXT, rollout_path TEXT)")
            db.execute("INSERT INTO threads VALUES ('t', '标题', ?)", (str(self.path),))
        runtime = self.root / "runtime"
        atomic_json(runtime / "selection.json", {"title": "标题", "thread_id": "t", "refresh_id": 1})
        process = subprocess.Popen([sys.executable, "-I", str(Path(__file__).resolve().parents[1] / "metrics.py"),
                                    "--codex-home", str(self.root), "--runtime", str(runtime)],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        def wait_for(predicate):
            deadline = time.monotonic() + 4
            while time.monotonic() < deadline:
                try:
                    value = json.loads((runtime / "metrics.json").read_text("utf8"))
                    if predicate(value):
                        return value
                except (OSError, ValueError, KeyError, TypeError):
                    pass
                if process.poll() is not None:
                    self.fail(process.stderr.read().decode())
                time.sleep(0.04)
            self.fail("Collector did not acknowledge refresh within four seconds")
        try:
            wait_for(lambda value: value["refresh"]["request_id"] == 1)
            newer = self.root / "sessions/b.jsonl"
            write_log(newer, response(10, 15, "b", output=200), start=10)
            atomic_json(runtime / "selection.json", {"title": "标题", "thread_id": "t", "refresh_id": 2})
            result = wait_for(lambda value: value["refresh"]["request_id"] == 2)
            self.assertTrue(Path(result["source"]["path"]).samefile(newer))
            self.assertEqual(result["metrics"]["last"]["rate"], 40)
            self.assertEqual(result["refresh"]["state"], "ok")
        finally:
            process.terminate()
            process.communicate(timeout=3)


if __name__ == "__main__":
    unittest.main()
