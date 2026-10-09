"""Read-only Codex usage measurements. No credentials, network, or conversation exports."""
from __future__ import annotations

import argparse
import collections
from contextlib import closing
import datetime as dt
import json
import os
from pathlib import Path
import sqlite3
import sys
import time
from typing import Any

# In isolated mode, trust only this installed source directory for sibling modules.
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))


def timestamp_ms(value: str | None) -> float | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return dt.datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp() * 1000
    except (TypeError, ValueError):
        return None


def integer(value: Any) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError, OverflowError):
        return 0


def cache_percent(usage: dict) -> float | None:
    if "input_tokens" not in usage or "cached_input_tokens" not in usage:
        return None
    if usage["input_tokens"] is None or usage["cached_input_tokens"] is None:
        return None
    total = integer(usage.get("input_tokens"))
    cached = integer(usage.get("cached_input_tokens"))
    if not total or cached > total:
        return None
    return 100 * cached / total


class Measurements:
    """One thread's samples, with generation timing separated from tool execution."""

    def __init__(self, model: str | None = None):
        self.model = model
        self.turn_id: str | None = None
        self.last: dict | None = None
        self.model_start: float | None = None
        self.request_boundary: float | None = None
        self.pending_calls: set[str] = set()
        self.stage = "idle"
        self.output_total = 0
        self.reasoning_total = 0
        self.turn_output = 0
        self.turn_generation_ms = 0.0
        self.sample_count = 0
        self.recent_response_ids: collections.deque[str] = collections.deque(maxlen=256)
        self.last_usage_fingerprint: tuple | None = None
        self.legacy_total: tuple | None = None
        self.expected_legacy: tuple | None = None
        self.last_usage_at: float = 0
        self.event_at: float = 0
        self.turn_started_at: float | None = None

    def feed(self, event: dict) -> None:
        kind = event.get("type")
        p = event.get("payload") or {}
        if not isinstance(p, dict):
            return
        at = timestamp_ms(event.get("timestamp"))
        if at is not None:
            self.event_at = max(self.event_at, at)
        event_type = p.get("type")

        if kind == "turn_context":
            self.model = p.get("model") or self.model
            return
        if kind == "event_msg" and event_type in ("task_started", "turn_started"):
            self.turn_id = p.get("turn_id")
            self.turn_started_at = at
            self.request_boundary = at
            self.model_start = None
            self.pending_calls.clear()
            self.stage = "generating"
            self.turn_output = 0
            self.turn_generation_ms = 0
            self.sample_count = 0
            return
        if kind == "event_msg" and event_type in ("task_complete", "task_completed", "turn_complete", "turn_aborted"):
            self.stage = "idle"
            self.pending_calls.clear()
            return

        if kind == "event_msg" and event_type == "item_completed":
            item = p.get("item") or {}
            if not isinstance(item, dict):
                return
            model_item = str(item.get("type", "")).replace("_", "").lower()
            if model_item in ("reasoning", "agentmessage", "assistantmessage"):
                start = p.get("started_at_ms")
                if isinstance(start, (int, float)) and at is not None and 0 < start <= at:
                    # Item timings can arrive late; never attach an old item to the next response.
                    if start >= self.last_usage_at:
                        self.model_start = min(self.model_start or start, start)
                        self.stage = "generating"
            return

        if kind == "response_item":
            call_id = p.get("call_id")
            if event_type in ("function_call", "custom_tool_call") and call_id:
                self.pending_calls.add(call_id)
                self.stage = "tools"
            elif event_type in ("function_call_output", "custom_tool_call_output"):
                self.pending_calls.discard(call_id)
                if not self.pending_calls:
                    self.request_boundary = at
                    self.stage = "generating"
            elif event_type == "message" and p.get("role") == "user":
                self.request_boundary = at
            return

        if kind == "token_usage_record":
            response_id = p.get("response_id")
            if response_id and response_id in self.recent_response_ids:
                return
            if response_id:
                self.recent_response_ids.append(response_id)
            usage = p.get("usage")
            if isinstance(usage, dict):
                self._sample(usage, at, "response", p.get("thread_token_usage"), p.get("turn_token_usage"))
                self.expected_legacy = self._fingerprint(usage)
            return

        if kind == "event_msg" and event_type == "token_count":
            info = p.get("info") or {}
            if not isinstance(info, dict):
                return
            usage = info.get("last_token_usage")
            total = info.get("total_token_usage") or {}
            if isinstance(usage, dict) and at is not None:
                fp = self._fingerprint(usage)
                # The two streams have DIFFERENT cumulative totals after resume/compaction.
                # Compare legacy totals to legacy totals, never to billing-record totals.
                cumulative = self._fingerprint(total) if isinstance(total, dict) and total else None
                repeated_total = cumulative is not None and cumulative == self.legacy_total
                self.legacy_total = cumulative
                record_duplicate = fp == self.expected_legacy
                if record_duplicate:
                    self.expected_legacy = None
                if not repeated_total and not record_duplicate:
                    self.expected_legacy = None
                    self._sample(usage, at, "legacy", total, None)

    @staticmethod
    def _fingerprint(usage: dict) -> tuple:
        return tuple(integer(usage.get(k)) for k in (
            "input_tokens", "cached_input_tokens", "output_tokens", "reasoning_output_tokens"))

    def _sample(self, usage: dict, at: float | None, source: str,
                total: dict | None, turn: dict | None) -> None:
        if at is None:
            return
        output = integer(usage.get("output_tokens"))
        basis = "stream" if self.model_start is not None else "request"
        start = self.model_start if self.model_start is not None else self.request_boundary
        duration = at - start if start is not None else None
        # Old history may start halfway through a response. Preserve usage without inventing speed.
        rate = output * 1000 / duration if duration is not None and duration >= 50 and output else None
        self.last = {
            "rate": rate, "duration_ms": duration if duration is not None and duration > 0 else None,
            "basis": basis, "input_tokens": integer(usage.get("input_tokens")),
            "cached_input_tokens": integer(usage.get("cached_input_tokens")),
            "output_tokens": output, "reasoning_output_tokens": integer(usage.get("reasoning_output_tokens")),
            "cache_percent": cache_percent(usage), "measured_at_ms": at, "model": self.model,
            "source": source, "turn_id": self.turn_id,
        }
        if isinstance(total, dict):
            self.output_total = integer(total.get("output_tokens"))
            self.reasoning_total = integer(total.get("reasoning_output_tokens"))
        else:
            self.output_total += output
        if isinstance(turn, dict):
            self.turn_output = integer(turn.get("output_tokens"))
        else:
            self.turn_output += output
        if rate is not None:
            self.turn_generation_ms += duration
            self.sample_count += 1
        self.last_usage_fingerprint = self._fingerprint(usage)
        self.last_usage_at = at
        self.model_start = None
        self.request_boundary = at

    def snapshot(self) -> dict:
        return {"model": self.model, "stage": self.stage, "last": self.last,
                "turn_id": self.turn_id, "turn_output_tokens": self.turn_output,
                "sample_count": self.sample_count, "output_total": self.output_total,
                "turn_started_at_ms": self.turn_started_at,
                "last_event_at_ms": self.event_at}


