#!/usr/bin/env python3
"""PostToolUse hook (shell): detect expired AWS creds in command output."""
import re, sys
raw = sys.stdin.read()
if re.search(r"ExpiredToken|ExpiredTokenException|security token included in the request is (expired|invalid)|UnrecognizedClientException", raw):
    print("[aws-expiry-watch] AWS workshop credentials have EXPIRED (they last 1 hour). "
          "Do NOT change code to work around this. Stop and ask the user to paste fresh credentials "
          "from Workshop Studio into agent/.env, then re-run `python scripts/check_aws.py`.")
sys.exit(0)
