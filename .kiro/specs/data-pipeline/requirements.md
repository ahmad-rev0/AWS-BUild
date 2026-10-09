# Requirements Document

## Introduction

This document defines requirements for the Atlas11 data pipeline, which validates urban project records, builds the project index, supports incremental indexing and retrieval, diagnoses AWS availability, and preserves the offline cached-demo boundary and source provenance.

## Glossary

- **Atlas11 Data Pipeline**: The system that loads, validates, embeds, indexes, and retrieves urban project records for Atlas11.
- **Project**: An existing urban development record represented by the shared Pydantic `Project` model.
- **Seeded Record**: A project record marked with `source=seeded` for deterministic demo or test data.
- **Provenance**: The source label and source URL identifying how a project record was obtained.
- **Incremental Indexing**: Reconciliation that re-embeds and upserts only new or changed validated records and removes stale records.
- **Candidate**: A retrieval result represented by a project ID and normalized similarity score.
- **Demo Mode**: The runtime mode that permits the scripted review path to use local cached responses.

## Requirements

### 1. Input loading and validation

### 1.1 Primary and seeded inputs
**WHEN** `scripts/build_index.py` runs and `data/processed/projects.csv` does not exist, **THE SYSTEM SHALL** stop input loading and display an actionable message directing the operator to the `worldbank-ingest` skill.

**WHEN** `scripts/build_index.py` runs and `data/processed/projects.csv` exists, **THE SYSTEM SHALL** load that file as the authoritative primary input.

**WHEN** `data/processed/seeded_projects.csv` exists, **THE SYSTEM SHALL** load its rows as an additional input without writing, deleting, or modifying any row in `data/processed/projects.csv`.

**IF** a row loaded from `data/processed/seeded_projects.csv` has a `source` value other than `seeded`, **THEN THE SYSTEM SHALL** reject that row and report the source file, 1-based CSV row number, and validation reason.

**IF** a row loaded from `data/processed/projects.csv` has `source=seeded`, **THEN THE SYSTEM SHALL** reject that row and report the source file, 1-based CSV row number, project ID when available, and validation reason.

### 1.2 Pydantic validation
**WHEN** a CSV row is loaded from either input file, **THE SYSTEM SHALL** validate that row independently against the shared Pydantic `Project` model before including it in the loaded project set.

**IF** a CSV row fails Pydantic validation, **THEN THE SYSTEM SHALL** exclude that row, report its source file, 1-based CSV row number, project ID when available, and validation reason, and continue attempting to load every remaining row in both input files.

**IF** a valid row has `source=worldbank_api` or `source=iati` and its `source_url` is missing or empty, **THEN THE SYSTEM SHALL** reject that row and report its source file, 1-based CSV row number, project ID when available, and validation reason.

**WHEN** a valid row has `source=seeded`, **THE SYSTEM SHALL** preserve the value `seeded` for that row in the loaded project data.

**IF** two or more loaded rows across `projects.csv` and `seeded_projects.csv` have the same non-empty project ID, **THEN THE SYSTEM SHALL** reject every row with that duplicated project ID, report each affected source file and 1-based CSV row number, and **SHALL NOT** silently overwrite or select one duplicate record.

### 2. Embedding and indexing

**WHEN** a project row passes validation and is indexed, **THE SYSTEM SHALL** construct the embedding input by concatenating `name`, `description`, and `themes` in that order, using the same field separator and text normalization for every row, and **SHALL** submit that input exactly once for embedding.

**WHERE** `EMBEDDINGS_PROVIDER=bedrock`, **THE SYSTEM SHALL** use Amazon Bedrock Titan Text Embeddings V2 and load AWS configuration from `agent/.env` through environment variables before requesting embeddings.

**WHERE** `EMBEDDINGS_PROVIDER=local`, **THE SYSTEM SHALL** use `sentence-transformers/all-MiniLM-L6-v2` and **SHALL** complete embedding and search without network access when that model is locally available.

**IF** the configured embedding provider is unsupported, unavailable, or cannot produce an embedding, **THEN THE SYSTEM SHALL** stop the indexing operation, preserve the last valid index and manifest, and expose an error indicating that embedding failed; **THE SYSTEM SHALL NOT** write a partial index.

**WHEN** indexing succeeds for one or more valid project rows, **THE SYSTEM SHALL** upsert exactly one record for each valid `project_id` into a persistent Chroma collection named `projects` under `data/index/`, using the `project_id` as the record identifier and preserving the same identifier across repeated indexing runs.

**THE SYSTEM SHALL** store non-null metadata values for `city`, `district`, `sector`, `funder`, `approval_date`, `closing_date`, `amount_usd`, and `source` on every indexed record; numeric `amount_usd` metadata **SHALL** preserve the source amount without rounding introduced by indexing.

**WHEN** no project rows pass validation, **THE SYSTEM SHALL NOT** replace, truncate, or modify an existing valid `projects` index or manifest with an empty index, and **SHALL** expose an error indicating that no valid rows were available.

### 3. Incremental indexing

**WHEN** `--incremental` is passed, **THE SYSTEM SHALL** compute a deterministic content hash from each validated record’s normalized content, compare that hash with the previous committed manifest, and re-embed and upsert only records whose IDs are absent from the manifest or whose hashes differ.

**WHEN** an incremental indexing run processes a validated record whose ID and content hash both match the previous committed manifest, **THE SYSTEM SHALL** make zero embedding calls and shall not rewrite that record’s existing collection entry.

