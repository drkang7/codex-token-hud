# Validation and limits

This record describes local verification of **1.2.0-beta.1** on 2026-10-06. It contains no real chat identifiers, titles, or machine paths.

## Automated checks

- 21 Python tests cover usage/timing, canonical and legacy deduplication, cache denominators, missing data, split UTF-8 / partial JSONL, resumed file paths, replacement/rewriting, manual refresh, collector append latency, exact title binding, and database schema/version discovery. Incompatible newer databases cannot silently fall back to retained older metadata.
- 16 C# checks cover freshness, new turns, heartbeat loss, missing logs, model/chat changes, database failures, Windows argument quoting, portable Python selection, CODEX_HOME, and per-user configuration.
- The extracted portable ZIP is tested with system Python removed from PATH. The packaged C# launcher verifies bundled Python; the bundled `pythonw.exe` collector reads an artificial `state_6.sqlite` and synthetic JSONL from a temporary path containing spaces and Chinese characters. Expected result: 20 tok/s and 75% cache. Archive checks reject real settings, runtime folders, inspection extracts, session logs, and databases; Python's license must be present.

## Native Windows check

The HUD was verified with Codex Desktop **26.930.7945** at **150%** display scaling on Windows x64. Native hit testing covers the drag area, all resize edges/corners, and the close button. The published image captures only the HUD. Live telemetry binding and per-user layout migration are checked independently of synthetic numeric fixtures.

## What remains unverified

GitHub-hosted CI has not run until the first push. Its workflows use the same local scripts but a hosted runner is a separate environment. Python 3.10/3.12 and other Windows machines are included in the CI plan; the local primary interpreter is Python 3.14. Windows UI language beyond Chinese/English, other Codex versions/layouts, mixed display scaling, ARM64, cloud-only chats, and non-Windows platforms are unverified.

Internal telemetry fields and accessibility layout can change. Versioned database discovery only supports schemas with compatible thread metadata; it does not prove all future Codex releases work. Duplicate chat titles require explicit user binding. Historical tails are bounded, so this HUD is not a complete conversation accounting ledger.

Token speed is a completed-response average. Exact instantaneous token speed and exact per-chat weekly allowance consumption are unavailable from the exposed records. A placeholder is intentionally retained for the latter.
