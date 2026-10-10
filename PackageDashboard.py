"""Package only portable source and public docs; no local settings or chat data."""
from pathlib import Path
import zipfile


def main():
    root = Path(__file__).resolve().parent
    version = (root / "VERSION").read_text().strip()
    output = root / "dist" / ("CodexTokenHud-" + version + "-dashboard.zip")
    output.parent.mkdir(exist_ok=True)
    files = ["metrics.py", "history.py", "dashboard.py", "stats.py", "VERSION", "LICENSE", "README.md",
             "README.zh-CN.md", "PRIVACY.md", "SECURITY.md", "CHANGELOG.md", "StartDashboard.ps1", "start-dashboard.sh",
             "overlay.py", "overlay_state.py", "requirements-overlay.txt", "start-overlay.sh", "StartOverlay.command", "THIRD_PARTY.md"]
    files.extend(str(p.relative_to(root)) for p in (root / "web").glob("*.*"))
    files.extend(str(p.relative_to(root)) for p in (root / "licenses").glob("*.txt"))
    files.extend(["docs/COMPATIBILITY.md", "docs/VALIDATION.md", "docs/RELEASE_NOTES.md", "docs/UI_DESIGN.md",
                  "docs/images/hud.png", "docs/images/dashboard.jpg", "docs/images/overlay.png"])
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in files:
            entry = zipfile.ZipInfo.from_file(root / name, str(Path(output.stem) / name))
            if name.endswith((".sh", ".command")):
                entry.create_system = 3
                entry.external_attr = (0o100755 << 16)
            archive.writestr(entry, (root / name).read_bytes(), compress_type=zipfile.ZIP_DEFLATED)
    print(output)


if __name__ == "__main__":
    main()
