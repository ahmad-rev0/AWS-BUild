#!/usr/bin/env python3
"""PreToolUse hook: block writes that contain AWS credentials (except into .env files).
Reads the tool-call context JSON from STDIN; a non-zero exit blocks the tool call."""

import re
import sys

raw = sys.stdin.read()
if re.search(r'\.env(\.local)?["\s]', raw) and ".env.example" not in raw:
    sys.exit(0)  # writing the real .env is allowed (it's git-ignored)
patterns = [
    r"\b(AKIA|ASIA)[0-9A-Z]{16}\b",  # access key id
    r"aws_secret_access_key\s*[=:]\s*['\"]?[A-Za-z0-9/+]{40}",  # secret key
    r"AWS_SESSION_TOKEN\s*[=:]\s*['\"]?[A-Za-z0-9/+=]{100,}",  # session token
]
for p in patterns:
    if re.search(p, raw, re.I):
        print(
            "[secret-guard] Blocked: this write contains what looks like an AWS credential. "
            "Put credentials only in agent/.env (git-ignored) and reference them via environment variables.",
            file=sys.stderr,
        )
        sys.exit(2)
sys.exit(0)
