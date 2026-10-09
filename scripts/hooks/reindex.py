#!/usr/bin/env python3
"""Hook: rebuild the vector index. No-op until scripts/build_index.py exists."""

import subprocess
import sys
from pathlib import Path

if not Path("scripts/build_index.py").exists():
    print("[data-reindex] scripts/build_index.py not built yet, skipping.")
    sys.exit(0)
r = subprocess.run(
    [sys.executable, "scripts/build_index.py", "--incremental"],
    capture_output=True,
    text=True,
)
print(r.stdout[-1500:])
if r.returncode:
    print(r.stderr[-1500:], file=sys.stderr)
sys.exit(r.returncode)
