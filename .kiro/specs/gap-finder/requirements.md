# Requirements Document

## Introduction

This specification defines the Atlas11 gap-finder capability. The capability derives bounded, reproducible district need scores from local district GeoJSON, district indicators, local weights, and existing funded-project commitments; writes provenance-preserving `need_scores.csv`; and exposes the resulting district records through `GET /gaps`. Existing `scripts/build_need_scores.py` already validates indicator IDs, validates weights, min-max normalizes four positively oriented configured indicators, aggregates exact canonical project-district commitments, computes per-capita funding, and applies the specified gap threshold. The necessary deltas are GeoJSON district validation and geometry-derived district coverage, snapshot-date preservation, shared Pydantic gap contracts, a read-only `agent/gaps.py` data-access module, `GET /gaps`, and Hypothesis coverage for bounds and monotonicity.

## Glossary

- **Atlas11 Gap Finder**: The build, validation, data-access, and API capability that produces and returns district funding-gap records.
- **District GeoJSON**: A local GeoJSON FeatureCollection whose Features identify the districts represented in a need-score build.
- **Canonical District ID**: An opaque stable district identifier that matches exactly across District GeoJSON, district indicators, Projects, generated scores, API records, and map state, and satisfies the existing Project canonical identifier contract: a string matching `^[A-Za-z0-9][A-Za-z0-9._:-]*$`.
- **District Indicator**: A finite source measurement associated with one Canonical District ID and used by the configured Need Score calculation.
- **Positively Oriented Indicator**: A District Indicator for which a greater value represents greater district need.
- **Need Weight**: A finite non-negative value in `need_weights.json` assigned to one Positively Oriented Indicator; all Need Weights sum to exactly 1 within a tolerance of `1e-12`.
- **Need Score**: A finite weighted sum of configured, min-max-normalized Positively Oriented Indicators, represented in the inclusive range `[0,1]`.
- **Funded Commitment**: A non-negative `amount_usd` of an existing Project whose `district` exactly equals a Canonical District ID.
- **Funding per Capita**: The sum of Funded Commitments for one district divided by that district's positive population.
- **Inclusive Bottom Funding Quartile**: Every district whose Funding per Capita is less than or equal to the deterministic nearest-rank 25th-percentile threshold.
- **Funding Gap**: A district whose Need Score is at least `0.6` and whose Funding per Capita is in the Inclusive Bottom Funding Quartile.
- **District Need Record**: The Pydantic-validated API and file representation containing district identity, Need Score, funding metrics, Funding Gap status, indicator quality, snapshot date, and provenance.
- **Indicator Quality**: The source quality label `measured`, `estimated`, or `illustrative` for a District Indicator and derived District Need Record.
- **Snapshot Date**: The actual ISO 8601 date associated with the source data, or the literal `TBD: needs source` when that date is unavailable.
- **Provenance**: The source label and source URL retained from local source inputs to identify data origin.

## Requirements

### Requirement 1: Validate local district inputs

**User Story:** As a planning officer, I want the gap finder to use one consistent district universe, so that map districts, indicators, funding totals, and returned records refer to the same canonical districts.

#### Acceptance Criteria

1. WHEN the Gap Finder builds need scores, THE Atlas11 Gap Finder SHALL load a local District GeoJSON FeatureCollection, district indicators CSV, projects CSV, and Need Weights JSON.
2. WHEN the Gap Finder loads a District GeoJSON Feature, THE Atlas11 Gap Finder SHALL read exactly one Canonical District ID from the configured district-ID property and validate the Canonical District ID under the existing Project canonical identifier contract.
3. IF a District GeoJSON input is missing, unreadable, not a FeatureCollection, contains a Feature without a Canonical District ID, contains a Canonical District ID that fails the existing Project canonical identifier contract, or contains duplicate Canonical District IDs, THEN THE Atlas11 Gap Finder SHALL stop the build without replacing an existing `need_scores.csv` and return a readable validation error.
4. IF the set of Canonical District IDs in District GeoJSON and the set of Canonical District IDs in district indicators differ, THEN THE Atlas11 Gap Finder SHALL stop the build without writing `need_scores.csv` and report the missing or extra Canonical District IDs.
5. WHEN the Gap Finder accepts district indicators, THE Atlas11 Gap Finder SHALL require one unique Canonical District ID, a non-empty district name, a positive finite population, an Indicator Quality value of `measured`, `estimated`, or `illustrative`, and retained Provenance for every District Indicator.
6. IF a configured Need Weight names an unavailable District Indicator column, is non-finite, is negative, or the finite Need Weights do not sum to 1 within `1e-12`, THEN THE Atlas11 Gap Finder SHALL stop the build without writing `need_scores.csv` and return a readable validation error.
7. IF a configured Positively Oriented Indicator value is missing or non-finite for any Canonical District ID, THEN THE Atlas11 Gap Finder SHALL stop the build without writing `need_scores.csv` and identify the Canonical District ID and indicator column in the validation error.

