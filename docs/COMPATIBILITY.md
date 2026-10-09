# Compatibility / 兼容范围

The shared collector, range analysis, local web service and terminal reports use only Python 3.10+ standard-library modules. They do not depend on Electron internals, a window title, an OS UI toolkit, a CPU architecture, pip packages or an account API.

| Environment | Interface | Requirements / validation boundary |
| --- | --- | --- |
| Windows x64 | Native draggable/resizable HUD; browser dashboard; terminal report | Native HUD requires .NET Framework 4.8 and an accessible local Codex Desktop window. Local Windows x64 checks passed. |
| Windows ARM64 | Browser dashboard and terminal report; AnyCPU HUD candidate | ARM64 private Python packaging is available. Native .NET Framework 4.8.1 on Windows 11 ARM64 or compatible emulation is needed for the HUD. No ARM64 hardware verification in this change. |
| Windows x86 | Browser dashboard and terminal report | x86 private Python packaging is available; the AnyCPU binary can also load under Framework 4.8, but Codex Desktop itself may not support this OS architecture. No 32-bit OS verification. |
| macOS, Intel / Apple Silicon | Browser dashboard; terminal report | An existing Python 3.10+ runtime with SQLite and a modern browser. Shared parsing, range and loopback-service CI passed on macOS. No native floating HUD or real Codex UI validation on macOS. |
| Linux, x64 / ARM64 / other Python architectures | Browser dashboard; terminal report | An existing Python 3.10+ runtime with SQLite. Shared parsing, range and loopback-service CI passed on Ubuntu; other CPU combinations are conditional source portability. A browser is optional for terminal reports. |
| WSL / SSH / headless hosts | Browser through local forwarding; terminal report | Run alongside the local logs. Forward the same chosen loopback port to your own computer. No public listening address. |
| Other systems with compatible Python, e.g. BSD or Android Python environments | Terminal report; browser where loopback sockets are available | Conditional portability of source only; requires readable Codex-format logs. Not device-tested; no bundled runtime or Codex client is promised. |

“支持”指工具具备对应入口和代码路径；未实机验证的平台不能视为已通过端到端验收。浏览器模式可以选择任意本地对话，Windows 原生状态栏默认通过无障碍标题识别当前桌面对话，也可从它的面板按 ID 固定一个 CLI/IDE/桌面对话并置顶显示。

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
