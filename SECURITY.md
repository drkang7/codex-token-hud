# Security

This beta is an unsigned local desktop application. Review its source and distribution checksum before running it. It requests the highest available user privilege to read an elevated Codex window through UI Automation; it does not use that privilege to modify Codex or account settings.

Report a suspected vulnerability through the repository's private vulnerability reporting feature if the owner has enabled it. Otherwise open an issue containing only a high-level, redacted description and ask for a private contact. Do not publish exploit data containing credentials, chat content, local account paths, or real session logs.

Until a stable release exists, fixes target the latest beta. No compatibility or security maintenance window is promised for earlier builds. Python runtime updates require updating the pinned official URL and SHA256, rerunning tests, and rebuilding the portable release; the HUD does not self-update.