### Requirement 2: Calculate bounded, positively oriented need scores

**User Story:** As a planning officer, I want transparent need scores, so that the map ranks districts without inventing source values.

#### Acceptance Criteria

1. WHEN the Gap Finder calculates a configured Positively Oriented Indicator, THE Atlas11 Gap Finder SHALL normalize each district value by `(value - minimum)/(maximum - minimum)` using the minimum and maximum values for that indicator across the validated district set.
2. WHEN all validated district values for one configured Positively Oriented Indicator are equal, THE Atlas11 Gap Finder SHALL assign normalized value `0.0` to every district for that indicator.
3. WHEN the Gap Finder calculates a District Need Record, THE Atlas11 Gap Finder SHALL calculate the Need Score as the sum of each configured Need Weight multiplied by the corresponding normalized Positively Oriented Indicator value.
4. WHEN the Gap Finder writes or returns a District Need Record, THE Atlas11 Gap Finder SHALL represent Need Score as a finite value in the inclusive range `[0.0,1.0]` without rounding that changes Funding Gap classification.
5. WHEN two otherwise identical validated district datasets differ only by an increase to one district's Positively Oriented Indicator with a positive Need Weight, THE Atlas11 Gap Finder SHALL produce a Need Score for that district that is greater than or equal to the Need Score from the unchanged dataset.
6. WHEN the Gap Finder derives a District Need Record from an Indicator Quality value of `estimated` or `illustrative`, THE Atlas11 Gap Finder SHALL retain that exact Indicator Quality value without labelling the record as measured.

### Requirement 3: Aggregate committed funding and classify gaps

**User Story:** As a planning officer, I want district funding metrics tied only to canonical project assignments, so that an unmatched project does not distort gap detection.

#### Acceptance Criteria

1. WHEN the Gap Finder loads a Project with a `district` value exactly equal to a Canonical District ID, THE Atlas11 Gap Finder SHALL add that Project's non-negative `amount_usd` to that district's Funded Commitment total.
2. WHEN the Gap Finder loads a Project with a missing or non-matching `district` value, THE Atlas11 Gap Finder SHALL exclude that Project amount from every district Funded Commitment total and retain no inferred district assignment.
3. IF a Project assigned to a Canonical District ID has a missing, non-finite, or negative `amount_usd`, THEN THE Atlas11 Gap Finder SHALL stop the build without writing `need_scores.csv` and return a readable validation error identifying the Project row.
4. WHEN the Gap Finder calculates Funding per Capita, THE Atlas11 Gap Finder SHALL divide each district's Funded Commitment total by that district's validated positive population.
5. WHEN the Gap Finder calculates the Inclusive Bottom Funding Quartile for `n` validated districts, THE Atlas11 Gap Finder SHALL sort Funding per Capita values in ascending order and select the value at zero-based index `max(0, ceil(0.25*n)-1)` as the inclusive threshold.
6. WHEN the Gap Finder classifies a Funding Gap, THE Atlas11 Gap Finder SHALL set `funding_gap=true` exactly when Need Score is greater than or equal to `0.6` and Funding per Capita is less than or equal to the Inclusive Bottom Funding Quartile threshold.
7. WHEN two or more districts equal the Inclusive Bottom Funding Quartile threshold and satisfy Need Score greater than or equal to `0.6`, THE Atlas11 Gap Finder SHALL set `funding_gap=true` for every such district.

### Requirement 4: Generate rebuildable provenance-preserving output

**User Story:** As a data steward, I want a deterministic generated file, so that the gap map can be rebuilt locally and explain each displayed value.

#### Acceptance Criteria

