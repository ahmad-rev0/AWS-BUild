# Implementation Plan: Atlas11 Data Pipeline

## Overview

Implement the Atlas11 data pipeline contracts, embedding-provider boundary, persistent Chroma indexing, filtered retrieval, AWS diagnostics, and offline cached-demo safeguards. The plan preserves the existing implementation order: establish shared contracts first, then providers, indexing, retrieval, diagnostics, and operational verification.

## Tasks

- [ ] 1. Establish shared project and pipeline contracts
  - [x] 1.1 Add/confirm the Pydantic `Project`, `Candidate`, `RejectedRow`, and `IndexReport` models and validation rules without changing application routes.
  - [x] 1.2 Add typed configuration and typed errors for provider selection, missing data, invalid filters, embedding failures, and `CredentialsExpired`.
  - [~] 1.3 Add focused tests for CSV parsing, provenance boundaries, date normalization, duplicate IDs, and exact AWS expiry messaging.

- [ ] 2. Implement embedding provider boundary
  - [~] 2.1 Implement local `sentence-transformers/all-MiniLM-L6-v2` provider with no implicit network download in offline mode.
  - [~] 2.2 Implement Bedrock Titan Text Embeddings V2 provider using refreshed dotenv/environment configuration, bounded 20-second calls, and credential exception mapping.
  - [~] 2.3 Add provider tests with fake local/model and boto3 clients, including partial failure behavior.

- [ ] 3. Implement `scripts/build_index.py`
  - [~] 3.1 Load the required primary CSV and optional separate seeded CSV, validate rows independently, and report rejected rows.
  - [~] 3.2 Canonicalize `name + description + themes`, compute deterministic SHA-256 content hashes, and reject conflicting duplicate IDs.
  - [~] 3.3 Create/reuse persistent Chroma `projects` at `data/index/` and upsert required metadata and documents.
  - [~] 3.4 Implement `--incremental`, including skip-on-unchanged, re-upsert-on-change, stale-ID removal, and atomic manifest commit.
  - [~] 3.5 Add command-line summary output and actionable missing-data/provider errors.

- [ ] 4. Implement `agent/retrieval.py`
  - [~] 4.1 Implement `search(text, k=8, filters)` with supported city, district, and inclusive date-window filters.
  - [~] 4.2 Normalize Chroma distances to `[0,1]`, deduplicate IDs, sort descending with deterministic ties, and enforce the `k` bound.
  - [~] 4.3 Add required Hypothesis properties for ordering, uniqueness, score bounds, filter compliance, and local/offline behavior.
  - [~] 4.4 Add a temporary persistent-Chroma integration smoke test that reopens the index and verifies metadata filtering.

- [ ] 5. Implement `scripts/check_aws.py`
  - [~] 5.1 Check Nova Pro and Titan embeddings independently using refreshed dotenv credentials.
  - [~] 5.2 Report callable status, model IDs, and known token lifetime without secrets; return non-zero on unavailable checks.
  - [~] 5.3 Add mocked success, expiry, and partial-service diagnostic tests.

- [ ] 6. Verify operational boundaries and data provenance
  - [~] 6.1 Confirm `data/index/` is git-ignored and generated artifacts are rebuildable from CSV inputs.
  - [~] 6.2 Confirm `DEMO_MODE=cached` does not call Bedrock for the scripted review path.
  - [~] 6.3 Run the narrow pipeline unit/property tests and local smoke test with cached MiniLM; document any missing optional model/cache dependency.

## Notes

- Tasks are ordered so shared schemas and typed errors precede providers, indexing, retrieval, diagnostics, and final operational checks.
- The implementation must preserve application routes and the existing requirements/design contracts.
- Tests are included within the relevant implementation groups so each group can validate its own behavior before later groups depend on it.
- The final verification group confirms the generated index is rebuildable, cached demo mode remains offline from Bedrock, and the narrow pipeline validation passes.

## Task Dependency Graph

```json
{
  "waves": [
    {
      "id": 0,
      "tasks": ["1.1", "1.2"]
    },
    {
      "id": 1,
      "tasks": ["1.3", "2.1", "2.2"]
    },
    {
      "id": 2,
      "tasks": ["2.3", "3.1", "3.2"]
    },
    {
      "id": 3,
      "tasks": ["3.3", "3.4", "3.5"]
    },
    {
      "id": 4,
      "tasks": ["4.1", "4.2", "5.1"]
    },
    {
      "id": 5,
      "tasks": ["4.3", "4.4", "5.2", "5.3"]
    },
    {
      "id": 6,
      "tasks": ["6.1", "6.2", "6.3"]
    }
  ]
}
```
