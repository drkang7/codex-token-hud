# Codex Token HUD 1.3.0-beta.5

Native macOS/Linux floating HUDs now show output speed, input cache fraction, model and sample time. The strip moves/resizes, saves layout, stays visible across normal applications where the desktop honors topmost requests, and restores the same instance on relaunch. Choose and pin a conversation by exact ID, or explicitly follow the latest recorded activity. This is distinct from the original Windows foreground-conversation detector. Browser range results and pin/unpin changes synchronize with the matching strip.

Four native build targets package Python/Qt: macOS Intel and Apple Silicon, Linux x64 and ARM64. The source launcher installs its optional GUI dependency in a private environment; browser/terminal tools remain dependency-free. Cocoa properties and X11 window-manager state are checked with synthetic telemetry in the native jobs, followed by launching the bundled application. See VALIDATION.md for actual completed runs. Pure Wayland stacking/positioning remains compositor-controlled; the app prefers available XWayland unless explicitly overridden. macOS packages are ad-hoc signed, not notarized.

Dashboard UI update: range averages lead the workspace, latest-response values and Windows binding controls have separate sections, and the return/pin/unpin actions are recognizable filled buttons before hovering. Focus, pending requests, inline validation, keyboard tabs, narrow screens and mini-window layouts are handled explicitly. Binding state is reread from live metadata, including changes made from another window.

Windows menu fix: **显示状态栏** is disabled while the strip is already displayed. Repeated show requests keep its current conversation instead of restarting automatic identification. A hidden or minimized strip can still be restored. See docs/UI_DESIGN.md and docs/VALIDATION.md for design and regression evidence.

Windows display fix: checks actual native visibility/topmost state, repairs inconsistent z-order and restores minimized startup without taking focus. Starting another copy, double-clicking the tray icon or choosing **显示状态栏** brings back the existing strip. Launchers and new shortcuts use normal display; legacy minimized shortcuts are recovered by the app. Native-state regressions supplement the earlier unpin lifecycle checks; shared Python statistics are unchanged.

Windows fix: unpinning keeps a visible waiting strip until automatic discovery finds a foreground window. Both right-click menus always retain the ID-pinning entry. The HUD is independent of the followed window's lifetime and does not display the formerly pinned chat's measurements while waiting. Twelve targeted binding/lifecycle checks passed locally; shared Python analysis is unchanged from beta.1.

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

Only readable compatible local logs can be measured; cloud-only tasks are unavailable. Native macOS/Linux HUDs use exact-ID selection or latest-activity following. Earlier shared parsing, range and local-service checks passed on Windows, macOS and Ubuntu in [GitHub CI](https://github.com/drkang7/codex-token-hud/actions/runs/37965804033); this does not verify real Codex UI behavior or every CPU combination. Exact current-chat weekly allowance percentage remains unavailable.

See README and docs/VALIDATION.md for formulas, privacy, verification scope, and troubleshooting.
