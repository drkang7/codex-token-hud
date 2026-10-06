# Codex Token HUD 1.2.0-beta.1

First public Windows x64 beta candidate. Shows the current local Codex Desktop chat's recorded model, completed-response output token speed, and input cache fraction in a draggable/resizable native strip.

- Portable ZIP includes private Python; no system Python or pip packages required.
- 100 ms data polling, visible sample age, stale/new-turn guards, and manual refresh.
- Saved per-user layout, tray menu, optional desktop shortcut and logon startup.
- Resumed rollout tracking, versioned database discovery, and CODEX_HOME support.
- Local-only read-only telemetry; no credentials, network requests, or Codex installation modifications at runtime.

Extract the entire `win-x64.zip` and run `CodexTokenHud.exe`. Compare its SHA256 with the adjacent `.sha256` file. Requires Windows 10/11 x64 and .NET Framework 4.8. The EXE is unsigned and may request elevation to match an elevated Codex window.

Known limits: local desktop chats only; header matching verified in Chinese/English on Codex 26.930.7945 at 150% scaling; duplicate titles require right-click selection. Speed is a response average reported after final usage arrives. Exact current-chat weekly allowance percentage is unavailable and is shown as such.

See README and docs/VALIDATION.md for formulas, privacy, verification scope, and troubleshooting.
