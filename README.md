# CNAIM Python Toolkit

This repository contains a CNAIM-aligned Python library providing models and
lookup-driven pipelines for assessing asset condition, probability of failure
(PoF), consequence of failure (CoF), and final risk profiles used by UK
Distribution Network Operators (DNOs).

## Current Scope

- Core domain models with hierarchy: assets, installation, PoF, consequences,
    and final risk profile.
- Pydantic validation for input models.
- Submarine cable runtime support for location factor, OCI/MCI condition
    modifiers, and EHV/132kV network-performance routing.
- Lookup tables stored as JSON under `src/cnaim/config/lookups`.
- Full reference-table extraction under
    `src/cnaim/config/lookups/reference_tables` (243 tables).
- PDF-first regression tests anchored to the Ofgem CNAIM methodology PDF (link
    below) with a local baseline copy under `docs/`.
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
- `src/cnaim/submarine.py`: Submarine cable location-factor and condition-modifier pipeline.
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

## PDF-First Completeness Snapshot (2026-04-10)

Baseline:
- Source PDF: [Ofgem CNAIM methodology](https://www.ofgem.gov.uk/decision/decision-distribution-network-operators-common-network-asset-indices-methodology-0)
- Methodology edition: DNO Common Network Asset Indices Methodology v2.1 (01 April 2021)

Implemented runtime scope:
- `CNAIMPoFModel` (generic, table-driven): `src/cnaim/generic_models.py`
- `CNAIMConsequenceModel` (generic, table-driven): `src/cnaim/generic_models.py`
- `Transformer11To20kVPoFModel` (specialized): `src/cnaim/pof.py`
- Transformer diagnostics modifiers (Oil/DGA/FFA): `src/cnaim/diagnostics.py`
- Submarine cable location factor and OCI/MCI pipeline: `src/cnaim/submarine.py`
- EHV/132kV secure network-performance CoF routing (including submarine cables): `src/cnaim/generic_models.py`
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
    - Submarine cable location-factor execution path (tables 25, 27-30)
    - Submarine cable OCI/MCI execution path (tables 107, 189-191)
    - Duty-factor lookups in generic and transformer models
    - Health-score and reliability modifiers in active paths
    - Financial/Safety/Environmental CoF components
    - EHV/132kV secure network-performance CoF path (table 235)
- Partial:
    - General non-submarine location-factor methodology from tables 22-26
    - Generic OCI/MCI derivation breadth outside transformer and submarine paths
    - Risk-profile output remains a simplified current-year monetary/matrix view,
        not the full table-weighted CNAIM risk-matrix workflow
- Gap:
    - In-year risk-matrix weighting pipeline (tables 236-238)
    - Long-term risk / risk-index pipeline (tables 239-241)
    - Runtime evaluators for the remaining family-specific OCI/MCI tables
        already extracted under `reference_tables`

Prioritized next actions:
1. Implement table-driven in-year and long-term risk-matrix weighting using tables 236-241 and expose those results from `RiskProfile`.
2. Implement the general non-submarine location-factor stack from tables 22-26 and wire it into `Installation.resolve_generic()` / `CNAIMPoFModel`.
3. Add family-specific OCI/MCI evaluators for the remaining extracted assets (LV/HV/EHV switchgear, non-submarine cables, poles, towers, fittings, conductors) and convert them into `AssetConditionInput`.
4. Resolve the Table 112 mapping defect with one canonical table artifact and extend PDF-first regression coverage around manifest/table consistency.
5. Expand section-level regression tests for risk matrices, generic location factors, and family-specific OCI/MCI execution completeness.


## Development Commands

```bash
uv sync --all-groups
uv run pytest
uv run ruff check .
uv run ruff format .
uv run mypy src tests
uv run pre-commit run --all-files
```

## License

- Code: Apache License 2.0 ([LICENSE](LICENSE))
- CNAIM-derived data and table content attribution: Open Government Licence v3.0 guidance ([DATA_LICENSE.md](DATA_LICENSE.md))
