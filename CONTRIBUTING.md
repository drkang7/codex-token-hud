# Contributing

Use Windows x64 and Python 3.10+; there are no pip dependencies. The .NET Framework 4.x C# compiler and UI Automation assemblies come from Windows. Run `Test.ps1`, then `Build.ps1 -OutputDirectory build\app`. For a distributable build, run `Package.ps1`; the default includes tests and the extracted-package smoke test.

Use synthetic usage records and temporary databases in tests. Cover changes that affect timing, duplicate usage, source switching, partial file writes, binding, stale display guards, or packaging. Avoid tests that merely duplicate rendering implementation. Do not add real Codex session data or extracted Codex app code.

Keep the meanings of speed and cache fraction in README.md / README.zh-CN.md accurate. Never infer an individual chat's weekly allowance consumption from account-wide usage, context occupancy, token totals, or API prices. Unknown measurements must remain unknown.

For bugs, include the HUD version, Windows version, Codex version, display scale, UI language, whether Codex is elevated, and reproducible steps. Redact titles and paths. Do not attach `%LOCALAPPDATA%\CodexTokenHud`, `.codex` databases, real logs, `auth.json`, or credentials.

Changes to the public release should update VERSION and CHANGELOG.md. See docs/RELEASING.md for the tag/draft release workflow. The project is MIT licensed; contributions should be compatible with that license.
