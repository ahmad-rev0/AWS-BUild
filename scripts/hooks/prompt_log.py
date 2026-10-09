#!/usr/bin/env python3
"""PromptSubmit hook: log prompts as evidence of Kiro usage (reads USER_PROMPT env var)."""

import os
import datetime
from pathlib import Path

p = (os.environ.get("USER_PROMPT") or "").strip().replace("\n", " ")
if p:
    log = Path(".kiro/evidence/prompt-log.md")
    log.parent.mkdir(parents=True, exist_ok=True)
    if not log.exists():
        log.write_text(
            "# Prompt log (auto-captured by hook)\n\n| time | prompt (first 300 chars) |\n|---|---|\n"
        )
    with log.open("a") as f:
        f.write(
            f"| {datetime.datetime.now():%H:%M:%S} | {p[:300].replace('|', '/')} |\n"
        )
