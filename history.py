"""Local session discovery and weighted, historical usage measurements."""
from __future__ import annotations

import collections
import heapq
import hashlib
import json
from pathlib import Path
import re
import time

from metrics import Measurements, ThreadRepository, timestamp_ms


def events(path: Path):
    """Stream complete JSON records; ignore incomplete objects at the live EOF."""
    with path.open("rb") as stream:
        for line in stream:
            try:
                value = json.loads(line)
            except (ValueError, UnicodeDecodeError):
                continue
            if isinstance(value, dict):
                yield value


class SessionCatalog:
    """Group resumed rollouts by metadata ID, independent of the desktop database."""

    def __init__(self, codex_home: Path, logs=()):
        self.home = codex_home.expanduser().resolve()
        self.logs = [Path(p).expanduser().resolve() for p in logs]
        self.repository = ThreadRepository(self.home)
        self.files: dict[str, dict] = {}
        self.rows: dict[str, dict] = {}
        self.updated = 0.0

    @staticmethod
    def _inspect(path: Path, old: dict | None) -> dict:
        stat = path.stat()
        signature = (stat.st_size, stat.st_mtime_ns, stat.st_ino)
        if old and old["signature"] == signature:
            return old
        with path.open("rb") as stream:
            first = stream.readline(4 * 1024 * 1024)
            try:
                record = json.loads(first)
                meta = (record.get("payload") or {}) if record.get("type") == "session_meta" else {}
                if not isinstance(meta, dict):
                    meta = {}
            except (ValueError, UnicodeDecodeError, AttributeError):
                meta = {}
            stream.seek(max(0, stat.st_size - 64 * 1024))
            tail = stream.read().splitlines()
        at = timestamp_ms(meta.get("timestamp")) or 0
        recorded = None
        for line in reversed(tail):
            try:
                value = json.loads(line)
                recorded = timestamp_ms(value.get("timestamp"))
                if recorded is not None:
                    at = max(at, recorded)
                    break
            except (ValueError, UnicodeDecodeError, AttributeError):
                continue
        if recorded is None:
            at = max(at, stat.st_mtime * 1000)  # Discovery only; never used as sample timing.
        return {"path": str(path), "id": meta.get("id") if isinstance(meta.get("id"), str) else None, "signature": signature,
                "updated_at_ms": at, "created_at_ms": timestamp_ms(meta.get("timestamp")) or 0,
                "model": meta.get("model"), "cwd": meta.get("cwd") if isinstance(meta.get("cwd"), str) else "", "size": stat.st_size}

    def refresh(self, force=False) -> None:
        if not force and time.monotonic() - self.updated < 2:
            return
        self.repository.refresh()
        paths = set(self.logs)
        if not self.logs:
            for directory in (self.home / "sessions", self.home / "archived_sessions"):
                if directory.is_dir():
                    paths.update(directory.rglob("*.jsonl"))
            paths.update(Path(r["rollout_path"]) for r in self.repository.rows.values() if r.get("rollout_path"))
        found = {}
        for path in paths:
            try:
                key = str(path.resolve())
                info = self._inspect(path, self.files.get(key))
                if not info["id"] and path in self.logs:
                    info = dict(info, id="file:" + key)
                if info["id"]:
                    found[key] = info
            except OSError:
                continue
        self.files = found
        titles = {}
        try:
            for entry in events(self.home / "session_index.jsonl"):
                if entry.get("id") and isinstance(entry.get("thread_name"), str):
                    titles[entry["id"]] = entry["thread_name"]
        except OSError:
            pass
        grouped = collections.defaultdict(list)
        for info in found.values():
            grouped[info["id"]].append(info)
        rows = {}
        for thread_id, segments in grouped.items():
            latest = max(segments, key=lambda s: (s["updated_at_ms"], s["created_at_ms"]))
            row = dict(self.repository.rows.get(thread_id) or {})
            row.update(id=thread_id, title=row.get("title") or titles.get(thread_id) or Path(latest["cwd"]).name or thread_id,
                       model=row.get("model") or latest["model"], rollout_path=latest["path"],
                       updated_at_ms=latest["updated_at_ms"], segment_count=len(segments))
            rows[thread_id] = row
        self.rows = dict(sorted(rows.items(), key=lambda pair: pair[1]["updated_at_ms"], reverse=True))
        self.updated = time.monotonic()

    def segments(self, thread_id: str) -> list[Path]:
        return [Path(s["path"]) for s in sorted(self.files.values(),
                key=lambda s: (s["created_at_ms"], s["path"])) if s["id"] == thread_id]

    def title_matches(self, title: str) -> list[dict]:
        rows = {r["id"]: r for r in self.repository.title_matches(title)}
        for row in self.rows.values():
            if row["title"] == title or row["id"] in rows:
                rows[row["id"]] = row
        return list(rows.values())


