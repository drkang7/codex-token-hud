"""Portable HUD selection and presentation, independent of any GUI toolkit."""
from __future__ import annotations

import math
import time

from metrics import atomic_json


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def display_number(value):
    return f"{value:,.1f}" if number(value) else "—"


def choose_thread(threads, pinned):
    """Activity following is explicit; never claim to know the foreground chat."""
    if pinned:
        return next((t for t in threads if t["id"] == pinned), None)
    if not threads:
        return None
    latest = max(t["updated_at_ms"] for t in threads)
    matches = [t for t in threads if t["updated_at_ms"] == latest]
    return matches[0] if len(matches) == 1 else None


class OverlayState:
    def __init__(self, service):
        self.service = service
        self.bound = object()  # Clear any stale bound ID on the first snapshot too.

    def snapshot(self, force=False):
        # The GUI worker acquires this non-blockingly so a long browser history
        # calculation never freezes the window or its controls.
        with self.service.lock:
            listing = self.service.get("threads", {"force": ["1"]} if force else {})
            threads, pinned = listing["threads"], listing.get("pinned_thread_id")
            row = choose_thread(threads, pinned)
            thread_id = row["id"] if row else None
            if thread_id != self.bound:
                atomic_json(self.service.runtime / "metrics.json", {"thread_id": thread_id})
                self.bound = thread_id
            query = {"thread": [thread_id]}
            if force:
                query["force"] = ["1"]
            live = self.service.get("live", query) if row else None
            return {"threads": threads, "pinned_thread_id": pinned, "thread": row, "live": live,
                    "updated_at_ms": time.time() * 1000}

    def command(self, name, thread_id=""):
        if name == "pin":
            self.service.post("pin", {"thread_id": thread_id})
        elif name == "follow":
            self.service.post("unpin", {})
        elif name == "latest":
            self.service.post("clear", {"thread_id": thread_id})
        elif name != "refresh":
            raise ValueError("Unknown HUD command")
        return self.snapshot(force=name == "refresh")


def presentation(snapshot, now_ms=None):
    """Never display expired, unreadable, wrong-model or previous-turn live counts."""
    now_ms = time.time() * 1000 if now_ms is None else now_ms
    row, live = snapshot.get("thread"), snapshot.get("live")
    result = {"title": row["title"] if row else "", "model": "", "rate": "—", "cache": "—",
              "kind": "waiting", "at_ms": None, "range": False, "sample_count": 0}
    if snapshot.get("error"):
        result["kind"] = "error"
        return result
    if not row or not live:
        result["kind"] = "missing" if snapshot.get("pinned_thread_id") else "ambiguous" if snapshot.get("threads") else "empty"
        return result
    measurements, source = live.get("metrics") or {}, live.get("source") or {}
    result["model"] = measurements.get("model") or row.get("model") or ""
    selected = live.get("range")
    if selected and selected.get("thread_id") == row["id"]:
        result.update(rate=display_number(selected.get("rate")), cache=display_number(selected.get("cache_percent")),
                      model=" / ".join(selected.get("models") or []) or result["model"], range=True,
                      kind="range", at_ms=selected.get("confirmed_at_ms"), sample_count=selected.get("sample_count", 0))
        return result
    sample = measurements.get("last") or {}
    at = sample.get("measured_at_ms")
    result["at_ms"] = at
    age = now_ms - at if number(at) else float("inf")
    previous_turn = (measurements.get("turn_started_at_ms") or 0) > (at or 0) and measurements.get("stage") != "idle"
    current_model = bool(sample) and sample.get("model") == measurements.get("model")
    if source.get("state") != "ok":
        result["kind"] = "unreadable"
    elif not sample:
        result["kind"] = "waiting"
    elif age >= 15 * 60 * 1000 or age < -60 * 1000:
        result["kind"] = "history"
    elif not current_model or previous_turn:
        result["kind"] = "pending"
    else:
        result.update(rate=display_number(sample.get("rate")), cache=display_number(sample.get("cache_percent")), kind="current")
    if result["kind"] not in ("unreadable", "history") and measurements.get("stage") in ("tools", "generating"):
        result["kind"] = measurements["stage"]
    return result
