#!/usr/bin/env python3
"""Append a labelled pair to data/eval/golden_pairs.jsonl."""
import argparse
import json
from pathlib import Path

LABELS = {"DUPLICATE", "OVERLAPPING", "COMPLEMENTARY", "UNRELATED"}

ap = argparse.ArgumentParser()
ap.add_argument("--proposal-file", required=True)
ap.add_argument("--project-id", required=True)
ap.add_argument("--expected", required=True, choices=sorted(LABELS))
ap.add_argument("--rationale", required=True)
ap.add_argument("--source", default="worldbank_api", choices=["worldbank_api", "iati", "seeded"])
ap.add_argument("--golden", default="data/eval/golden_pairs.jsonl")
a = ap.parse_args()

golden = Path(a.golden)
golden.parent.mkdir(parents=True, exist_ok=True)
existing = golden.read_text().splitlines() if golden.exists() else []
pair = {
    "pair_id": f"gp-{len([l for l in existing if l.strip()]) + 1:03d}",
    "proposal": json.loads(Path(a.proposal_file).read_text()),
    "project_id": a.project_id,
    "expected": a.expected,
    "rationale": a.rationale,
    "labelled_by": "team",
    "source": a.source,
}
with golden.open("a") as f:
    f.write(json.dumps(pair) + "\n")
print(f"Added {pair['pair_id']} ({a.expected})")
