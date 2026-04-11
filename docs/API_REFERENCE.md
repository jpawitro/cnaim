# CNAIM Python API Reference

## Overview

The package currently exposes three API layers:

1. Transformer-focused vertical slice:
   - `Transformer11To20kVPoFModel`
   - `Transformer11kVConsequenceModel`
2. Table-driven generic coverage for all registry categories:
   - `CNAIMPoFModel`
   - `CNAIMConsequenceModel`
3. Submarine cable specialisation layered onto the generic path:
  - `submarine_location_factor`
  - `SubmarineCableConditionInput`
  - submarine OCI/MCI modifier helpers

Both paths share core domain models (`Asset`, `Installation`, `PoFResult`,
`ConsequenceBreakdown`) and can be combined into a final `RiskProfile`.

## Public Exports

`from cnaim import ...` currently exposes:

- Assets and catalog:
  - `Asset`, `NetworkAsset`
  - `TransformerAsset`, `CableAsset`, `SwitchgearAsset`, `OverheadLineAsset`, `LowVoltageAsset`
  - `AssetCatalog`
- Submarine enums:
  - `SubmarineTopography`, `SubmarineSituation`
  - `CombinedWaveEnergyIntensity`
  - `SubmarineArmourCondition`, `SheathTestResult`
- Installation:
  - `Installation`, `ResolvedInstallation`
- PoF:
  - `Transformer11To20kVPoFModel`, `TransformerConditionInput`
  - `CNAIMPoFModel`, `AssetConditionInput`
  - `SubmarineCableConditionInput`
  - `PoFResult`
- Consequences:
  - `Transformer11kVConsequenceModel`
  - `CNAIMConsequenceModel`
  - `ConsequenceBreakdown`
- Diagnostics helpers:
  - `oil_test_modifier`, `dga_test_modifier`, `ffa_test_modifier`
- Submarine helpers:
  - `submarine_location_factor`
  - `submarine_armour_condition_modifier`
  - `submarine_sheath_test_modifier`
  - `submarine_partial_discharge_modifier`
  - `submarine_fault_history_modifier`
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
  - `Installation.resolve_for_submarine_cable()`

### Conditions

- `TransformerConditionInput`: transformer vertical-slice condition inputs.
- `AssetConditionInput`: generic observed/measured factors and cap/collar values.
- `SubmarineCableConditionInput`: submarine-specific observed/measured raw
  inputs converted into `AssetConditionInput` using CNAIM MMI combination rules.

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
5. For non-submarine assets, resolve location factor from tables 22-26.
6. For submarine cable assets, resolve location factor from tables 25 and 27-30.
7. Apply health equations and compute PoF.

Reference tables used:

- `categorisation_of_assets`
- `generic_terms_for_assets`
- `pof_curve_parameters`
- `normal_expected_life`
- `distance_from_coast_factor_lut`
- `altitude_factor_lut`
- `corrosion_category_factor_lut`
- `environment_indoor_outdoor`
- `increment_constants`
- `submarin_cable_topog_factor`
- `submarin_cable_sitution_factor`
- `submarin_cable_wind_wave`
- `combined_wave_ct_energy_factor`
- `duty_factor_lut_distrib_tf`
- `duty_factor_lut_grid_prim_tf`
- `duty_factor_lut_switchgear`
- `duty_factor_lut_cables_df1`
- `duty_factor_lut_cables_df2`

Location-factor routing notes:

- Non-submarine cable categories remain neutral (`location_factor=1.0`) unless
  `Installation.location_factor` is explicitly provided, because tables 22-24
  do not define cable-specific columns.
- Explicit `Installation.location_factor` overrides table-derived values.

### Generic CoF (`CNAIMConsequenceModel`)

Primary method:

- `calculate(asset: NetworkAsset) -> ConsequenceBreakdown`

Component formulas:

- Financial: $F = F_{ref} \cdot f_{type} \cdot f_{access}$
- Safety: $S = S_{ref} \cdot f_{safety} \cdot f_{reduction}$
- Environmental: $E = E_{ref} \cdot f_{size} \cdot f_{proximity} \cdot f_{bunding}$
- Network (LV/HV): $N = N_{ref} \cdot f_{customer}$
- Network (EHV/132kV secure assets): $N = N_{ref,secure}$

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
- `ref_nw_perf_cost_of_fail_ehv`
- `customer_no_adjust_lv_hv_asset`

Special routing currently implemented:

- EHV and 132kV secure-network assets use table 235 directly for network
  performance cost of failure.
- `EHV Sub Cable` and `132kV Sub Cable` are routed through that same secure
  network path.

### Transformer Vertical Slice

`Transformer11To20kVPoFModel` methods:

- `calculate_current(asset: TransformerAsset, installation: Installation, condition: TransformerConditionInput | None = None) -> PoFResult`
- `calculate_future(asset: TransformerAsset, installation: Installation, condition: TransformerConditionInput | None = None, simulation_end_year: int = 100) -> PoFResult`

Transformer location-factor behavior:

- Uses the same table-driven location-factor stack from tables 22-26 as the
  generic path (`transformers` column mapping).
- Installation placement defaults from table 26 when available, then falls back
  to `Indoor` in transformer-specific resolution.
- Explicit `Installation.location_factor` takes precedence over table lookup.

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

### Submarine Helpers

The submarine helpers expose the currently implemented non-transformer
condition/location execution path from the methodology:

- `submarine_location_factor(...)`
  - computes CNAIM equations 18 and 19 using tables 25 and 27-30
- `submarine_armour_condition_modifier(...)`
  - observed condition input from table 107
- `submarine_sheath_test_modifier(...)`
  - measured condition input from table 189
- `submarine_partial_discharge_modifier(...)`
  - measured condition input from table 190
- `submarine_fault_history_modifier(...)`
  - measured condition input from table 191
- `SubmarineCableConditionInput.to_asset_condition_input()`
  - combines submarine OCI/MCI values into generic `AssetConditionInput`
    using CNAIM MMI parameters

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

Current limitation:

- The runtime `RiskProfile` is still the simplified current-year monetary risk
  view. The methodology's table-driven in-year and long-term risk weighting
  pipeline from tables 236-241 is not yet executed.

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

### Submarine End-to-End Example

```python
from cnaim import (
  CNAIMConsequenceModel,
  CNAIMPoFModel,
  CableAsset,
  CombinedWaveEnergyIntensity,
  Installation,
  SheathTestResult,
  SubmarineArmourCondition,
  SubmarineCableConditionInput,
  SubmarineSituation,
  SubmarineTopography,
)

asset = CableAsset(
  asset_id="SUB-001",
  asset_name="EHV Submarine Cable",
  asset_category="EHV Sub Cable",
  topography=SubmarineTopography.VERY_HIGH,
  situation=SubmarineSituation.BURIED,
  wind_wave_rating=2,
  combined_wave_energy_intensity=CombinedWaveEnergyIntensity.MODERATE,
  is_landlocked=False,
)

installation = Installation(age_years=20)
condition = SubmarineCableConditionInput(
  armour_condition=SubmarineArmourCondition.POOR,
  sheath_test_result=SheathTestResult.FAILED_MINOR,
  partial_discharge_level="Medium",
  fault_rate=0.02,
).to_asset_condition_input()

pof = CNAIMPoFModel().calculate_current(asset=asset, installation=installation, condition=condition)
cof = CNAIMConsequenceModel().calculate(asset)
```
