# Codex Token HUD

[English](README.md) | [简体中文](README.zh-CN.md)

A small, local Windows companion that shows the current Codex Desktop chat's model, output token speed, and input cache hit rate in a draggable status strip.

![Codex Token HUD](docs/images/hud.png)

**Status: 1.2.0-beta.1. Windows x64 only.** This is an independent project, unaffiliated with OpenAI. It uses local telemetry and does not modify Codex's installation.

## Try the portable release

1. Download `CodexTokenHud-1.2.0-beta.1-win-x64.zip` from this repository's Releases page.
2. Extract the **whole** ZIP to a folder you control. Keep the EXE, `metrics.py`, and `python/` together.
3. Run `CodexTokenHud.exe`, then open a local chat in Codex Desktop.

The ZIP includes a private Python runtime; you do not need to install Python or any pip packages. Windows 10/11 x64 with .NET Framework 4.8 is the target. The EXE requests the highest available user privilege to read the accessibility tree of an elevated Codex window; administrator accounts may see a Windows UAC prompt. The beta EXE is unsigned.

Drag the middle of the strip to move it; drag an edge or corner to resize it. Right-click the strip or its tray icon for refresh, reset layout, startup, and exit. It appears while the matching Codex window is foreground. Closing the strip exits its collector too.

Autostart is optional. Run `Install.ps1` in an administrator PowerShell to add a desktop shortcut and a per-user logon task, or use the tray menu. `Uninstall.ps1` removes only the task/shortcut belonging to this copy. It preserves your saved layout. For temporary use, simply run the EXE.

## What the numbers mean

| Field | Meaning |
| --- | --- |
| Model | The model recorded in this local chat's latest telemetry |
| `tok/s` | Output tokens divided by measured generation time for the latest completed model response, including reasoning tokens once |
| Cache | Cached input tokens / all input tokens for that same response |
| Age/state | Time of the measurement; new turns and expired samples show `--` |
| This chat's weekly allowance | Unavailable: local telemetry does not expose an attributable weekly allowance debit or denominator |

**Speed is a response average, not a live token counter.** The log supplies final counts after a response finishes. When stream timing is available, timing starts at the earliest model item; the fallback uses the request interval and includes time to first token. Tool execution is excluded when the recorded boundaries allow it. Hover for the timing basis and full sample time. Model switches, new turns without counts, samples older than 15 minutes, and collector heartbeat loss hide old numeric results.

The cache figure is a token fraction, not a cache request success rate. Token counts or API price estimates cannot be converted into this chat's percentage of a ChatGPT weekly allowance. The HUD does not estimate that percentage.

The collector checks for appended data every 100 ms and publishes a heartbeat at least once per second. The strip refreshes every 150 ms and checks the active chat around every 350 ms. Codex's own telemetry delivery can take longer.

## Local data and configuration

- Reads only thread metadata from a compatible `state_*.sqlite` opened read-only, plus the selected chat's recent JSONL tail. Message text is traversed as part of the JSONL but is not exported or stored by the HUD.
- No network requests, analytics, credentials, account quota requests, or changes to Codex files at runtime. The **developer packaging script** downloads the official Python archive after verifying a pinned SHA256.
- Layout and derived telemetry stay under `%LOCALAPPDATA%\CodexTokenHud`. This folder contains private chat titles, IDs, and local paths. Do not upload it.
- The Codex home defaults to `%USERPROFILE%\.codex`; `CODEX_HOME` is supported.
- Copy `settings.example.json` to `settings.json` beside the EXE or in the data folder for `codex_home` / `pythonw` overrides. A per-user file takes precedence. Relative Python paths are resolved beside the EXE. The portable runtime is preferred over PATH when no override is set.
- `CODEX_TOKEN_HUD_HOME` can isolate the HUD's data directory for development. Existing installs' legacy `user-layout.json` is copied into the new data folder once.

## Compatibility and troubleshooting

The beta was exercised with Codex Desktop 26.930.7945 on Windows at 150% display scaling. It binds chats by the visible accessibility header and exact local title. Chinese and English headers are recognized; other UI languages and future layouts are not verified. Two identical titles require an explicit right-click selection; the HUD does not guess. UI matching uses an internal app structure and can break after Codex updates.

Only **local** Codex chats with a readable rollout are supported. CLI/VS Code windows, cloud-only chats, macOS, Linux, and ARM64 native builds are outside this release. If the tray icon appears without a strip, bring a local Codex chat to the foreground and check that the HUD and Codex have compatible privilege levels. New or idle chats may have no current sample. Database incompatibility and unreadable logs are displayed as unavailable, never fabricated measurements.

See [validation and known limits](docs/VALIDATION.md), [privacy](PRIVACY.md), and [change history](CHANGELOG.md). Please report problems using synthetic/redacted examples; do not attach real session logs or account credentials.

## Build and test

Source builds require Windows x64, the Windows .NET Framework 4.x compiler, and Python 3.10+ for tests/runtime. The collector uses only the standard library.

```powershell
.\Test.ps1
.\Build.ps1
.\Start.ps1
```

If Python is not on PATH, `Build.ps1 -PythonExecutable 'C:\path\to\python.exe'` writes an ignored, local configuration. Use `Stop.ps1` before rebuilding a running EXE. To build away from the running copy: `Build.ps1 -OutputDirectory build\app`.

```powershell
.\Package.ps1
```

Packaging runs tests, builds the executable, copies an explicit release allowlist, downloads the pinned Python embeddable ZIP from python.org, checks SHA256, preserves its licenses, and smoke-tests the extracted release with system Python removed from PATH. Outputs are under `dist/`; neither `build/` nor `dist/` belongs in source control. See [contributing](CONTRIBUTING.md) and [release checklist](docs/RELEASING.md).

GitHub Actions runs the test/build scripts on Windows for Python 3.10, 3.12, and 3.14. A separate workflow creates a **draft prerelease** when a version tag is pushed. The initial upload still requires its first hosted CI run; local verification is described separately.

## License

[MIT](LICENSE). The portable distribution includes CPython under its own licenses, preserved in `python/LICENSE.txt`; see [third-party notices](THIRD_PARTY_NOTICES.md).
