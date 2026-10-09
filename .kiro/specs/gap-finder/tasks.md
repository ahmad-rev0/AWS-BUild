# Implementation Plan: Gap Finder

## Overview

Implement the smallest compatible local gap-finder path: extend the existing builder with GeoJSON validation and atomic output, add one shared Pydantic gap contract and read-only loader, then wire the loader into the district tool and `GET /gaps`. Keep calculations deterministic and local; focused pytest/Hypothesis coverage verifies the numeric invariants and service boundary.

## Tasks

- [ ] 1. Establish shared gap contracts and deterministic builder helpers
  - [ ] 1.1 Extend `agent/schemas.py` with the `IndicatorQuality` type and `DistrictNeedRecord` Pydantic contract, including canonical-ID, finite/bounded numeric, non-empty provenance, and ISO-date-or-`TBD: needs source` validation.
    - Preserve the exact generated CSV field order in the model definition.
    - _Requirements: 4.2–4.6, 5.1–5.2_
  - [ ] 1.2 Refactor `scripts/build_need_scores.py` into typed, testable helpers for canonical district validation, indicator/weight validation, min-max normalization, commitment aggregation, nearest-rank quartile selection, and funding-gap classification.
    - Reuse the shared canonical-ID rule and perform no district inference.
    - _Requirements: 1.2, 1.5–1.7, 2.1–2.6, 3.1–3.7_
  - [ ]* 1.3 Add focused unit and Hypothesis tests in `agent/tests/test_build_need_scores.py` for district/indicator/weight validation and numeric helpers.
    - **Property 1: Canonical district universe validation** — _Validates: Requirements 1.2, 1.4._
    - **Property 2: Indicator and weight validation rejects invalid numerical inputs** — _Validates: Requirements 1.5–1.7._
    - **Property 3: Normalization and weighted score bounds** — _Validates: Requirements 2.1, 2.3, 2.4, 6.1._
    - **Property 4: Constant indicators normalize to zero** — _Validates: Requirements 2.2, 6.3._
    - **Property 5: Positive-weight indicator monotonicity** — _Validates: Requirements 2.5, 6.2._
    - **Property 6: Exact-assignment commitment aggregation** — _Validates: Requirements 3.1–3.2._
    - **Property 7: Funding per-capita, quartile, and gap classification** — _Validates: Requirements 3.4–3.7, 6.4._

- [ ] 2. Publish validated, provenance-preserving need-score output
  - [ ] 2.1 Extend `scripts/build_need_scores.py` to load and validate the configured local GeoJSON FeatureCollection, require an exact GeoJSON/indicator district-ID set match, and preserve existing output on every failure.
    - Add/use the local district GeoJSON input and `snapshot_date` source column only as required by the builder contract; do not alter raw or processed project data.
    - _Requirements: 1.1, 1.3–1.4, 4.3–4.6_
  - [ ] 2.2 Implement complete record construction, shared-model validation, ascending district-ID serialization, and same-directory staged-file replacement in `scripts/build_need_scores.py`.
    - Publish only a complete, valid `need_scores.csv`; retain round-trip-safe score precision and clean up failed staging files.
    - _Requirements: 2.4, 3.3, 4.1–4.2, 4.7–4.8_
  - [ ]* 2.3 Add deterministic builder integration cases in `agent/tests/test_build_need_scores.py` for malformed GeoJSON, ID mismatch, matched/unmatched project amounts, provenance/snapshot retention, stable ordering, reproducible rebuilds, and output preservation on validation or staging failure.
    - _Requirements: 1.1–1.7, 3.1–3.3, 4.1–4.8_

- [ ] 3. Add one read-only Pydantic-validated gap data boundary
  - [ ] 3.1 Create `agent/gaps.py` with `load_gap_records` and `get_gap_record`, complete-file header/row/duplicate validation, deterministic sorting, and typed unavailable/not-found errors.
    - Never return a partial collection and do not recalculate scores or write files.
    - _Requirements: 5.1–5.2, 5.5–5.6_
  - [ ] 3.2 Replace direct CSV handling in `agent/tools/district_need.py` with delegation to `agent.gaps.get_gap_record` while retaining a model-facing docstring and typed unknown-ID behavior.
    - _Requirements: 5.7_
  - [ ]* 3.3 Add loader and tool tests in `agent/tests/test_gaps.py` for valid records, invalid contract dimensions, bad/missing headers, duplicate IDs, unavailable files, all-or-nothing loading, sorting, and unknown IDs.
    - **Property 8: District Need Record contract validation** — _Validates: Requirements 5.1–5.2._
    - _Requirements: 5.1–5.2, 5.5–5.7_

- [ ] 4. Expose the gap records through the FastAPI application
  - [ ] 4.1 Add `GET /gaps` with optional `district_id` to the established FastAPI application entrypoint, using shared response models and `agent.gaps` exclusively.
    - Return sorted collections or one matching record with HTTP 200; map unknown IDs to readable HTTP 404 and unavailable/invalid complete data to readable HTTP 503.
    - _Requirements: 5.3–5.6_
  - [ ]* 4.2 Add route tests in `agent/tests/test_gaps.py` for collection, known filtered record, unknown record, and missing/malformed source error mappings.
    - _Requirements: 5.3–5.6_

- [ ] 5. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional test tasks for the fastest MVP path; they remain in the plan because the design defines universal correctness properties.
- The build remains strictly local and atomic: a failed validation or staging write cannot replace the committed output.
- Implementation must use the activated Python virtual environment, focused pytest/Hypothesis tests, and Ruff only for changed Python files.

## Task Dependency Graph

```json
{
  "waves": [
    {"id": 0, "tasks": ["1.1", "1.2"]},
    {"id": 1, "tasks": ["1.3", "2.1"]},
    {"id": 2, "tasks": ["2.2"]},
    {"id": 3, "tasks": ["2.3", "3.1"]},
    {"id": 4, "tasks": ["3.2"]},
    {"id": 5, "tasks": ["3.3", "4.1"]},
    {"id": 6, "tasks": ["4.2"]}
  ]
}
```