**WHEN** an incremental reconciliation completes successfully, **THE SYSTEM SHALL** remove from the collection every ID present in the previous committed manifest but absent from the current validated input, and shall commit a manifest containing exactly the current validated record IDs and their content hashes.

**WHEN** any embedding, upsert, deletion, or manifest-commit operation fails during an incremental indexing run, **THE SYSTEM SHALL** preserve the previous committed manifest unchanged and report that the incremental indexing run failed.

### 4. Retrieval

1. **WHEN** `agent.retrieval.search(text, k, filters)` is called with a valid non-empty search text of 1–10,000 characters, an integer `k` from 1 through 100 inclusive, and valid filters, **THE SYSTEM SHALL** return a collection containing 0 through `k` `Candidate(project_id, score)` values, with no duplicate `project_id` values.
2. **THE SYSTEM SHALL** return each candidate score as a finite numeric value in the inclusive range `[0,1]`, sort candidates by descending score, and order candidates by ascending `project_id` using deterministic lexical ordering when scores are equal.
3. **WHEN** a city or district filter is supplied, **THE SYSTEM SHALL** return only indexed projects whose corresponding metadata value equals the filter value exactly, including case and whitespace.
4. **WHEN** an inclusive implementation date window is supplied with a start date on or before its end date, **THE SYSTEM SHALL** return only projects whose known approval-to-closing interval intersects the window, including boundary-date intersections; **IF** either required interval date is missing or the interval cannot be established from indexed metadata, **THEN THE SYSTEM SHALL** exclude that project rather than infer a date.
5. **WHEN** `k` is not an integer from 1 through 100 inclusive, search text is empty, exceeds 10,000 characters, contains an unsupported value, or filters contain an unsupported field, invalid date, or a start date after its end date, **THE SYSTEM SHALL** raise a typed input error and **SHALL NOT** query Chroma.

### 5. AWS diagnostics and credential resilience

**WHEN** `scripts/check_aws.py` runs, **THE SYSTEM SHALL** perform and report two independent Bedrock callability checks: one for the configured Bedrock Nova Pro model and one for the configured Titan embeddings model; each check **SHALL** identify the model ID used and report either `callable` or `not callable`, and the diagnostic output **SHALL** report the known AWS session-token lifetime as 3,600 seconds without printing any credential value.

**IF** either Bedrock check returns an expired-credential or invalid-credential error, **THEN THE SYSTEM SHALL** raise or map the failure to `CredentialsExpired` and expose the exact message `AWS credentials expired. Refresh agent/.env from Workshop Studio.`

**WHEN** the operator changes values in `agent/.env` and a later invocation of `scripts/check_aws.py` occurs, **THE SYSTEM SHALL** load the changed values for that invocation without requiring a process restart.

### 6. Offline cached-demo boundary and provenance

**WHILE** `DEMO_MODE=cached`, **THE SYSTEM SHALL** execute the scripted review path using only locally stored cached responses and **SHALL NOT** invoke Bedrock.

**IF** a locally stored cached response required by the scripted review path is unavailable or cannot be read, **THEN THE SYSTEM SHALL** stop the affected operation, display an error indicating that the cached demo response is unavailable, and preserve the submitted proposal and any previously stored review data.

**WHILE** `DEMO_MODE=cached`, **THE SYSTEM SHALL** allow the index pipeline to be absent or not run without preventing the scripted review path from completing.

**THE SYSTEM SHALL** retain provenance for every project record used by the scripted review path, including whether the record is seeded or fetched, and **SHALL** display or return that provenance with the record.

**IF** a project record is seeded, **THEN THE SYSTEM SHALL** label it as seeded in every user-visible project, review, or memo output that includes the record and **SHALL NOT** label it as fetched.

**THE SYSTEM SHALL NOT** state or imply that index creation produced funding, project-delivery, or impact outcomes; any such outcome statement **SHALL** be based only on an explicitly identified source record or an explicitly identified derived calculation.

### 7. Correctness properties

- For every generated valid project, hashing the project twice without modifying any canonical field **SHALL** return the same non-empty hash string. For each canonical field, changing only that field to a different valid value **SHALL** return a hash different from the original hash.
- For every generated valid project list and an index state containing zero or more previously indexed project IDs, incremental indexing **SHALL** embed exactly the projects whose IDs are new to the index or whose canonical content has changed since the previous index state. It **SHALL NOT** embed projects whose IDs and canonical content are unchanged, and the resulting index **SHALL** contain at most one entry for each project ID.
- For every generated retrieval result list and every integer `k` from 1 through the requested result limit, the returned list **SHALL** contain no duplicate project IDs, **SHALL** contain at most `k` results, **SHALL** assign each result a finite score in the inclusive range `[0.0, 1.0]`, and **SHALL** order adjacent results so that each result's score is greater than or equal to the next result's score.
- For every finite distance value, score normalization **SHALL** return a finite value in the inclusive range `[0.0, 1.0]`. For each non-finite distance value, including positive infinity, negative infinity, and NaN, score normalization **SHALL** return exactly `0.0`.
- For every generated valid filter and every result returned for that filter, the result **SHALL** satisfy every specified predicate: a specified city **SHALL** equal the result city, a specified district **SHALL** equal the result district, and a specified date range **SHALL** include the result date according to the filter's inclusive boundary semantics. When multiple predicates are specified, all predicates **SHALL** be satisfied simultaneously.