1. WHEN a need-score build succeeds, THE Atlas11 Gap Finder SHALL write `data/geo/need_scores.csv` with exactly one District Need Record for every validated Canonical District ID.
2. WHEN the Gap Finder writes `need_scores.csv`, THE Atlas11 Gap Finder SHALL sort District Need Records by ascending Canonical District ID and write the fields `district_id`, `district_name`, `need_score`, `funded_commitments_usd`, `commitments_per_capita`, `funding_gap`, `indicator_quality`, `snapshot_date`, `source`, and `source_url` in that order.
3. WHEN source data has an actual Snapshot Date expressed as an ISO 8601 calendar date, THE Atlas11 Gap Finder SHALL preserve that exact ISO 8601 calendar date in every derived District Need Record using that source snapshot.
4. IF source data has no actual Snapshot Date, THEN THE Atlas11 Gap Finder SHALL write the literal `TBD: needs source` as the Snapshot Date and SHALL NOT write an empty string or fabricated date.
5. IF source data supplies a Snapshot Date that is neither an ISO 8601 calendar date nor the literal `TBD: needs source`, THEN THE Atlas11 Gap Finder SHALL stop the build without replacing an existing `need_scores.csv` and return a readable validation error identifying the source record.
6. WHEN the Gap Finder writes a District Need Record, THE Atlas11 Gap Finder SHALL preserve its district name, Indicator Quality, source label, and source URL from the validated District Indicator without fabricating a source value.
7. WHEN identical validated input files and Need Weights are rebuilt, THE Atlas11 Gap Finder SHALL produce District Need Records with identical field values and ascending Canonical District ID order.
8. IF validation or output staging fails, THEN THE Atlas11 Gap Finder SHALL preserve the previously committed `need_scores.csv` unchanged and return a readable error.

### Requirement 5: Expose Pydantic contracts and gap retrieval

**User Story:** As a frontend developer, I want typed gap records from one read-only endpoint, so that the map renders the generated data without duplicating calculation rules.

#### Acceptance Criteria

1. WHEN the Atlas11 Service loads `need_scores.csv`, THE Atlas11 Service SHALL validate every row as a Pydantic District Need Record before returning the row through an API or agent tool.
2. WHEN the Atlas11 Service validates a District Need Record, THE Atlas11 Service SHALL require a Canonical District ID that satisfies the existing Project canonical identifier contract, a non-empty district name, finite non-negative funded commitments, finite non-negative Funding per Capita, a finite Need Score in `[0.0,1.0]`, a boolean Funding Gap value, an Indicator Quality value of exactly `measured`, `estimated`, or `illustrative`, a Snapshot Date that is either an ISO 8601 calendar date or the literal `TBD: needs source`, and retained Provenance.
3. WHEN a client sends `GET /gaps`, THE Atlas11 Service SHALL return HTTP 200 with a JSON collection of all validated District Need Records sorted by ascending Canonical District ID.
4. WHEN a client sends `GET /gaps?district_id={Canonical District ID}` for a validated record, THE Atlas11 Service SHALL return HTTP 200 with exactly that validated District Need Record.
5. IF a client sends `GET /gaps?district_id={Canonical District ID}` and no validated District Need Record has that Canonical District ID, THEN THE Atlas11 Service SHALL return HTTP 404 with a readable error and no fabricated gap data.
6. IF `need_scores.csv` is missing, unreadable, or contains a row that fails Pydantic validation, THEN THE Atlas11 Service SHALL return HTTP 503 with a readable error and SHALL NOT return a partial collection.
7. WHEN an agent calls `district_need(district_id)`, THE Atlas11 Service SHALL use the same Pydantic District Need Record source as `GET /gaps` for a known Canonical District ID.

### Requirement 6: Verify universal gap-finder properties

**User Story:** As a maintainer, I want generative tests for numerical invariants, so that the generated gap data remains bounded and directionally correct as source data changes.

#### Acceptance Criteria

1. WHEN Hypothesis generates finite valid Positively Oriented Indicator datasets and valid Need Weights, THE Atlas11 Gap Finder SHALL produce a finite Need Score in the inclusive range `[0.0,1.0]` for every generated district.
2. WHEN Hypothesis generates two finite valid datasets that differ only by a non-decreasing change to one district's Positively Oriented Indicator with a strictly positive Need Weight, THE Atlas11 Gap Finder SHALL produce a Need Score for that district in the changed dataset that is greater than or equal to the Need Score in the original dataset.
3. WHEN Hypothesis generates a finite valid dataset in which all values of one configured Positively Oriented Indicator are equal, THE Atlas11 Gap Finder SHALL assign normalized value `0.0` for that indicator to every generated district.
4. WHEN Hypothesis generates valid Funding per Capita values and Need Scores, THE Atlas11 Gap Finder SHALL classify a Funding Gap exactly according to Need Score greater than or equal to `0.6` and Funding per Capita less than or equal to the deterministic Inclusive Bottom Funding Quartile threshold.

## Non-goals

- Funding allocation, payment, transfer, or any claim that a Funding Gap classification causes a district to receive funds.
- Inference of a Project district from a display name, location text, or map geometry.
- Creation or alteration of raw project or indicator data during a need-score build.
- Fabrication of source dates, funding commitments, indicator values, or provenance.
