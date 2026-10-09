---
name: clash-eval
description: Build, extend and run the golden-pair evaluation that measures the Atlas11 clash agent's classification accuracy (DUPLICATE / OVERLAPPING / COMPLEMENTARY / UNRELATED). Use when labelling new test pairs, investigating a misclassification, comparing prompt versions, or when the eval hook reports a regression.
compatibility: Requires agent/eval.py (built by the clash-agent spec) and data/eval/golden_pairs.jsonl.
metadata:
  project: atlas11
---
# Clash evaluation

## The golden set
`data/eval/golden_pairs.jsonl` holds one JSON object per line:
```json
{"pair_id": "gp-001", "proposal": {...Proposal fields...}, "project_id": "P171422",
 "expected": "OVERLAPPING", "rationale": "same city + same water network, different components",
 "labelled_by": "team", "source": "worldbank_api|seeded"}
```
Aim for **at least 12 pairs**: 3 per label, including at least 2 *hard negatives*. A hard negative has very similar wording but is COMPLEMENTARY or UNRELATED, e.g. a BRT line in another corridor or the same sector in another city. Hard negatives are what prove the agent isn't just matching text.

## Adding a pair
```bash
python .kiro/skills/clash-eval/scripts/add_pair.py --proposal-file data/eval/proposals/p-drainage.json \
  --project-id P171422 --expected OVERLAPPING --rationale "same district drainage, different scope"
```

## Running
- Quick (hook, first 6 pairs, cached embeddings): `python -m agent.eval --quick`
- Full: `python -m agent.eval`
- Each run appends a row to `.kiro/evidence/eval-history.csv`: `timestamp, prompt_hash, model_id, n, accuracy, dup_precision, hard_negative_accuracy`

## Reading results
1. **DUPLICATE precision matters most.** A false DUPLICATE could block a legitimate project. If it's below 1.0, fix it before anything else.
2. Hard-negative accuracy is the headline number for the pitch ("the agent correctly told apart N of M look-alike projects").
3. For each failure, check the agent trace. Did the deterministic `check_overlap` tool return the right facts?
   - Facts wrong → it's a **code bug** → open a **Bugfix spec**.
   - Facts right but the label is wrong → it's a **prompt issue** → edit `agent/prompts/clash_system.md` (the hook re-runs the eval).
4. Never edit golden labels just to make a run pass. If a label is genuinely wrong, change it with a rationale and note it in the commit message.
