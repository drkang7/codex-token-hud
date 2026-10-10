# Compatibility / 兼容范围

The shared collector, range analysis, local web service and terminal reports use only Python 3.10+ standard-library modules. They do not depend on Electron internals, a window title, an OS UI toolkit, a CPU architecture, pip packages or an account API.

| Environment | Interface | Requirements / validation boundary |
| --- | --- | --- |
| Windows x64 | Native draggable/resizable HUD; browser dashboard; terminal report | Native HUD requires .NET Framework 4.8 and an accessible local Codex Desktop window. Local Windows x64 checks passed. |
| Windows ARM64 | Browser dashboard and terminal report; AnyCPU HUD candidate | ARM64 private Python packaging is available. Native .NET Framework 4.8.1 on Windows 11 ARM64 or compatible emulation is needed for the HUD. No ARM64 hardware verification in this change. |
| Windows x86 | Browser dashboard and terminal report | x86 private Python packaging is available; the AnyCPU binary can also load under Framework 4.8, but Codex Desktop itself may not support this OS architecture. No 32-bit OS verification. |
| macOS, Intel / Apple Silicon | Native Qt floating HUD; browser dashboard; terminal report | Native packages bundle Python/Qt. Qt 6.9.3 requires macOS 12+; Python 3.14 source uses Qt 6.10.3 and macOS 13+. Cocoa window/bundled-launch CI is configured on Intel and ARM64; passed runs are recorded in VALIDATION.md. Real Codex UI use on a Mac remains a separate validation boundary. |
| Linux x64 / ARM64 | Native Qt floating HUD; browser dashboard; terminal report | x64 packages target Ubuntu 22.04+ / glibc 2.35+; ARM64 packages need glibc 2.39+ (e.g. Ubuntu 24.04). Qt/XCB or Wayland system libraries and a graphical desktop are needed. Native X11/bundled-launch CI is configured on both architectures. |
| Other Linux Python architectures | Browser dashboard; terminal report | Shared tools use Python 3.10+ with SQLite. A Qt source HUD is conditional on a compatible PySide6 installation; official wheels are primarily x64/ARM64. Other CPU combinations are not claimed as native-package support. |
| WSL / SSH / headless hosts | Browser through local forwarding; terminal report | Run alongside the local logs. Forward the same chosen loopback port to your own computer. No public listening address. |
| Other systems with compatible Python, e.g. BSD or Android Python environments | Terminal report; browser where loopback sockets are available | Conditional portability of source only; requires readable Codex-format logs. Not device-tested; no bundled runtime or Codex client is promised. |

“支持”指工具具备对应入口和代码路径；未实机验证的平台不能视为已通过端到端验收。浏览器模式可以选择任意本地对话，Windows 原生状态栏默认通过无障碍标题识别当前桌面对话，也可从它的面板按 ID 固定一个 CLI/IDE/桌面对话并置顶显示。

## Native macOS/Linux desktop strip

`overlay.py` uses official Qt for Python Widgets, with optional dependencies in `requirements-overlay.txt`. Python 3.10–3.13 selects Qt 6.9.3 to retain macOS 12 and older x64 glibc compatibility; Python 3.14 selects Qt 6.10.3. The browser/terminal tools still need only the standard library. Native packages include Python 3.13, Qt shared libraries and the local dashboard assets. Build on each target OS with `python PackageOverlay.py`; the builder does not cross-compile or collect local state.

- **macOS:** a native NSPanel remains visible when inactive, uses a floating level, and sets `canJoinAllSpaces` / `fullScreenAuxiliary` on its own window. The beta is ad-hoc signed, not notarized. These native properties are checked in Cocoa CI; all actual Spaces/full-screen workflows with Codex are not hardware-verified here.
- **Linux X11 / XWayland:** uses the window-manager topmost request, system drag/resize and saved layout. With `XDG_SESSION_TYPE=wayland` and an available `DISPLAY`, it prefers XCB/XWayland unless `QT_QPA_PLATFORM` was explicitly set. X11 CI uses Xvfb with Openbox and checks the actual `_NET_WM_STATE_ABOVE` property. Other window managers may apply different rules.
- **Pure Wayland:** starts with Qt's Wayland backend when XWayland is unavailable, or when explicitly selected with `QT_QPA_PLATFORM=wayland`. System drag/resize remains available, but global positioning, restoring exact screen coordinates and always-on-top are compositor-controlled. Configure a desktop window rule if needed; this app cannot promise universal topmost behavior. Native Wayland compositor sessions are not covered by the X11 tests.
- **Missing tray:** the strip keeps its normal taskbar window on Linux and disables hiding. If a tray disappears, a hidden strip is restored. Reopening the application restores the existing instance without changing its binding. Closing a window without a tray exits the tool instead of leaving an inaccessible process.

