#!/bin/sh
# Optional Qt desktop HUD, installed in a private venv on first launch.
set -eu
task_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
task_python=${PYTHON:-python3}
if ! command -v "$task_python" >/dev/null 2>&1; then
    echo "Python 3.10-3.14 is required. Install Python or download the ready-to-run HUD package." >&2
    exit 1
fi
"$task_python" -c 'import sys; sys.exit(0 if (3, 10) <= sys.version_info[:2] <= (3, 14) else "The desktop HUD needs Python 3.10-3.14; use a bundled app or a matching Python.")'
if [ -n "${CODEX_TOKEN_HUD_HOME:-}" ]; then
    task_data=$CODEX_TOKEN_HUD_HOME
elif [ "$(uname -s)" = Darwin ]; then
    task_data="$HOME/Library/Application Support/CodexTokenHud"
else
    task_data="${XDG_STATE_HOME:-$HOME/.local/state}/codex-token-hud"
fi
task_env="$task_data/overlay-env"
task_requirements="$task_dir/requirements-overlay.txt"
if [ ! -x "$task_env/bin/python" ]; then
    "$task_python" -m venv "$task_env" || {
        echo "Cannot create the private environment. On Debian/Ubuntu install python3-venv, then retry." >&2
        exit 1
    }
fi
# Compare only this small public dependency list; never scan or hash user files.
if [ ! -f "$task_env/hud-requirements.txt" ] || ! cmp -s "$task_requirements" "$task_env/hud-requirements.txt"; then
    "$task_env/bin/python" -m pip install --disable-pip-version-check --only-binary=:all: -r "$task_requirements"
    cp "$task_requirements" "$task_env/hud-requirements.txt"
fi
exec "$task_env/bin/python" -I -X utf8 "$task_dir/overlay.py" "$@"
