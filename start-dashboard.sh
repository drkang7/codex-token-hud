#!/bin/sh
# No installation or third-party Python modules required.
set -eu
task_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec "${PYTHON:-python3}" -I -X utf8 "$task_dir/dashboard.py" "$@"
