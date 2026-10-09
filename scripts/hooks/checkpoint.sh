#!/bin/sh
# Stop hook: commit a git checkpoint if there are changes.
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || { echo "[git-checkpoint] not a git repo"; exit 0; }
if [ -z "$(git status --porcelain)" ]; then echo "[git-checkpoint] nothing to commit"; exit 0; fi
git add -A && git commit -q -m "checkpoint: $(date '+%H:%M:%S')" && echo "[git-checkpoint] committed $(git rev-parse --short HEAD)"
