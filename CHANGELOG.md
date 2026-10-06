# Changelog

## 1.2.0-beta.1 — 2026-10-06

First public distribution candidate. Windows x64 portable ZIP includes a pinned, checksum-verified private Python runtime. Added MIT license, English and Chinese documentation, privacy guidance, automated Windows test/build and draft prerelease workflows, and an extracted-package smoke test with synthetic telemetry.

Moved writable HUD state to the current user's LocalAppData directory, preserving a legacy layout on first launch. Added `CODEX_HOME` and settings overrides, relative runtime discovery, database version/schema discovery, and explicit unavailable/incompatible database states. No individual-chat weekly quota estimate is supplied.

## 1.1.0 — 2026-10-06

Fixed resumed chats continuing to read their previous rollout file, and mismatched canonical/legacy cumulative counters suppressing new statistics. Added source replacement/truncation handling, bounded recent history, 100 ms tail polling, sample age, stale/new-turn display guards, manual refresh, and collector heartbeat recovery.

## 1.0.0 — 2026-10-02

Initial local Windows HUD: current model, response-average output token speed, input cache fraction, draggable/resizable native strip, saved layout, tray menu, and optional logon startup.
