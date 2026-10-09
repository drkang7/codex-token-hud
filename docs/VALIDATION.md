# Validation and limits

## 1.3.0-beta.1 — local checks on 2026-10-10

Targeted checks on Windows x64 / Python 3.14.8:

- Existing 21 collector/parser regressions passed once after the collector changes.
- 13 new historical-range and local-server cases passed incrementally. They cover weighted denominators, inclusive completion-time bounds, inclusion of the last message's response, repeated-message selection, missing telemetry, canonical/legacy dedup, resumed segment gaps, history beyond the live tail, stable message IDs, database-free titles, offline EOF records, manual ID binding, same-size rewrites, loopback token/Origin/Host validation, and refresh acknowledgement while the database retains the previous path. Two fixture cleanup failures were corrected by closing fixture SQLite connections; only affected cases were rerun.
- 19 C# presentation/configuration checks passed, including confirmed ranges, conversation-ID isolation, and collector disconnection. AnyCPU compilation succeeded. Native hit geometry was unchanged; earlier broad native tests were not repeated.
- Browser interactions exercised both selection modes, confirmation and persisted results using artificial logs. The complete time range returned 3,116 output tokens / 92 s = 33.8696 tok/s and 54,000 / 61,000 cached/input = 88.5246%. Selecting the first through third user messages included the third answer and excluded the fourth: 2,466 / 72 s = 34.25 tok/s; 39,600 / 45,000 = 88% cache. Screenshots use this artificial fixture only.
- The terminal entry point ran in Python isolated mode and returned the same weighted time-range values. The bundled Windows x86 Python also ran this report successfully on the current Windows x64 host; this does not verify a 32-bit OS or x86 native HUD.
- Complete history of the current local conversation was parsed across multiple resumed segments. The browser-confirmed one-hour result synchronized to the native HUD: 31.9 tok/s, 93.8% cache, 56 responses. Browser pin/unpin feedback and exact-ID binding were observed, with a separate pinned layout saved. The installed native copy was rebuilt; no real message bodies are included in public screenshots or artifacts.
- Official x64/ARM64/x86 Python download digests were checked for packaging. No逐文件哈希 or repeat full-package smoke run was performed; only download integrity and ZIP distribution checksums are used.

The current local Codex installation is 26.1002.7124.0. Header discovery now accepts an exact known local chat title when menu wording has changed. Current native telemetry binding is checked separately from artificial average values.

The [GitHub CI run for commit cbbf986](https://github.com/drkang7/codex-token-hud/actions/runs/37965804033) passed on 2026-10-10 (Asia/Shanghai): Windows Python 3.10/3.12/3.14, Ubuntu Python 3.10, macOS Python 3.14, and Windows portable packaging. Each Python job ran all 34 collector/range/server tests; Windows jobs also ran the 19 C# checks and compiled AnyCPU. The initial run exposed two test assertions comparing path spelling instead of file identity (Windows short names and macOS aliases); they were corrected to check the actual file, then passed. Packaging did not repeat the test matrix or run an extra smoke test.

Windows x64 source, local server and UI were exercised locally. macOS/Ubuntu CI validates shared code with synthetic logs, not those platforms' real Codex UI or every architecture. ARM64 and x86 ZIPs are built candidates, not proof of execution on ARM64 hardware or a 32-bit OS. WSL was unavailable on this machine and was not installed. The portable source entry points remain conditional on an existing compatible Python runtime and readable local logs. No pure-cloud statistics, native macOS/Linux overlay, instantaneous per-token stream or per-conversation weekly quota measurement is claimed.

## Earlier 1.2.0-beta.1 verification

This record describes local verification of **1.2.0-beta.1** on 2026-10-06. It contains no real chat identifiers, titles, or machine paths.

## Automated checks

- 21 Python tests cover usage/timing, canonical and legacy deduplication, cache denominators, missing data, split UTF-8 / partial JSONL, resumed file paths, replacement/rewriting, manual refresh, collector append latency, exact title binding, and database schema/version discovery. Incompatible newer databases cannot silently fall back to retained older metadata.
- 16 C# checks cover freshness, new turns, heartbeat loss, missing logs, model/chat changes, database failures, Windows argument quoting, portable Python selection, CODEX_HOME, and per-user configuration.
- The extracted portable ZIP is tested with system Python removed from PATH. The packaged C# launcher verifies bundled Python; the bundled `pythonw.exe` collector reads an artificial `state_6.sqlite` and synthetic JSONL from a temporary path containing spaces and Chinese characters. Expected result: 20 tok/s and 75% cache. Archive checks reject real settings, runtime folders, inspection extracts, session logs, and databases; Python's license must be present.

## Native Windows check

The HUD was verified with Codex Desktop **26.930.7945** at **150%** display scaling on Windows x64. Native hit testing covers the drag area, all resize edges/corners, and the close button. The published image captures only the HUD. Live telemetry binding and per-user layout migration are checked independently of synthetic numeric fixtures.

## What remains unverified

The [first GitHub-hosted Windows CI run](https://github.com/drkang7/codex-token-hud/actions/runs/37492761938) passed on 2026-10-07: all three Python matrix jobs (3.10, 3.12, 3.14) and the portable package job succeeded. These validate synthetic telemetry and packaging on a hosted runner; they do not verify Codex's native UI on additional users' computers.

Windows UI language beyond Chinese/English, other Codex versions/layouts, mixed display scaling, ARM64, cloud-only chats, and non-Windows platforms remain unverified.

Internal telemetry fields and accessibility layout can change. Versioned database discovery only supports schemas with compatible thread metadata; it does not prove all future Codex releases work. Duplicate chat titles require explicit user binding. Historical tails are bounded, so this HUD is not a complete conversation accounting ledger.

Token speed is a completed-response average. Exact instantaneous token speed and exact per-chat weekly allowance consumption are unavailable from the exposed records. A placeholder is intentionally retained for the latter.
