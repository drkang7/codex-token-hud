# Codex Token HUD 1.3.0-beta.1

Select a time interval or the first/last user messages, then confirm to see weighted average output speed and cache hit fraction across complete local history. Includes the last selected message's responses, handles resumed log segments, and reports missing-data coverage. The matching Windows HUD can show the confirmed range or return to the latest response.

- Portable browser dashboard and terminal reports use existing Python 3.10+ on Windows/macOS/Linux and other compatible Python hosts; no pip dependencies.
- Local Desktop/CLI/IDE logs, archived/offline JSONL, database-free file discovery, CODEX_HOME, WSL and SSH forwarding.
- Browser mini-window, plus the original draggable/resizable native Windows strip and saved layout.
- Exact-ID Windows pinning from the dashboard, including CLI/IDE conversations, with separate pinned/automatic layouts.
- AnyCPU Windows executable with architecture-matching x64/ARM64/x86 private-Python package options.
- Manual refresh rescans rollouts, rereads the latest file, returns visible acknowledgement, and distinguishes no new usage from failure.
- Same-size log rewrites are detected and reread.
- Loopback-only token-protected dashboard. User message excerpts stay in browser/process memory; saved statistics omit message text. No credentials or external runtime requests.

For Windows x64, extract the entire `win-x64.zip` and run `CodexTokenHud.exe` (.NET Framework 4.8 required). `StartDashboard.ps1` starts the browser alternative using private Python. The source `dashboard.zip` runs with `python3 dashboard.py`. ARM64/x86 packages are execution candidates with explicit hardware-validation limits. Windows 11 ARM64 native Framework support requires 4.8.1. The native EXE is unsigned and may request elevation to match an elevated Codex window.

Only readable compatible local logs can be measured; cloud-only tasks are unavailable. Non-Windows interfaces use manual conversation selection and do not supply a native overlay. Shared parsing, range and local-service checks passed on Windows, macOS and Ubuntu in [GitHub CI](https://github.com/drkang7/codex-token-hud/actions/runs/37965804033); this does not verify real Codex UI behavior or every CPU combination. Exact current-chat weekly allowance percentage remains unavailable.

See README and docs/VALIDATION.md for formulas, privacy, verification scope, and troubleshooting.
