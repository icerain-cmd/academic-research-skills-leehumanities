#!/usr/bin/env bash
# Runs from any working directory; forwards arguments without shell evaluation.
set -euo pipefail
lh_installer_dir="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
for lh_python in python3 python; do
  if command -v "$lh_python" >/dev/null 2>&1 && "$lh_python" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' >/dev/null 2>&1; then
    exec "$lh_python" "$lh_installer_dir/install.py" "$@"
  fi
done
printf '%s\n' 'Python 3.10 or newer is required for the installer and local audit tools.' >&2
exit 1
