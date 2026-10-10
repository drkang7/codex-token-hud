"""Build a native onedir HUD on its target OS; bundle public assets only."""
from importlib import metadata
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import sysconfig
import tarfile
import zipfile


def main():
    root = Path(__file__).resolve().parent
    work = root / "build/overlay-native"
    version = (root / "VERSION").read_text("utf-8").strip()
    machine = platform.machine().lower()
    arch = "arm64" if machine in ("arm64", "aarch64") else "x64" if machine in ("amd64", "x86_64") else machine
    target = "macos" if sys.platform == "darwin" else "linux" if sys.platform.startswith("linux") else "win"
    app_dir = work / "app"
    command = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--name", "CodexTokenHud",
               "--onedir", "--distpath", str(app_dir), "--workpath", str(work / "temp"),
               "--specpath", str(work), "--add-data", str(root / "web") + ":web",
               "--exclude-module", "tkinter", "--exclude-module", "PySide6.QtQml",
               "--exclude-module", "PySide6.QtQuick", "--exclude-module", "PySide6.QtTest"]
    if target == "macos":
        command.extend(["--windowed", "--osx-bundle-identifier", "io.github.drkang7.codex-token-hud"])
    elif target == "win":
        command.append("--windowed")
    command.append(str(root / "overlay.py"))
    subprocess.run(command, cwd=root, check=True)
    bundle = app_dir / ("CodexTokenHud.app" if target == "macos" else "CodexTokenHud")
    resources = bundle / "Contents/Resources" if target == "macos" else bundle
    public_files = ["LICENSE", "VERSION", "README.md", "README.zh-CN.md", "PRIVACY.md", "SECURITY.md", "THIRD_PARTY.md",
                    "requirements-overlay.txt", "docs/COMPATIBILITY.md", "docs/RELEASE_NOTES.md",
                    "docs/images/hud.png", "docs/images/dashboard.jpg", "docs/images/overlay.png"]
    for name in public_files:
        destination = resources / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(root / name, destination)
    # Preserve all dependency license files, including Qt's embedded LGPL texts.
    for dependency in ("PySide6-Essentials", "shiboken6", "PyInstaller"):
        dist = metadata.distribution(dependency)
        for entry in dist.files or ():
            if "license" in str(entry).lower() or "copying" in str(entry).lower():
                source = Path(dist.locate_file(entry))
                if source.is_file():
                    relative = Path(*entry.parts[1:])
                    destination = resources / "THIRD_PARTY" / dependency / relative
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, destination)
    # Official Python distributions keep this next to the executable or in stdlib.
    for source in (Path(sys.base_prefix) / "LICENSE.txt", Path(sys.base_prefix) / "LICENSE",
                   Path(sysconfig.get_path("stdlib")) / "LICENSE.txt"):
        if source.is_file():
            destination = resources / "THIRD_PARTY/Python/LICENSE.txt"
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            break
    else:
        raise RuntimeError("Python license not found; refusing to distribute an incomplete package")
    shutil.copytree(root / "licenses", resources / "THIRD_PARTY/Qt-open-source", dirs_exist_ok=True)
    if target == "macos":
        subprocess.run(["codesign", "--force", "--deep", "--sign", "-", str(bundle)], check=True)
    output = root / "dist" / ("CodexTokenHud-" + version + "-overlay-" + target + "-" + arch)
    output.parent.mkdir(exist_ok=True)
    if target == "linux":
        archive = output.with_suffix(output.suffix + ".tar.gz")
        with tarfile.open(archive, "w:gz") as tar:
            tar.add(bundle, arcname=bundle.name)
    else:
        archive = output.with_suffix(output.suffix + ".zip")
        if target == "macos":
            # ditto retains .app symlinks, executable modes and bundle metadata.
            subprocess.run(["ditto", "-c", "-k", "--keepParent", str(bundle), str(archive)], check=True)
        else:
            with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zipped:
                for source in bundle.rglob("*"):
                    if source.is_file():
                        zipped.write(source, Path(bundle.name) / source.relative_to(bundle))
    program = bundle / "Contents/MacOS/CodexTokenHud" if target == "macos" else bundle / ("CodexTokenHud.exe" if target == "win" else "CodexTokenHud")
    (work / "package.json").write_text(json.dumps({"program": str(program), "archive": str(archive)}), encoding="utf-8")
    print("Ready: " + str(archive))


if __name__ == "__main__":
    main()