class SessionTail:
    def __init__(self, path: str, model: str | None = None, history_bytes: int = 8 * 1024 * 1024):
        self.path = Path(path)
        self.measurements = Measurements(model)
        self.offset = 0
        self.partial = b""
        self.history_bytes = history_bytes
        self.initialized = False
        self.identity: tuple | None = None
        self.anchor = b""
        self.source_state = "waiting"
        self.file_size = 0
        self.file_mtime_ms: float | None = None
        self.mtime_ns: int | None = None

    def reset(self) -> None:
        self.measurements = Measurements(self.measurements.model)
        self.offset = 0
        self.partial = b""
        self.initialized = False
        self.anchor = b""

    def update(self) -> None:
        try:
            stat = self.path.stat()
            size = stat.st_size
            identity = (stat.st_dev, stat.st_ino)
            if size < self.offset or (self.identity is not None and identity != self.identity):
                self.reset()
            self.identity = identity
            self.file_size = size
            self.file_mtime_ms = stat.st_mtime * 1000
            self.source_state = "ok"
            unchanged = self.mtime_ns == stat.st_mtime_ns
            self.mtime_ns = stat.st_mtime_ns
            if self.initialized and size == self.offset and unchanged:
                return
            if self.initialized and size == self.offset and not unchanged:
                self.reset()  # Same-length rewrites can leave the last 64 payload bytes unchanged.
            # A chat left unwatched for days can have hundreds of MB of new logs.
            # Jump to recent history rather than publishing old samples while replaying it.
            if self.initialized and size - self.offset > 16 * 1024 * 1024:
                self.reset()
            with self.path.open("rb") as f:
                if self.initialized and self.anchor:
                    f.seek(max(0, self.offset - len(self.anchor)))
                    if f.read(len(self.anchor)) != self.anchor:
                        self.reset()  # Same file was rewritten and grew before the next poll.
                if not self.initialized:
                    self.offset = max(0, size - self.history_bytes)
                    f.seek(self.offset)
                    if self.offset:
                        f.readline()  # discard an incomplete first JSON line
                        self.offset = f.tell()
                    self.initialized = True
                f.seek(self.offset)
                data = f.read(16 * 1024 * 1024)
                self.offset = f.tell()
                f.seek(max(0, self.offset - 64))
                self.anchor = f.read(min(64, self.offset))
                self.source_state = "ok" if self.offset >= size else "catching_up"
        except OSError:
            self.source_state = "unavailable"
            return
        if not data:
            return
        lines = (self.partial + data).split(b"\n")
        self.partial = lines.pop()
        for line in lines:
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except (ValueError, UnicodeDecodeError):
                continue
            if isinstance(event, dict):
                self.measurements.feed(event)

    def source(self) -> dict:
        return {"path": str(self.path), "state": self.source_state, "size": self.file_size,
                "offset": self.offset, "modified_at_ms": self.file_mtime_ms}


