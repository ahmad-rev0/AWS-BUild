---
inclusion: always
---
# Technology stack and constraints

## Stack (prefer these over alternatives; don't add frameworks without being asked)
| Layer | Choice | Notes |
|---|---|---|
| Frontend | React 18 + Vite + TypeScript | Tailwind CSS for styling |
| Map | Leaflet + react-leaflet, OpenStreetMap tiles | District polygons from local GeoJSON in `data/geo/` |
| Backend API | Python 3.11+, FastAPI, Uvicorn | REST + JSON; port 8000 |
| Agent | Strands Agents SDK (Python) | Model: Amazon Bedrock **Nova Pro** (`us.amazon.nova-pro-v1:0` or the model ID the event account exposes) |
| Embeddings | Amazon Bedrock Titan Text Embeddings V2 | **Fallback:** local `sentence-transformers/all-MiniLM-L6-v2` when Bedrock embeddings are unavailable. Choose with env var `EMBEDDINGS_PROVIDER=bedrock|local` |
| Vector store | ChromaDB, persistent local mode (`data/index/`) | No hosted vector DB. No extra accounts |
| Relational data | SQLite (`data/atlas11.db`) | Proposals, decisions, approvals, audit log |
| Tests | pytest + Hypothesis (property-based) for Python; Vitest for frontend | |
| Package mgmt | Python `venv` + `requirements.txt`; `npm` for frontend | Always activate the venv before running Python |

## AWS and credentials
- Credentials come only from environment variables (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN`, `AWS_REGION=us-east-1`), loaded from `agent/.env` with `python-dotenv`.
- Workshop credentials **expire after 1 hour**. Code must surface a clear error ("AWS credentials expired, refresh agent/.env") rather than a stack trace.
- Never write real keys into any tracked file. `.env` is git-ignored; `.env.example` holds placeholders.

## 90-minute MVP cut line
The must-demo path is deterministic and seeded/cached: fixed proposal → review → one `OVERLAPPING` and one `COMPLEMENTARY` verdict → memo → approver action → gap redirect/map state. Live Bedrock, full indexing, exhaustive evaluation, and screenshots are secondary when they are not already working. The pipeline, API, and frontend share the same IDs and Pydantic/TypeScript payload schema; the minimal end-to-end smoke test is the integration gate.

## Resilience requirements (the demo must not die)
- **Demo cache:** every agent response for the scripted demo scenario is cached in `data/demo_cache/`. With `DEMO_MODE=cached`, the API serves the scripted report by its fixed scenario key/proposal ID without Bedrock; approval and gap responses are deterministic or locally backed.
- Time out all Bedrock calls (20s) and degrade gracefully.
- The app must run fully offline in cached mode, except for map tiles.

## Ports
- Frontend: 5173 (Vite dev)
- API: 8000
- Never start a second instance on an occupied port. Check first.

## Coding conventions
- Python: type hints everywhere, Pydantic models for every API payload and agent output, `ruff` for lint and format.
- TypeScript: strict mode, no `any`, functional components and hooks.
- All agent outputs are **structured JSON validated against a Pydantic schema** before they reach the API response.
