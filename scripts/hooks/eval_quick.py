#!/usr/bin/env python3
"""Hook: run quick golden-pair eval after a prompt change. No-op until agent/eval.py exists."""

import subprocess
import sys
from pathlib import Path

if not Path("agent/eval.py").exists():
    print("[prompt-eval] agent/eval.py not built yet, skipping.")
    sys.exit(0)
if not Path("data/eval/golden_pairs.jsonl").exists():
    print(
        "[prompt-eval] data/eval/golden_pairs.jsonl missing. Label pairs with the clash-eval skill."
    )
    sys.exit(0)
r = subprocess.run(
    [sys.executable, "-m", "agent.eval", "--quick", "--fail-on-regression"],
    capture_output=True,
    text=True,
)
print(r.stdout[-2500:])
if r.returncode:
    print(
        "[prompt-eval] EVAL FAILED OR REGRESSED. Do not keep this prompt change without fixing it.",
        file=sys.stderr,
    )
    print(r.stderr[-1500:], file=sys.stderr)
sys.exit(r.returncode)
