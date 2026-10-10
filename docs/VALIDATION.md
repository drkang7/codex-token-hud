# Validation and limits

## 1.3.0-beta.5 — native macOS/Linux overlay

On Windows x64 / Python 3.14.8 / Qt 6.10.3, the complete Python regression suite passed **54 tests** after adding the initial 20 overlay checks. An additional minimum-layout/screenshot check then passed, bringing the current suite to 55 checks. The overlay checks cover latest-activity selection, exact pin/unpin, missing logs, tied timestamps, external range/binding changes, force reread, model/turn/age guards, window recovery, unavailable trays, saved layout, exact-ID search, repeat-launch IPC and range display. The test harness explicitly flushes Qt deferred deletion between own-window fixtures; it does not automate Codex.

A separate source-process launch with synthetic logs confirmed **500 output tokens / 5 seconds = 100.0 tok/s**, **1,500 / 2,000 = 75.0% cache**, a visible window, packaged-style local assets/API access, range/clear/unpin, repeat launch preserving the same real HUD process and graceful exit. Windows virtual-environment launchers may have a different parent PID, so recovery compares the original HUD's reported PID. No real log contents or IDs are used.

The normal and compact native layouts were captured with artificial data at 850×160 and 640×160 logical pixels. Action buttons fit and remain visibly bordered without hovering. Node syntax checking and shell syntax checking passed. The source ZIP uses an explicit public-file list and executable metadata for shell/macOS launchers. Dependency license texts are included; the browser/terminal paths do not import Qt.

Four native CI jobs are configured for macOS Intel/Apple Silicon and Linux x64/ARM64. They install Qt, run own-window regressions under Cocoa or X11/Openbox, build an onedir app, then launch that bundled app with synthetic telemetry and check actual Cocoa properties or X11 `_NET_WM_STATE_ABOVE`. Actual run results will be recorded here after completion. A configured job alone is not evidence of a passed native run. There is no real Codex desktop acceptance on those machines, full Spaces/full-screen workflow proof, or native Wayland compositor verification. Per-conversation weekly allowance remains unavailable.

## 1.3.0-beta.4 — dashboard and repeated-show checks on 2026-10-10

The existing complete local regression script passed three consecutive times on Windows x64 / Python 3.14.8: **34 Python tests, 19 C# presentation/configuration checks and 24 native binding/lifecycle checks in every run**. The three new native cases assert that showing an already displayed strip preserves its view and title, disables the redundant menu action, and retains recovery for a hidden strip. Own-form fixtures do not control Codex. JavaScript syntax checking with Node 24.21.0 and the diff whitespace check also passed.

The final browser code completed three consecutive real UI/API round trips using isolated synthetic logs: confirm all history, clear its snapshot, pin, reload and reread the fixed state, unpin, reload and reread automatic mode. Each confirmation returned **10,019 output tokens / 279.0 s = 35.9 tok/s**, **93.4%** weighted cache and **14** samples. Additional checks exercised first/last message selection, invalidation after query editing, retained inputs/previous result on validation failure, keyboard tabs, and a separately changed binding becoming visible through live polling. Selecting the first three responses returned **2,056 / 55.6 = 37.0 tok/s**, **92.0%** cache and **3** samples. Appending a synthetic 200-token / 10-second response yielded **20.0 tok/s and 80.0% cache** after refresh, while the confirmed range snapshot stayed unchanged; polling may already have read that append before the refresh button was clicked.

Actual screenshots and geometry were checked at 1280×900, 390×844 and 500×590. Critical actions measure 44px high; confirmation measures 48px. Mobile confirmation scrolls its result into view. At 390px the content client width is 375px with a scrollbar, and the result region leaves approximately 16px on both sides; the 500px mini-window has client/scroll width 485px. Normal viewport captures show the full margins. The host's full-page narrow capture crops the scrollbar width, so the earlier narrow full-page images are not evidence of missing padding. Normal enabled-state contrast is 10.73:1 for button text, 8.39:1 for secondary text on the surface, 3.09:1 for control border against button fill and 9.79:1 for primary-button text; these are color calculations, not a complete accessibility audit. Browser error/warning logs were empty in the final flow.

An independent Oil UI Pro existing-interface review confirmed the default button affordances and desktop hierarchy. Follow-up fixes make the automatic-follow object explicit, tighten the mini-window header, unify button heights and remove repeated text. Motion evidence records range-tab movement, numeric confirmation feedback and panel entrance. The screenshot clip coordinates were corrected from viewport to page coordinates; the complete numeric card is included. Some middle frames are near the animation's end, so full animation feel is not claimed. The host did not apply browser zoom shortcuts: actual 200% browser reflow and reduced-motion OS preference switching remain unverified, although the source supplies a reduced-motion path.

The installed root executable was rebuilt as **1.3.0-beta.4** and restarted. Its native status confirmed visible, topmost, not minimized, uncloaked and no display error. A local API pin/show/unpin integration check kept the same HUD process, conversation, title, mode and waiting state during the duplicate launch, then restored the original automatic mode with the same visible process. This is application/native-state evidence on this host; it is not a new user visual acceptance report or a check on another machine. Local harness setup mistakes were corrected before the passing integration check.

The shared parsing/statistics formulas and runtime versions are unchanged. Local Windows and source-dashboard ZIPs use the public-file allowlist; no additional per-file hashing or package smoke rerun was needed. macOS/Linux and ARM64/x86 execution were not repeated for this UI/native menu change. The previous CI evidence below remains limited to the code and platforms it actually ran.

## 1.3.0-beta.3 — native Windows display checks on 2026-10-10

Twenty-one focused own-form checks passed on the current Windows x64 host. The added cases reproduce WinForms' cached visibility/topmost differing from native state, a topmost style inconsistent with the native z-order band, hidden windows, and minimized legacy launches. Recovery verifies native visibility/topmost and unchanged foreground focus. The earlier unpin, ID-picker and window-lifetime cases also passed. Fixtures use temporary data and this test's own forms; they do not control Codex. Failed restore attempts were corrected before this passing run.

The final rebuilt installed copy was deliberately launched minimized and then launched again. Its native status confirmed a visible topmost, non-minimized, uncloaked HUD with no display error; the second launcher exited and the same existing instance acknowledged the show request. During diagnosis the user also reported seeing the strip. These observations cover this local host, not additional machines. The earlier beta.2 application's managed `Visible` property had been insufficient evidence of actual display; beta.3 records native state instead. Shared Python code is unchanged, so the shared-code matrix and full-package smoke were not repeated.

## 1.3.0-beta.2 — targeted Windows checks on 2026-10-10

Twelve own-form binding/lifecycle checks passed on the current Windows x64 host. They exercise a real menu unpin handler, visible waiting state and position, immediate clearing of the former fixed selection and measurements, the permanent ID-pinning entry in both modes, waiting-strip movement without overwriting the automatic layout, discovery of the next conversation, waiting for the discovered process to be foreground, and the followed window closing without destroying the HUD. Fixtures use temporary local data and this test's own forms; they do not automate Codex's UI. AnyCPU compilation succeeded. No Python parser changes or full-package smoke rerun were needed; the beta.1 cross-platform CI below remains the shared-code evidence.

The rebuilt installed copy also completed a pin/unpin round trip through its local dashboard API. Its own status record confirmed the same HUD process remained alive and visible in automatic mode, with the collector continuing to update. This is application-state evidence; no new visual acceptance on other machines is claimed.

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