def user_text(event: dict) -> str | None:
    p = event.get("payload") or {}
    if not isinstance(p, dict):
        return None
    if event.get("type") == "event_msg" and p.get("type") == "user_message":
        text = p.get("message")
    elif event.get("type") == "response_item" and p.get("type") == "message" and p.get("role") == "user":
        content = p.get("content") or []
        text = "\n".join(c.get("text", "") for c in content if isinstance(c, dict) and isinstance(c.get("text"), str))
    else:
        return None
    if not isinstance(text, str) or not text.strip():
        return None
    text = text.strip()
    # These are client-injected context records, not messages sent by the user.
    if text.startswith(("<environment_context>", "<permissions instructions>", "<collaboration_mode>",
                        "<user_instructions>", "# AGENTS.md instructions", "<turn_aborted>")):
        return None
    return text


class History:
    def __init__(self, paths: list[Path], model=None):
        self.samples: list[dict] = []
        self.messages: list[dict] = []
        self.warnings: list[str] = []
        measurements = Measurements(model)
        # Complete history needs dedup beyond the live collector's 256-response window.
        seen_responses = set()
        seen_messages = set()
        canonical = []
        fallback = []
        def ordered(path):
            try:
                for e in events(path):
                    yield (timestamp_ms(e.get("timestamp")) or 0, e)
            except OSError:
                self.warnings.append("有日志文件不可读，结果可能不完整")

        # Rollouts can overlap after resume. Merge by recorded time while keeping equal-time order.
        try:
            merged = heapq.merge(*(ordered(p) for p in paths), key=lambda pair: pair[0])
            for _, e in merged:
                p = e.get("payload") or {}
                if not isinstance(p, dict):
                    continue
                if e.get("type") == "session_meta":
                    # A resumed segment can begin halfway through a response. Do not time the gap.
                    measurements.request_boundary = None
                    measurements.model_start = None
                    measurements.pending_calls.clear()
                text = user_text(e)
                at = timestamp_ms(e.get("timestamp"))
                if text and at is not None:
                    key = (at, text)
                    if key not in seen_messages:
                        message = {"at_ms": at, "text": text}
                        if e.get("type") == "event_msg":
                            canonical.append(message)
                        else:
                            fallback.append(message)
                        seen_messages.add(key)
                if e.get("type") == "token_usage_record" and p.get("response_id"):
                    if p["response_id"] in seen_responses:
                        continue
                    seen_responses.add(p["response_id"])
                last = measurements.last
                measurements.feed(e)
                if measurements.last is not last:
                    self.samples.append(dict(measurements.last))
        except OSError:
            self.warnings.append("有日志文件不可读，结果可能不完整")
        # Canonical events are preferred per matching message, with a small emission-time tolerance.
        self.messages = list(canonical)
        canonical_times = collections.defaultdict(list)
        for message in canonical:
            canonical_times[message["text"]].append(message["at_ms"])
        for message in fallback:
            if not any(abs(at - message["at_ms"]) < 2000 for at in canonical_times[message["text"]]):
                self.messages.append(message)
        self.messages.sort(key=lambda m: m["at_ms"])
        for message in self.messages:
            message["id"] = str(int(message["at_ms"])) + ":" + hashlib.sha256(message["text"].encode()).hexdigest()[:16]
            message["preview"] = re.sub(r"\s+", " ", message["text"])[:240]
        self.last = measurements.snapshot()

    def find_messages(self, query="", limit=100):
        query = query.strip().casefold()
        matches = [m for m in self.messages if not query or query in m["text"].casefold()]
        return [{k: m[k] for k in ("id", "at_ms", "preview")} for m in matches[-limit:]]

    def calculate(self, selection: dict) -> dict:
        mode = selection.get("mode")
        end_exclusive = False
        if mode == "messages":
            ids = {m["id"]: i for i, m in enumerate(self.messages)}
            first, last = str(selection.get("first_id", "")), str(selection.get("last_id", ""))
            if first not in ids or last not in ids:
                raise ValueError("请先从搜索结果中选定首尾两条用户消息")
            a, b = ids[first], ids[last]
            if a > b:
                raise ValueError("首条消息必须早于或等于末条消息")
            start = self.messages[a]["at_ms"]
            end = self.messages[b + 1]["at_ms"] if b + 1 < len(self.messages) else float("inf")
            end_exclusive = True
            bounds = {"first": {k: self.messages[a][k] for k in ("id", "at_ms", "preview")},
                      "last": {k: self.messages[b][k] for k in ("id", "at_ms", "preview")}}
        elif mode == "time":
            start, end = timestamp_ms(selection.get("start")), timestamp_ms(selection.get("end"))
            if start is None or end is None or start > end:
                raise ValueError("请输入有效的起止时间，结束时间不能早于开始时间")
            bounds = {"start_ms": start, "end_ms": end}
        else:
            raise ValueError("请选择时间段或消息范围")
        selected = [s for s in self.samples if s["measured_at_ms"] >= start and
                    (s["measured_at_ms"] < end if end_exclusive else s["measured_at_ms"] <= end)]
        timed = [s for s in selected if s["rate"] is not None]
        cached = [s for s in selected if s["cache_percent"] is not None]
        seconds = sum(s["duration_ms"] for s in timed) / 1000
        output = sum(s["output_tokens"] for s in timed)
        inputs = sum(s["input_tokens"] for s in cached)
        cache = sum(s["cached_input_tokens"] for s in cached)
        basis = collections.Counter(s["basis"] for s in timed)
        models = sorted({s["model"] for s in selected if s["model"]})
        return {"mode": mode, "bounds": bounds, "rate": output / seconds if seconds else None,
                "cache_percent": cache * 100 / inputs if inputs else None,
                "output_tokens": sum(s["output_tokens"] for s in selected),
                "timed_output_tokens": output, "duration_seconds": seconds,
                "input_tokens": inputs, "cached_input_tokens": cache, "sample_count": len(selected),
                "timed_samples": len(timed), "cache_samples": len(cached), "timing_basis": dict(basis),
                "models": models, "warnings": self.warnings, "confirmed_at_ms": time.time() * 1000}


class HistoryCache:
    def __init__(self, maximum=3):
        self.entries = collections.OrderedDict()
        self.maximum = maximum

    def load(self, catalog: SessionCatalog, thread_id: str, force=False) -> History:
        paths = catalog.segments(thread_id)
        if not paths:
            raise ValueError("此对话没有可读的本地日志")
        signature = []
        for path in paths:
            try:
                stat = path.stat()
                signature.append((str(path), stat.st_size, stat.st_mtime_ns, stat.st_ino))
            except OSError:
                signature.append((str(path), None))
        cached = self.entries.get(thread_id)
        if force or not cached or cached[0] != signature:
            cached = (signature, History(paths))  # The latest DB model is not evidence of older responses' models.
            self.entries[thread_id] = cached
        self.entries.move_to_end(thread_id)
        while len(self.entries) > self.maximum:
            self.entries.popitem(last=False)
        return cached[1]
