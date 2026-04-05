# CNAIM Python API Reference

## Overview

The package currently exposes two modeling paths:

1. Transformer-focused vertical slice:
   - `Transformer11To20kVPoFModel`
   - `Transformer11kVConsequenceModel`
2. Table-driven generic coverage for all registry categories:
   - `CNAIMPoFModel`
   - `CNAIMConsequenceModel`

Both paths share core domain models (`Asset`, `Installation`, `PoFResult`,
`ConsequenceBreakdown`) and can be combined into a final `RiskProfile`.

## Public Exports

`from cnaim import ...` currently exposes:

- Assets and catalog:
  - `Asset`, `NetworkAsset`
  - `TransformerAsset`, `CableAsset`, `SwitchgearAsset`, `OverheadLineAsset`, `LowVoltageAsset`
  - `AssetCatalog`
- Installation:
  - `Installation`, `ResolvedInstallation`
- PoF:
  - `Transformer11To20kVPoFModel`, `TransformerConditionInput`
  - `CNAIMPoFModel`, `AssetConditionInput`
  - `PoFResult`
- Consequences:
  - `Transformer11kVConsequenceModel`
  - `CNAIMConsequenceModel`
  - `ConsequenceBreakdown`
- Diagnostics helpers:
  - `oil_test_modifier`, `dga_test_modifier`, `ffa_test_modifier`
- Risk:
  - `RiskProfile`

## Core Inputs and Outputs

### Assets

- `Asset`: base identity, family, category, optional subdivision.
- `NetworkAsset`: shared technical/risk metadata used in generic CoF and PoF.
- Family classes add validation/defaulting behavior:
  - `TransformerAsset`
  - `CableAsset`
  - `SwitchgearAsset`
  - `OverheadLineAsset`
  - `LowVoltageAsset`
- `AssetCatalog` discovers supported families/types from `asset_type_registry.json`.

### Installation

- `Installation`: user-facing optional fields.
- `ResolvedInstallation`: explicit/defaulted runtime values used by engines.
- Default resolution methods:
  - `Installation.resolve_for_transformer()`
  - `Installation.resolve_generic()`

### Conditions

- `TransformerConditionInput`: transformer vertical-slice condition inputs.
- `AssetConditionInput`: generic observed/measured factors and cap/collar values.

### Outputs

- `PoFResult`: current PoF (`pof`), current health score (`chs`), optional `future_points`.
- `ConsequenceBreakdown`: `financial`, `safety`, `environmental`, `network_performance`,
  and derived `total`.
- `RiskProfile`: monetized risk, matrix coordinates, and final risk level.

## API by Model

### Generic PoF (`CNAIMPoFModel`)

Primary methods:

- `calculate_current(asset: NetworkAsset, installation: Installation, condition: AssetConditionInput | None = None) -> PoFResult`
- `calculate_future(asset: NetworkAsset, installation: Installation, condition: AssetConditionInput | None = None, simulation_end_year: int = 100) -> PoFResult`

Implementation flow:

1. Map `asset_category` to `health_index_asset_category`.
2. Resolve functional failure category for PoF curve parameters.
3. Resolve expected life (`normal_expected_life`) with optional subdivision logic.
4. Resolve family-specific duty factor:
   - transformer: utilization and optional tap-operation factors
   - switchgear/lv: `switchgear_duty_profile`
   - cable: DF1 x DF2
5. Apply health equations and compute PoF.

Reference tables used:

- `categorisation_of_assets`
- `generic_terms_for_assets`
- `pof_curve_parameters`
- `normal_expected_life`
- `duty_factor_lut_distrib_tf`
- `duty_factor_lut_grid_prim_tf`
- `duty_factor_lut_switchgear`
- `duty_factor_lut_cables_df1`
- `duty_factor_lut_cables_df2`

### Generic CoF (`CNAIMConsequenceModel`)

Primary method:

- `calculate(asset: NetworkAsset) -> ConsequenceBreakdown`

Component formulas:

- Financial: $F = F_{ref} \cdot f_{type} \cdot f_{access}$
- Safety: $S = S_{ref} \cdot f_{safety} \cdot f_{reduction}$
- Environmental: $E = E_{ref} \cdot f_{size} \cdot f_{proximity} \cdot f_{bunding}$
- Network: $N = N_{ref} \cdot f_{customer}$

