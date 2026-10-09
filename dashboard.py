"""Dependency-free, loopback-only dashboard for Codex local telemetry."""
from __future__ import annotations

import argparse
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import sys
import threading
import time
from urllib.parse import parse_qs, urlencode, urlsplit
import webbrowser

if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from history import HistoryCache, SessionCatalog
from metrics import TailCache, atomic_json, read_selection


def data_directory() -> Path:
    custom = os.environ.get("CODEX_TOKEN_HUD_HOME")
    if custom:
        return Path(custom).expanduser().resolve()
    if os.name == "nt":
        return Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData/Local") / "CodexTokenHud"
    if sys.platform == "darwin":
        return Path.home() / "Library/Application Support/CodexTokenHud"
    return Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local/state") / "codex-token-hud"


class Dashboard:
    def __init__(self, codex_home: Path, runtime: Path, logs=(), native_enabled=False):
        self.runtime = runtime
        self.native_enabled = native_enabled
        self.catalog = SessionCatalog(codex_home, logs)
        self.histories = HistoryCache()
        self.tails = TailCache()
        self.lock = threading.RLock()

    def row(self, thread_id: str) -> dict:
        self.catalog.refresh()
        row = self.catalog.rows.get(thread_id)
        if row is None:
            raise ValueError("未找到此对话的本地日志，请刷新对话列表")
        return row

    def get(self, endpoint: str, query: dict) -> dict:
        with self.lock:
            thread_id = query.get("thread", [""])[0]
            if endpoint == "threads":
                self.catalog.refresh(force=query.get("force") == ["1"])
                rows = [{k: row.get(k) for k in ("id", "title", "model", "updated_at_ms", "segment_count")}
                        for row in self.catalog.rows.values()]
                native = read_selection(self.runtime / "metrics.json")
                return {"threads": rows, "bound_thread_id": native.get("thread_id"),
                        "repository_state": self.catalog.repository.state,
                        "native_available": self.native_enabled,
                        "pinned_thread_id": read_selection(self.runtime / "manual-binding.json").get("thread_id")}
            row = self.row(thread_id)
            if endpoint == "live":
                force = query.get("force") == ["1"]
                if force:
                    self.catalog.refresh(force=True)
                    row = self.row(thread_id)
                tail = self.tails.update(row, force=force)
                return {"thread_id": thread_id, "metrics": tail.measurements.snapshot(), "source": tail.source(),
                        "native_available": self.native_enabled,
                        "pinned_thread_id": read_selection(self.runtime / "manual-binding.json").get("thread_id") if self.native_enabled else None,
                        "range": self.saved_range(thread_id), "updated_at_ms": time.time() * 1000}
            if endpoint == "messages":
                history = self.histories.load(self.catalog, thread_id, force=query.get("force") == ["1"])
                return {"messages": history.find_messages(query.get("q", [""])[0]),
                        "message_count": len(history.messages), "sample_count": len(history.samples),
                        "start_ms": history.messages[0]["at_ms"] if history.messages else None,
                        "end_ms": history.samples[-1]["measured_at_ms"] if history.samples else None,
                        "warnings": history.warnings}
            raise ValueError("未知接口")

    def saved_range(self, thread_id: str):
        saved = read_selection(self.runtime / "range-result.json")
        return saved if saved.get("thread_id") == thread_id else None

    def post(self, endpoint: str, body: dict) -> dict:
        with self.lock:
            thread_id = body.get("thread_id", "")
            self.row(thread_id)
            if endpoint == "range":
                if not isinstance(body.get("selection"), dict):
                    raise ValueError("请选择有效的统计范围")
                self.catalog.refresh(force=True)
                history = self.histories.load(self.catalog, thread_id)
                result = history.calculate(body.get("selection") or {})
                result["thread_id"] = thread_id
                # Save derived measurements only; message excerpts stay in browser memory.
                saved = json.loads(json.dumps(result))
                for message in (saved["bounds"].get("first"), saved["bounds"].get("last")):
                    if message:
                        message.pop("preview", None)
                atomic_json(self.runtime / "range-result.json", saved)
                return result
            if endpoint == "clear":
                if self.saved_range(thread_id):
                    atomic_json(self.runtime / "range-result.json", {})
                return {"ok": True}
            if endpoint == "pin":
                row = self.catalog.rows[thread_id]
                atomic_json(self.runtime / "manual-binding.json", {"thread_id": thread_id, "title": row["title"]})
                return {"ok": True}
            if endpoint == "unpin":
                atomic_json(self.runtime / "manual-binding.json", {})
                return {"ok": True}
            raise ValueError("未知接口")


class LocalServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False

    def __init__(self, service: Dashboard, port=0):
        self.service = service
        self.token = secrets.token_urlsafe(32)
        super().__init__(("127.0.0.1", port), Handler)
        self.origin = "http://127.0.0.1:" + str(self.server_port)

    def url(self, thread_id=""):
        parameters = {"token": self.token}
        if thread_id:
            parameters["thread"] = thread_id
        return self.origin + "/#" + urlencode(parameters)


class Handler(BaseHTTPRequestHandler):
    server: LocalServer

    def log_message(self, *args):
        pass  # No access logs containing search text or conversation identifiers.

    def send(self, status: int, body, content_type="application/json; charset=utf-8"):
        data = json.dumps(body, ensure_ascii=False, allow_nan=False).encode() if isinstance(body, dict) else body
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; "
                         "connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'")
        self.end_headers()
        self.wfile.write(data)

    def allowed(self, api=False) -> bool:
        if self.headers.get("Host") != "127.0.0.1:" + str(self.server.server_port):
            self.send(403, {"error": "不允许的访问地址"})
            return False
        origin = self.headers.get("Origin")
        if origin and origin != self.server.origin:
            self.send(403, {"error": "只允许本机面板访问"})
            return False
        if api and not hmac.compare_digest(self.headers.get("X-Hud-Token", "").encode(), self.server.token.encode()):
            self.send(403, {"error": "访问凭据已过期，请重新打开面板"})
            return False
        return True

    def do_GET(self):
        url = urlsplit(self.path)
        if not self.allowed(api=url.path.startswith("/api/")):
            return
        try:
            if url.path.startswith("/api/"):
                self.send(200, self.server.service.get(url.path[5:], parse_qs(url.query)))
                return
            static = {"/": ("index.html", "text/html; charset=utf-8"),
                      "/app.js": ("app.js", "text/javascript; charset=utf-8"),
                      "/style.css": ("style.css", "text/css; charset=utf-8")}
            if url.path not in static:
                self.send(404, {"error": "未找到页面"})
                return
            name, content_type = static[url.path]
            self.send(200, (Path(__file__).parent / "web" / name).read_bytes(), content_type)
        except (ValueError, OSError, TypeError) as error:
            self.send(400, {"error": str(error)})

    def do_POST(self):
        if not self.allowed(api=True):
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 32768:
                raise ValueError("请求大小无效")
            body = json.loads(self.rfile.read(size))
            if not isinstance(body, dict):
                raise ValueError("请求格式无效")
            self.send(200, self.server.service.post(urlsplit(self.path).path.removeprefix("/api/"), body))
        except (ValueError, OSError, TypeError) as error:
            self.send(400, {"error": str(error)})


def start_server(codex_home: Path, runtime: Path, logs=(), port=0, native_enabled=False):
    server = LocalServer(Dashboard(codex_home, runtime, logs, native_enabled), port)
    threading.Thread(target=server.serve_forever, name="local-dashboard", daemon=True).start()
    atomic_json(runtime / "dashboard.json", {"url": server.url(), "pid": os.getpid()})
    return server


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codex-home", type=Path, default=Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex"))
    parser.add_argument("--runtime", type=Path, default=data_directory() / "runtime")
    parser.add_argument("--log", type=Path, action="append", default=[], help="Explicit local JSONL; may be repeated")
    parser.add_argument("--port", type=int, default=0, help="Local port (default: choose an available port)")
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--thread", default="")
    args = parser.parse_args()
    server = start_server(args.codex_home, args.runtime, args.log, args.port)
    url = server.url(args.thread)
    print("Codex Token HUD: " + url, flush=True)
    if not args.no_browser:
        webbrowser.open(url)
    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
