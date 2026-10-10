"""Launch a source or bundled HUD with synthetic logs; verify native/API behavior."""
import argparse
import datetime as dt
import json
from pathlib import Path
import shutil
import os
import signal
import subprocess
import tempfile
import time
import urllib.request
from urllib.parse import parse_qs, urlsplit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--program", nargs="+")
    args = parser.parse_args()
    program = [json.loads(args.manifest.read_text("utf-8"))["program"]] if args.manifest else args.program
    if not program:
        parser.error("Specify --manifest or --program")
    with tempfile.TemporaryDirectory(prefix="HUD native smoke 测试 ") as directory:
        root = Path(directory)
        runtime = root / "runtime"
        path = root / "synthetic.jsonl"
        start = dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=10)
        def event(seconds, kind, payload):
            return {"timestamp": (start + dt.timedelta(seconds=seconds)).isoformat(), "type": kind, "payload": payload}
        records = [event(0, "session_meta", {"id": "synthetic-hud", "model": "demo-model", "cwd": "/synthetic"}),
                   event(0, "event_msg", {"type": "task_started", "turn_id": "synthetic-turn"}),
                   event(5, "token_usage_record", {"response_id": "synthetic-response", "usage": {
                       "output_tokens": 500, "input_tokens": 2000, "cached_input_tokens": 1500}}),
                   event(5, "event_msg", {"type": "task_complete"})]
        path.write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")
        command = program + ["--codex-home", str(root), "--runtime", str(runtime), "--log", str(path),
                             "--thread", "synthetic-hud", "--language", "en", "--no-tray", "--quit-after", "30"]
        with (root / "process.log").open("w+", encoding="utf-8") as output:
            process = subprocess.Popen(command, stdout=output, stderr=output)
            def wait_for(predicate, timeout=60):
                deadline = time.monotonic() + timeout
                last_status = None
                while time.monotonic() < deadline:
                    if process.poll() is not None:
                        output.seek(0)
                        raise AssertionError("HUD exited before verification: " + output.read())
                    try:
                        value = json.loads((runtime / "status.json").read_text("utf-8"))
                        last_status = value
                        if predicate(value):
                            return value
                    except (OSError, ValueError):
                        pass
                    time.sleep(0.05)
                startup = (runtime / "startup.json").read_text("utf-8") if (runtime / "startup.json").exists() else "not written"
                output.seek(0)
                raise AssertionError("HUD did not publish the expected state; last=" + json.dumps(last_status) +
                                     "; startup=" + startup + "; log=" + output.read()[-4000:])
            status = None
            try:
                status = wait_for(lambda value: value.get("rate") == "100.0" and value.get("cache") == "75.0")
                assert status["visible"] and status["topmost_requested"] and not status["minimized"], status
                assert status["native_error"] == "", status
                if status["platform"] == "cocoa":
                    assert status["native"]["collection_behavior"] & 257 == 257, status
                    assert status["native"]["level"] > 0, status
                elif status["platform"] == "xcb" and shutil.which("xprop"):
                    props = subprocess.check_output(["xprop", "-id", str(status["window_id"]), "_NET_WM_STATE"], text=True)
                    assert "_NET_WM_STATE_ABOVE" in props, props
                elif status["platform"] in ("offscreen", "minimal"):
                    raise AssertionError("A real window-system backend is required for the native smoke check")
                link = json.loads((runtime / "dashboard.json").read_text("utf-8"))["url"]
                parts = urlsplit(link)
                origin = parts.scheme + "://" + parts.netloc
                token = parse_qs(parts.fragment)["token"][0]
                def api(endpoint, body=None):
                    data = json.dumps(body).encode() if body is not None else None
                    request = urllib.request.Request(origin + "/api/" + endpoint, data=data,
                              headers={"X-Hud-Token": token, "Content-Type": "application/json"})
                    with urllib.request.urlopen(request, timeout=3) as response:
                        return json.load(response)
                with urllib.request.urlopen(origin, timeout=3) as response:
                    assert b"Codex Token HUD" in response.read(), "Packaged dashboard assets missing"
                assert api("threads")["native_follow_mode"] == "activity"
                selection = {"mode": "time", "start": start.isoformat(),
                             "end": (start + dt.timedelta(seconds=6)).isoformat()}
                api("range", {"thread_id": "synthetic-hud", "selection": selection})
                api("clear", {"thread_id": "synthetic-hud"})
                api("unpin", {})
                wait_for(lambda value: value["pinned_thread_id"] is None and value["visible"])
                again = subprocess.run(program + ["--runtime", str(runtime), "--quit-after", "1"],
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5)
                assert again.returncode == 0, again.stderr.decode("utf-8", "replace")
                final = wait_for(lambda value: value["thread_id"] == "synthetic-hud" and value["visible"])
                # Windows' venv redirector is a parent of the real Python process.
                assert final["pid"] == status["pid"], "Relaunch created a duplicate HUD"
                assert process.wait(timeout=45) == 0
                output.seek(0)
                log = output.read()
                assert "Traceback" not in log, log
                print("Native HUD smoke passed: " + status["platform"] + ", 100.0 tok/s, 75.0% cache; range, unpin, relaunch, assets and clean exit")
            finally:
                if process.poll() is None:
                    if os.name == "nt" and status and status["pid"] != process.pid:
                        try:
                            os.kill(status["pid"], signal.SIGTERM)
                        except ProcessLookupError:
                            pass
                    process.terminate()
                    process.wait(timeout=5)


if __name__ == "__main__":
    main()
