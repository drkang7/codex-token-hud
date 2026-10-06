# Privacy

The HUD runs locally and makes no network requests. It does not read `auth.json`, authentication tokens, passwords, account credentials, or environment files. It does not request account quota information.

It reads the `threads` table in a compatible local Codex `state_*.sqlite` database using SQLite read-only mode. It reads the selected chat's recent JSONL tail, parsing recorded usage/timing events. Other event records are encountered while parsing the file but message bodies are not copied into HUD output. It reads the accessibility header of Codex windows to identify the displayed chat.

Derived JSON in `%LOCALAPPDATA%\CodexTokenHud\runtime` includes chat titles, IDs, model, token counts, timing, source file paths, and recent thread metadata. Saved layout and optional settings are in the same data directory. These files stay on the computer but are private. Do not upload them, real rollout logs, database files, or screenshots containing chat text in bug reports.

The source repository excludes local settings, runtime data, legacy layouts, inspection extracts, downloads, and build artifacts. Packaging copies an explicit allowlist and checks the archive for prohibited private paths. Packaging downloads the official Python runtime over HTTPS and verifies its pinned SHA256; this is a developer build operation, not application runtime traffic.

Exiting the HUD ends its collector. Uninstall removes this copy's optional logon task and desktop shortcut but preserves saved user data. If you want to remove the saved data too, exit the HUD first and manually delete `%LOCALAPPDATA%\CodexTokenHud`. The HUD does not delete or alter Codex chats.