Reference tables used:

- `reference_costs_of_failure`
- `categorisation_of_assets`
- `type_financial_factors`
- `access_factor_swg_tf_asset`
- `access_factor_ohl`
- `safety_conseq_factor_sg_tf_oh`
- `safety_conseq_factor_cable`
- `safety_risk_reduction_factor`
- `size_enviromental_factor`
- `location_environ_al_factor`
- `ref_nw_perf_cost_fail_lv_hv`
- `customer_no_adjust_lv_hv_asset`

### Transformer Vertical Slice

`Transformer11To20kVPoFModel` methods:

- `calculate_current(asset: TransformerAsset, installation: Installation, condition: TransformerConditionInput | None = None) -> PoFResult`
- `calculate_future(asset: TransformerAsset, installation: Installation, condition: TransformerConditionInput | None = None, simulation_end_year: int = 100) -> PoFResult`

`Transformer11kVConsequenceModel` method:

- `calculate(asset: TransformerAsset) -> ConsequenceBreakdown`

### Diagnostics Helpers

All diagnostics helpers return a `ConditionModifier` object
(`factor`, `cap`, `collar`):

- `oil_test_modifier(...)`
  - oil condition score: $80 \cdot moisture + 125 \cdot acidity + 80 \cdot bd$
  - factor/collar from calibration tables by transformer group
- `dga_test_modifier(...)`
  - DGA score: $50H_2 + 30CH_4 + 30C_2H_4 + 30C_2H_6 + 120C_2H_2$
  - factor from DGA change category and DGA test-factor tables
- `ffa_test_modifier(...)`
  - factor from FFA banding table
  - collar from $2.33 \cdot ffa^{0.68}$ with CNAIM bounds

## Health and PoF Equations

Implemented in `cnaim.health`:

- `beta_1`: $\beta_1 = \ln(5.5 / 0.5) / EL$
- `initial_health`: $HS_{initial} = 0.5 \cdot e^{\beta_1 \cdot age}$ (capped at 5.5)
- `beta_2`: $\beta_2 = \ln(HS_{current} / 0.5) / age$
- `health_score_excl_ehv_132kv_tf`: observed/measured factor combiner
- `current_health`: applies cap/collar and clamps to $[0.5, 10]$
- `ageing_reduction_factor`: piecewise reduction for future CHS
- `pof_cubic`: cubic Taylor approximation of CNAIM PoF

## Risk Profile Composition

Create a final risk output with:

- `RiskProfile.from_results(asset_id, pof_result, consequence)`

Computation summary:

- Monetary risk: $risk = pof \cdot total\_cof$
- Matrix coordinates from CHS and CI bands in `risk_matrix_bands.json`
- Risk level thresholding (`Low`, `Medium`, `High`) from lookup config

## Reference Table Index

The full extracted table catalog (table number, id, source file, row count) is
in `docs/REFERENCE_TABLES.md`.

## Typical Usage

### Generic End-to-End Risk

```python
from cnaim import (
    CNAIMConsequenceModel,
    CNAIMPoFModel,
    Installation,
    RiskProfile,
    TransformerAsset,
)

asset = TransformerAsset(
    asset_id="TF-001",
    asset_name="Primary Transformer 1",
    asset_category="33kV Transformer (GM)",
    rated_capacity_kva=750,
    no_customers=750,
    kva_per_customer=51,
    bunded=True,
    proximity_to_water_m=100,
)

installation = Installation(
    age_years=12,
    utilisation_pct=80,
    tap_operations_per_day=10,
    location_factor=1.0,
)

pof = CNAIMPoFModel().calculate_current(asset=asset, installation=installation)
cof = CNAIMConsequenceModel().calculate(asset)
risk = RiskProfile.from_results(asset_id=asset.asset_id, pof_result=pof, consequence=cof)
```

### Diagnostics Helper Example

```python
from cnaim import oil_test_modifier

modifier = oil_test_modifier(
    moisture_ppm=15,
    acidity_mg_koh_g=0.15,
    bd_strength_kv=30,
    transformer_type_all="20kV Transformer (GM)",
)

print(modifier.factor, modifier.cap, modifier.collar)
```