class TailCache:
    """Cache by thread, but rebind whenever its active rollout path changes."""

    def __init__(self, maximum: int = 8):
        self.tails: collections.OrderedDict[str, SessionTail] = collections.OrderedDict()
        self.maximum = maximum

    def update(self, row: dict, force: bool = False) -> SessionTail | None:
        path = row.get("rollout_path")
        if not path:
            return None
        key = row["id"]
        tail = self.tails.get(key)
        if force or tail is None or os.path.normcase(str(tail.path)) != os.path.normcase(str(Path(path))):
            tail = SessionTail(path, row.get("model"))
            self.tails[key] = tail
        self.tails.move_to_end(key)
        tail.update()
        while len(self.tails) > self.maximum:
            self.tails.popitem(last=False)
        return tail


class ThreadRepository:
    def __init__(self, codex_home: Path):
        self.codex_home = codex_home.expanduser().resolve()
        self.database: Path | None = None
        self.state = "missing"
        self.columns: set[str] = set()
        self.rows: dict[str, dict] = {}

    def _connect(self):
        if self.database is None:
            raise sqlite3.OperationalError("No compatible database")
        return sqlite3.connect(self.database.as_uri() + "?mode=ro", uri=True, timeout=0.5)

    def _select(self) -> str:
        title = "COALESCE(NULLIF(name, ''), title)" if "name" in self.columns else "title"
        optional = [c if c in self.columns else f"NULL AS {c}" for c in ("model", "updated_at", "archived")]
        return f"SELECT id, {title} AS title, rollout_path, {', '.join(optional)} FROM threads"

    def _discover(self) -> None:
        # Codex can migrate to a new state_N.sqlite. Inspect only its thread schema.
        candidates = []
        for path in self.codex_home.glob("state_*.sqlite"):
            suffix = path.stem.removeprefix("state_")
            if suffix.isdigit():
                candidates.append((int(suffix), path))
        self.database = None
        self.columns = set()
        self.state = "unsupported" if candidates else "missing"
        # Never fall back to a retained old DB after an incompatible newer migration.
        for _, path in sorted(candidates, reverse=True)[:1]:
            try:
                with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=0.5)) as conn:
                    columns = {r[1] for r in conn.execute("PRAGMA table_info(threads)")}
                if {"id", "title", "rollout_path"} <= columns:
                    self.database, self.columns, self.state = path, columns, "ok"
                    return
            except (OSError, sqlite3.Error):
                self.state = "unavailable"

    def refresh(self) -> None:
        self._discover()
        try:
            with closing(self._connect()) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(self._select() + " ORDER BY updated_at DESC LIMIT 512").fetchall()
            self.rows = {row["id"]: dict(row) for row in rows}
        except (OSError, sqlite3.Error):
            self.rows = {}
            if self.database is not None:
                self.state = "unavailable"

    def title_matches(self, title: str) -> list[dict]:
        # Exact matching across the entire DB also covers old chats and duplicate titles.
        try:
            with closing(self._connect()) as conn:
                conn.row_factory = sqlite3.Row
                title_column = "COALESCE(NULLIF(name, ''), title)" if "name" in self.columns else "title"
                rows = conn.execute(
                    self._select() + f" WHERE {title_column} = ? ORDER BY updated_at DESC", (title,)).fetchall()
            return [dict(row) for row in rows]
        except (OSError, sqlite3.Error):
            return [r for r in self.rows.values() if r["title"] == title]


