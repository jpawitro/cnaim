# CNAIM Python Foundation

This repository contains a CNAIM-aligned Python module with OOP design and
configuration-driven lookup tables.

## Current Scope

- Core domain models with hierarchy: assets, installation, PoF, consequences,
    and final risk profile.
- Pydantic validation for input models.
- Lookup tables stored as JSON under `src/cnaim/config/lookups`.
- Full reference-table extraction under
    `src/cnaim/config/lookups/reference_tables` (243 tables).
- Generic table-driven PoF/CoF models covering all asset classes/subclasses
    from `asset_type_registry.json`.
- PDF-first regression tests anchored to `references/cnaim.pdf` and
    completeness markers documented in this README.
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

## PDF-First Completeness Snapshot (2026-04-05)

Baseline:
- Source PDF: `references/cnaim.pdf`
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
    - Long-term risk matrix weighting pipeline (tables 239-241)
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
