"""Exercise the extracted release using ONLY its bundled Python and synthetic chat data."""
import argparse
import datetime as dt
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import time
import zipfile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--zip", type=Path, required=True)
    args = parser.parse_args()
    package = args.package.resolve()
    with zipfile.ZipFile(args.zip) as archive:
        names = archive.namelist()
        forbidden = {"runtime", "inspection", ".git", "__pycache__"}
        for name in names:
            parts = Path(name.replace("\\", "/")).parts
            assert not any(p in forbidden for p in parts), f"Private/generated path in package: {name}"
            assert Path(name).name not in {"settings.json", "user-layout.json", "verification.json", "auth.json"}, name
            assert not name.endswith((".jsonl", ".sqlite", ".sqlite-wal", ".sqlite-shm", ".lnk")), name
        assert any(n.replace("\\", "/").endswith("/python/LICENSE.txt") for n in names), "Python license missing"
    with tempfile.TemporaryDirectory(prefix="HUD smoke \u4fbf\u643a ") as temporary:
        root = Path(temporary)
        fixture = root / "codex home"; fixture.mkdir()
        runtime = root / "data" / "runtime"; runtime.mkdir(parents=True)
        report = root / "runtime-check.json"
        environment = os.environ.copy()
        environment["CODEX_HOME"] = str(fixture)
        environment["CODEX_TOKEN_HUD_HOME"] = str(root / "data")
        # A valid run must not find or need the developer's system Python.
        environment["PATH"] = os.path.join(os.environ["WINDIR"], "System32")
        subprocess.run([str(package / "CodexTokenHud.exe"), "--check", str(report)],
                       env=environment, check=True, timeout=15)
        check = json.loads(report.read_text("utf-8-sig"))
        assert check["ok"] and check["bundled_python"], check
        assert check["app_version"] == (package / "VERSION").read_text().strip(), check
        def event(seconds, kind, payload):
            return {"timestamp": dt.datetime.fromtimestamp(1700000000 + seconds, dt.timezone.utc).isoformat(),
                    "type": kind, "payload": payload}
        log = fixture / "synthetic.jsonl"
        events = [event(0, "event_msg", {"type": "task_started", "turn_id": "synthetic-turn"}),
                  event(5, "token_usage_record", {"response_id": "synthetic-response", "usage": {
                      "input_tokens": 1000, "cached_input_tokens": 750, "output_tokens": 100}})]
        log.write_text("".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")
        with sqlite3.connect(fixture / "state_6.sqlite") as conn:
            conn.execute("CREATE TABLE threads (id TEXT, title TEXT, name TEXT, rollout_path TEXT, model TEXT, updated_at INT)")
            conn.execute("INSERT INTO threads VALUES (?,?,?,?,?,?)", ("synthetic-chat", "fixture prompt", "fixture chat", str(log), "fixture-model", 1))
        conn.close()
        (runtime / "selection.json").write_text(json.dumps({"title": "fixture chat"}), encoding="utf-8")
        # Match the GUI's pythonw backend launch, including parent lifetime and environment override.
        collector = subprocess.Popen([str(package / "python" / "pythonw.exe"), "-I", "-X", "utf8",
            str(package / "metrics.py"), "--runtime", str(runtime), "--parent-pid", str(os.getpid())], env=environment)
        try:
            deadline = time.monotonic() + 8
            metrics = None
            while time.monotonic() < deadline:
                if collector.poll() is not None:
                    raise AssertionError(f"Bundled collector exited: {collector.returncode}")
                try:
                    metrics = json.loads((runtime / "metrics.json").read_text("utf-8"))
                    if metrics["binding"] == "ok": break
                except (OSError, ValueError): pass
                time.sleep(0.05)
            assert metrics and metrics["binding"] == "ok", "Collector failed to bind synthetic chat"
            last = metrics["metrics"]["last"]
            assert last["rate"] == 20 and last["cache_percent"] == 75, last
            assert metrics["repository_state"] == "ok" and metrics["source"]["state"] == "ok", metrics
        finally:
            collector.terminate(); collector.wait(timeout=5)
        print(json.dumps({"portable_smoke": "passed", "python_version": check["python_version"],
                          "app_version": check["app_version"], "synthetic_rate": 20,
                          "synthetic_cache_percent": 75, "system_python_required": False}))


if __name__ == "__main__": main()
