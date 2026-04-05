# CNAIM Python Toolkit

This repository contains a CNAIM-aligned Python library providing models and
lookup-driven pipelines for assessing asset condition, probability of failure
(PoF), consequence of failure (CoF), and final risk profiles used by UK
Distribution Network Operators (DNOs).

## Current Scope

- Core domain models with hierarchy: assets, installation, PoF, consequences,
    and final risk profile.
- Pydantic validation for input models.
- Lookup tables stored as JSON under `src/cnaim/config/lookups`.
- Full reference-table extraction under
    `src/cnaim/config/lookups/reference_tables` (243 tables).
- PDF-first regression tests anchored to the Ofgem CNAIM methodology PDF (link
    below); local copies are not included in this repository.
- Unit tests with pytest.
- Linting and formatting with Ruff.
- Type checking with mypy.
- Pre-commit hooks for local quality gates.

## Package Structure

- `src/cnaim/assets.py`: Asset hierarchy and asset catalog.
- `src/cnaim/installation.py`: Installation parameters with default resolution.
- `src/cnaim/health.py`: Health score equations and PoF helper formulas.
- `src/cnaim/pof.py`: Transformer-focused PoF model.
- `src/cnaim/consequences.py`: Transformer-focused CoF model.
- `src/cnaim/generic_models.py`: Full-coverage table-driven PoF/CoF models.
- `src/cnaim/risk_profile.py`: Final risk profile class and risk matrix mapping.
- `src/cnaim/config/lookups/*.json`: Lookup/config data for formulas and mappings.

## Documentation

- `docs/API_REFERENCE.md`: Detailed API documentation and formula mapping.
- `docs/REFERENCE_TABLES.md`: Complete index of extracted reference tables.

## About CNAIM

CNAIM stands for "Common Network Asset Indices Methodology". It is a UK DNO
methodology that defines a consistent approach to assessing asset condition,
deriving condition indices, and converting condition into probability of
failure (PoF) and consequence of failure (CoF) scores. CNAIM provides:

- a set of calibrated reference tables and scoring rules,
- procedures for translating inspection and diagnostic information into
    condition inputs, and
- guidance to combine PoF and CoF into risk rankings.

This project implements a selection of CNAIM's lookup tables and model
pipelines to reproduce the parts of the methodology needed for computational
risk assessment and automated regression tests.

## Project name and rationale

The previous title used the word "Foundation", which can imply an organisation
or standards body. This repository is a code library and collection of
utilities — a "toolkit" — so the project has been renamed here to "CNAIM
Python Toolkit" to better reflect its purpose.

Alternative names you may prefer:
- CNAIM Python Library
- CNAIM Toolkit
- CNAIM Models
- CNAIM Tools

Tell me which one you prefer and I will update the repo title and badges.

## PDF-First Completeness Snapshot (2026-04-05)

Baseline:
- Source PDF: [Ofgem CNAIM methodology](https://www.ofgem.gov.uk/decision/decision-distribution-network-operators-common-network-asset-indices-methodology-0)
- Methodology edition: DNO Common Network Asset Indices Methodology v2.1 (01 April 2021)

Implemented runtime scope:
- `CNAIMPoFModel` (generic, table-driven): `src/cnaim/generic_models.py`
- `CNAIMConsequenceModel` (generic, table-driven): `src/cnaim/generic_models.py`
- `Transformer11To20kVPoFModel` (specialized): `src/cnaim/pof.py`
- Transformer diagnostics modifiers (Oil/DGA/FFA): `src/cnaim/diagnostics.py`
- Risk profile composition: `src/cnaim/risk_profile.py`

Coverage metrics:
- Expected asset register categories from PDF taxonomy: 61
- Implemented asset categories in runtime registry: 61
- Coverage: 61/61 (100%).
- Extracted reference table JSON files: 243
- Effective numbered table coverage after 31A/31B handling: 240/241 (99.6%)
- Known data issue: Table 112 mapping inconsistency (manifest number exists,
    but no dedicated canonical table JSON mapped solely to 112)

Current implementation status by capability:
- Implemented:
    - Core generic PoF/CoF pipelines
    - Transformer-specific PoF path
    - Duty-factor lookups in generic and transformer models
    - Health-score and reliability modifiers in active paths
    - Financial/Safety/Environmental CoF components
- Partial:
    - In-year risk matrix weighting depth
    - General location-factor methodology from full lookup stack
    - Generic OCI/MCI derivation breadth outside transformer-focused diagnostics
    - Network performance CoF for EHV/132-specific reference paths
- Gap:
    - Long-term risk matrix weighting pipeline (tables 236-241)
    - Full submarine/location-factor calibration execution path

Prioritized next actions:
1. Implement full risk-matrix weighting for in-year and long-term cases (tables 236-241).
2. Implement location-factor computation from lookup calibration tables (22-30).
3. Add broad OCI/MCI evaluators for non-transformer families.
4. Resolve the Table 112 mapping defect with one canonical table artifact.
5. Add section-level regression tests for risk matrices, location factors, and OCI/MCI completeness.


## Development Commands

```bash
uv sync --all-groups
uv run pytest
uv run ruff check .
uv run ruff format .
uv run mypy src tests
uv run pre-commit run --all-files
```
