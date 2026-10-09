# Changelog

## 1.3.0-beta.1 — 2026-10-10

Added a local browser panel for selecting a time interval or the first/last user messages. Confirmation calculates output-token/time-weighted speed and input-token-weighted cache fraction over complete history, including the last selected message's responses. Missing telemetry is excluded separately with coverage counts. Confirmed results are fixed snapshots, synchronized to the matching Windows HUD; users can return to the latest response.

Added standard-library-only browser and terminal entry points for Python 3.10+ hosts, including macOS/Linux/Windows, offline JSONL, archived logs, CLI/IDE local sessions, WSL and SSH forwarding. The browser mini-window is movable and resizable by the OS. File discovery works without a compatible database and combines resumed segments by conversation ID. Native Windows builds are now AnyCPU, with x64/ARM64/x86 private-Python packaging options; untested host architectures remain marked as such.

Fixed manual refresh to rescan active rollouts, even when the database's saved path has not changed, and publish an acknowledgement. The HUD shows pending/success/unavailable/no-new-count feedback and reconnects an unresponsive collector. Added targeted range, refresh and loopback-access checks plus macOS/Linux CI configuration. No per-conversation weekly quota estimate was introduced.

Added exact-ID pinning from the dashboard to keep the Windows HUD visible for Desktop/CLI/IDE chats when automatic title discovery is unavailable. Automatic and pinned modes keep separate saved layouts. Fixed same-size log rewrites so changed telemetry is reread rather than retaining an earlier sample.

## 1.2.0-beta.1 — 2026-10-06

First public distribution candidate. Windows x64 portable ZIP includes a pinned, checksum-verified private Python runtime. Added MIT license, English and Chinese documentation, privacy guidance, automated Windows test/build and draft prerelease workflows, and an extracted-package smoke test with synthetic telemetry.

Moved writable HUD state to the current user's LocalAppData directory, preserving a legacy layout on first launch. Added `CODEX_HOME` and settings overrides, relative runtime discovery, database version/schema discovery, and explicit unavailable/incompatible database states. No individual-chat weekly quota estimate is supplied.

## 1.1.0 — 2026-10-06

Fixed resumed chats continuing to read their previous rollout file, and mismatched canonical/legacy cumulative counters suppressing new statistics. Added source replacement/truncation handling, bounded recent history, 100 ms tail polling, sample age, stale/new-turn display guards, manual refresh, and collector heartbeat recovery.

## 1.0.0 — 2026-10-02

Initial local Windows HUD: current model, response-average output token speed, input cache fraction, draggable/resizable native strip, saved layout, tray menu, and optional logon startup.
