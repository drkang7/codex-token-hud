# Optional desktop HUD dependencies

The portable browser dashboard, terminal reports and original Windows .NET strip do not require Qt.

The macOS/Linux desktop HUD uses **PySide6-Essentials and Shiboken6**, the official Qt for Python bindings, under their applicable LGPLv3/GPLv3 or commercial terms. This project uses the open-source LGPL option. Qt shared libraries remain separate files in the desktop packages and may be replaced with compatible modified versions. Dependency notices and license texts are included under `THIRD_PARTY/` in each desktop package. Application source is MIT-licensed; this does not replace dependency licenses.

- [Qt for Python licensing](https://doc.qt.io/qtforpython-6/licenses.html)
- [Qt source and releases](https://download.qt.io/official_releases/QtForPython/)
- [Qt source repository](https://code.qt.io/cgit/pyside/pyside-setup.git/)
- [Qt 6 source repository](https://code.qt.io/cgit/qt/qtbase.git/)

Packages are assembled using **PyInstaller**, whose GPL exception permits distributing generated applications under their own license. Its notices are retained alongside the bundled Python license. See [PyInstaller license](https://pyinstaller.org/en/stable/license.html). No account data, telemetry logs or local configuration is included.
