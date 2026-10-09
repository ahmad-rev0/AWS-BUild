---
inclusion: always
---
# Project structure

```
atlas11/
├── .kiro/
│   ├── steering/        # persistent guidance (this folder)
│   ├── specs/           # Kiro specs: requirements.md / design.md / tasks.md per feature
│   ├── hooks/           # agent hooks (JSON)
│   ├── skills/          # Agent Skills (SKILL.md + scripts)
│   ├── agents/          # custom agents (judge simulator, data steward)
│   ├── settings/mcp.json
│   └── evidence/        # Kiro-usage evidence for the pitch (prompt log, screenshots list)
├── agent/               # Strands agent service (Python)
│   ├── app.py           # FastAPI entrypoint (routes)
│   ├── clash_agent.py   # Strands Agent definition + tools
│   ├── tools/           # one file per agent tool
│   ├── prompts/         # system prompts as .md files (hook-watched!)
│   ├── schemas.py       # Pydantic models: Proposal, Candidate, Verdict, Memo, Approval
│   ├── retrieval.py     # embeddings + Chroma search + filters
│   ├── gaps.py          # need-score vs funding gap computation
│   ├── store.py         # SQLite access
│   ├── eval.py          # golden-pair evaluation (run by hook)
│   ├── .env.example
│   └── tests/           # pytest + hypothesis
├── frontend/            # React + Vite + TS
│   └── src/{pages,components,api,types}/
├── data/
│   ├── raw/             # fetched source data (World Bank / IATI) — never hand-edit
│   ├── processed/       # normalized projects.csv (pipeline output)
│   ├── geo/             # district GeoJSON + need_scores.csv
│   ├── eval/            # golden_pairs.jsonl (hand-labelled)
│   ├── demo_cache/      # cached agent responses for DEMO_MODE=cached
│   └── index/           # Chroma persistent store (git-ignored, rebuildable)
├── scripts/             # data fetch, index build, hook helper scripts
└── docs/                # README, architecture diagram, pitch notes
```

## Rules
- One agent tool per file in `agent/tools/`, each with a docstring. Strands uses the docstring as the tool description, so write it for the model.
- System prompts live in `agent/prompts/*.md`, never inline in Python. A hook regression-tests them on every save.
- Pipeline outputs (`data/processed`, `data/index`) are generated and must be rebuildable with `python scripts/build_index.py`.
- Imports are absolute from the package root (`from agent.schemas import Verdict`).
- Names: snake_case in Python, PascalCase React components, kebab-case for spec folder names.
