# Releasing

1. Update VERSION, CHANGELOG.md, README download examples, and this release's validation record. Keep the release marked beta until compatibility has been exercised beyond one machine.
2. Run `Test.ps1` and `Package.ps1`. Packaging checks the pinned official Python SHA256, preserves its license, and smoke-tests the extracted ZIP. Check the HUD on a real supported Codex window and inspect the HUD-only screenshot.
3. Inspect `git ls-files`: no local settings, runtime data, layouts, verification dumps, inspection extracts, real session logs, account files, or binary downloads may be tracked. Never upload the whole working folder through a browser. Push only Git-tracked source; attach only the portable ZIP and `.sha256` to a release.
4. Create an empty GitHub repository, connect this local repository as its remote, and push `main`. Check the actual Windows CI jobs after that push. The source ZIP may be used for browser upload when needed, including its `.github/` directory, but it does not preserve local Git history.
5. After the hosted checks pass, create and push a tag matching VERSION, e.g. `v1.2.0-beta.1`. This action is a publication operation and should be done by the repository owner or with their explicit authorization.
6. `release.yml` builds and tests again, then creates a **draft prerelease** with the portable ZIP/checksum. Review the attached files and notes before publishing the draft. The workflow is not triggered by ordinary branches or pull requests and does not automatically publish a public release.

Example Git commands after an owner has selected the repository destination:

```powershell
git remote add origin https://github.com/OWNER/codex-token-hud.git
git push -u origin main
# Only after hosted CI succeeds and the release is approved:
git tag v1.2.0-beta.1
git push origin v1.2.0-beta.1
```

The beta EXE is unsigned. Checksums detect changes to downloaded bytes but do not provide an independent publisher identity. Do not label a hosted workflow as passing until GitHub reports success.
