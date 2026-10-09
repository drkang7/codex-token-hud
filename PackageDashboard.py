"""Package only portable source and public docs; no local settings or chat data."""
from pathlib import Path
import zipfile


def main():
    root = Path(__file__).resolve().parent
    version = (root / "VERSION").read_text().strip()
    output = root / "dist" / ("CodexTokenHud-" + version + "-dashboard.zip")
    output.parent.mkdir(exist_ok=True)
    files = ["metrics.py", "history.py", "dashboard.py", "stats.py", "VERSION", "LICENSE", "README.md",
             "README.zh-CN.md", "PRIVACY.md", "SECURITY.md", "CHANGELOG.md", "StartDashboard.ps1", "start-dashboard.sh"]
    files.extend(str(p.relative_to(root)) for p in (root / "web").glob("*.*"))
    files.extend(["docs/COMPATIBILITY.md", "docs/VALIDATION.md", "docs/RELEASE_NOTES.md",
                  "docs/images/hud.png", "docs/images/dashboard.jpg"])
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in files:
            archive.write(root / name, Path(output.stem) / name)
    print(output)


if __name__ == "__main__":
    main()
