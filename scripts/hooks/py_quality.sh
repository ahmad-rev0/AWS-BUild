#!/bin/sh
# Hook: ruff lint + format (quiet). Skips if ruff isn't installed.
if [ -x .venv/bin/ruff ]; then R=.venv/bin/ruff; elif command -v ruff >/dev/null 2>&1; then R=ruff; else echo "[python-quality] ruff not installed, skipping"; exit 0; fi
$R check --fix --quiet agent scripts 2>&1 | tail -20
$R format --quiet agent scripts
exit 0