def read_selection(path: Path) -> dict:
    try:
        value = json.loads(path.read_text("utf-8-sig"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    for attempt in range(4):
        try:
            temporary.replace(path)
            return
        except PermissionError:
            time.sleep(0.015 * (attempt + 1))


def monitor(codex_home: Path, runtime: Path, parent_pid: int | None = None, once: bool = False,
            dashboard_enabled: bool = False) -> dict | None:
    from history import SessionCatalog
    catalog = SessionCatalog(codex_home)
    repository = catalog.repository
    if dashboard_enabled and not once:
        from dashboard import start_server
        start_server(codex_home, runtime, native_enabled=os.name == "nt")
    tails = TailCache()
    matched_at = 0.0
    selection_key = None
    last_refresh_id = None
    matches: list[dict] = []
    last_published = 0.0
    last_payload = None
    refresh_result = None
    while True:
        if parent_pid and os.name == "nt":
            import ctypes
            kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel.OpenProcess.argtypes = (ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong)
            kernel.OpenProcess.restype = ctypes.c_void_p
            kernel.GetExitCodeProcess.argtypes = (ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong))
            kernel.CloseHandle.argtypes = (ctypes.c_void_p,)
            handle = kernel.OpenProcess(0x1000, False, parent_pid)
            if not handle:
                return None
            code = ctypes.c_ulong()
            alive = kernel.GetExitCodeProcess(handle, ctypes.byref(code)) and code.value == 259
            kernel.CloseHandle(handle)
            if not alive:
                return None
        elif parent_pid:
            try:
                os.kill(parent_pid, 0)
            except ProcessLookupError:
                return None
            except PermissionError:
                pass
        selection = read_selection(runtime / "selection.json")
        title = selection.get("title", "")
        selected_id = selection.get("thread_id")
        refresh_id = selection.get("refresh_id")
        force = refresh_id != last_refresh_id
        last_refresh_id = refresh_id
        catalog.refresh(force=force or once)
        key = (title, selected_id)
        if key != selection_key or force or time.monotonic() - matched_at >= 0.5 or once:
            matches = catalog.title_matches(title) if title else []
            selection_key = key
            matched_at = time.monotonic()
        selected = next((r for r in matches if r["id"] == selected_id), None)
        if selection.get("binding_mode") == "manual" and selected_id:
            selected = catalog.rows.get(selected_id)
        if selected is None and len(matches) == 1 and selection.get("binding_mode") != "manual":
            selected = matches[0]
        status = "ok" if selected else "ambiguous" if len(matches) > 1 else "unbound"
        tail = tails.update(selected, force) if selected else None
        metrics = tail.measurements.snapshot() if tail else None
        if force:
            refresh_result = {"request_id": refresh_id, "completed_at_ms": time.time() * 1000,
                              "state": "ok" if tail and tail.source_state == "ok" else
                              "unavailable" if tail else status,
                              "sample_at_ms": tail.measurements.last_usage_at if tail else None}
        saved_range = read_selection(runtime / "range-result.json")
        range_result = saved_range if selected and saved_range.get("thread_id") == selected["id"] else None
        result = {"schema_version": 2, "collector_pid": os.getpid(),
                  "repository_state": repository.state,
                  "binding": status, "thread_id": selected["id"] if selected else None,
                  "title": title, "metrics": metrics, "source": tail.source() if tail else None,
                  "refresh": refresh_result, "range": range_result,
                  "matches": [{k: r.get(k) for k in ("id", "title", "model", "updated_at")} for r in matches],
                  "threads": [{"id": r["id"], "title": r["title"], "model": r["model"]} for r in list(catalog.rows.values())[:80]]}
        if once:
            result["updated_at_ms"] = time.time() * 1000
            return result
        if result != last_payload or time.monotonic() - last_published >= 1:
            last_payload = result.copy()
            result["updated_at_ms"] = time.time() * 1000
            atomic_json(runtime / "metrics.json", result)
            last_published = time.monotonic()
        time.sleep(0.1)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--codex-home", type=Path, default=Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex"))
    parser.add_argument("--runtime", type=Path, default=Path(__file__).resolve().parent / "runtime")
    parser.add_argument("--parent-pid", type=int)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--dashboard", action="store_true", help="Start the local historical statistics panel")
    args = parser.parse_args()
    result = monitor(args.codex_home, args.runtime, args.parent_pid, args.once, args.dashboard)
    if result is not None:
        print(json.dumps(result, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
