#!/bin/sh
# Hook: TypeScript type-check. Skips until the frontend exists.
[ -f frontend/tsconfig.json ] || { echo "[typescript-quality] frontend not scaffolded yet, skipping"; exit 0; }
cd frontend && npx --no-install tsc --noEmit -p . 2>&1 | tail -25