Exact-ID pinning and explicitly labeled latest-activity following are available on both systems. Latest activity may belong to a background conversation and is not a foreground-window detector. Equal newest timestamps require manual selection. Range snapshots and browser pin/unpin synchronize through the same local service. A missing pinned log is shown as unavailable and can be unpinned without requiring that log to exist.

Run `sh start-overlay.sh` to create a private Qt virtual environment on first source launch, or double-click `StartOverlay.command` on macOS. Debian/Ubuntu source installs may need `python3-venv`. If XCB libraries are missing, install `libxcb-cursor0 libxkbcommon-x11-0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-render-util0 libxcb-xinerama0 libegl1`; a desktop normally supplies most already. Source Qt 6.9.3 x64 wheels require glibc 2.28+; the prebuilt x64 application has the higher Ubuntu 22.04 build baseline. ARM64 wheels require glibc 2.39+. For headless hosts use the browser/terminal entry points.

See [Qt platform requirements](https://doc.qt.io/qtforpython-6/overviews/qtdoc-supported-platforms.html), the pinned [Qt 6.9.3 wheels](https://pypi.org/project/PySide6-Essentials/6.9.3/), [Qt window flag behavior](https://doc.qt.io/qtforpython-6/PySide6/QtCore/Qt.html) and [third-party notices](../THIRD_PARTY.md). Dependency baselines describe what the packages require, not proof that every OS version was tested.

## Codex clients and logs

The dashboard can consume compatible local rollouts from Desktop, CLI and IDE extensions. It reads both `token_usage_record` and legacy `event_msg/token_count`, and groups resumed segments by `session_meta.payload.id`. A compatible SQLite database adds readable conversation titles; missing or incompatible databases do not prevent file-based selection. `CODEX_HOME`, `--codex-home`, archived sessions and explicit `--log` are supported. No authentication files are read.

The [official CLI guide](https://developers.openai.com/codex/cli) documents terminal use on macOS/Linux and Windows. The [official IDE guide](https://developers.openai.com/codex/ide) describes editor integration. This project's compatibility comes from the recorded local telemetry, rather than a guarantee about every client version. A cloud-only conversation without a readable local log is unavailable.

## Run on any supported Python host

```sh
python3 -I -X utf8 dashboard.py
# Optional existing interpreter:
PYTHON=/path/to/python3 sh start-dashboard.sh
# Logs from a different Codex data directory:
python3 dashboard.py --codex-home /path/to/.codex
# Explicit offline logs, without a database (repeat --log for resumed segments):
python3 dashboard.py --log /path/to/rollout.jsonl --log /path/to/resumed.jsonl
```

Windows: `StartDashboard.ps1` chooses the package's private Python first, otherwise `python.exe` on PATH. It also accepts `-PythonExecutable` and `-CodexHome`.

For an SSH host, run `python3 dashboard.py --no-browser --port 8765` there. On your computer run `ssh -L 8765:127.0.0.1:8765 user@host` and open the exact printed `http://127.0.0.1:8765/#token=...` link. The token stays between your computer and the host you selected. Do not publish this link. The port numbers must match because the service validates the Host header.

## No-browser reports

```sh
python3 stats.py --list
python3 stats.py --thread THREAD_ID --start '2026-10-09T10:00:00+08:00' --end '2026-10-09T11:00:00+08:00'
python3 stats.py --thread THREAD_ID --messages 'a fragment of the user message'
python3 stats.py --thread THREAD_ID --first FIRST_MESSAGE_ID --last LAST_MESSAGE_ID
```

JSON output goes to your terminal only. `--messages` contains local message excerpts for selection; do not publish that output. All source can run with `-I` because sibling imports are restricted to the installed source directory.

## Packaging

`python PackageDashboard.py` creates a source ZIP usable across Python-supported OS/CPU combinations. It does not bundle Python. Windows builds accept `Package.ps1 -Architecture x64`, `arm64`, or `x86`; each bundles the matching official CPython 3.14.8 runtime. Its download digest is pinned, including ARM64/x86 digests taken from the official Sigstore bundles. See [the Python distribution directory](https://www.python.org/ftp/python/3.14.8/) and [Python on Windows](https://docs.python.org/3.14/using/windows.html).

When building for a CPU your build host cannot execute, use `-SkipSmokeTest` and keep that package's execution status explicitly unverified. Local targeted feature checks can also justify `-SkipTests`; default release automation retains the x64 release checks. No new OS or runtime is installed by these scripts.

The [Microsoft Framework 4.8.1 announcement](https://devblogs.microsoft.com/dotnet/announcing-dotnet-framework-481/) confirms native ARM64 support on Windows 11+. This runtime prerequisite is separate from validation of this application.
