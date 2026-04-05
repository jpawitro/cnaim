# CNAIM Python API Reference

## Overview

This package now provides two modeling layers:

1. Detailed transformer vertical slice:
   - `Transformer11To20kVPoFModel`
   - `Transformer11kVConsequenceModel`
2. Table-driven full coverage layer for all registry categories:
   - `CNAIMPoFModel`
   - `CNAIMConsequenceModel`

The full-coverage layer is driven by extracted CNAIM reference tables under
`src/cnaim/config/lookups/reference_tables`.

## Core Domain Models

### Assets

- `Asset`: base identity + family + asset category + optional subdivision.
- `NetworkAsset`: shared technical/risk fields used in CoF formulas
  (capacity, access, customer count, bunding, proximity, risk ratings).
- `TransformerAsset`, `CableAsset`, `SwitchgearAsset`, `OverheadLineAsset`,
  `LowVoltageAsset`: family-specific models.
- `AssetCatalog`: runtime discovery of supported families and categories from
  `asset_type_registry.json`.

### Installation Inputs

- `Installation`: user input model with optional defaults.
- `ResolvedInstallation`: explicit parameters used by engines after defaulting.

Generic PoF fields include:
- `utilisation_pct`
- `operating_voltage_pct`
- `tap_operations_per_day`
- `switchgear_duty_profile`
- `location_factor`

### Condition Inputs

- `AssetConditionInput`: generic observed/measured factors for all assets.
- `TransformerConditionInput`: transformer-specific observed/measured enums for
  the original vertical slice.

### Outputs

- `PoFResult`: current PoF + CHS + optional future points.
- `ConsequenceBreakdown`: financial/safety/environmental/network components.
- `RiskProfile`: final monetary risk + matrix coordinates + risk level.

## Formula Reference

### Health and PoF Equations

Implemented in `cnaim.health`:

- `beta_1`: $\beta_1 = \ln(5.5/0.5)/EL$
- `initial_health`: $HS_{initial}=0.5 \cdot e^{\beta_1 \cdot age}$ (capped at 5.5)
- `beta_2`: $\beta_2 = \ln(HS_{current}/0.5)/age$
- `health_score_excl_ehv_132kv_tf`: observed/measured factor combiner
- `current_health`: cap/collar + global clamping to $[0.5, 10]$
- `ageing_reduction_factor`: piecewise reduction used for future CHS
- `pof_cubic`: cubic Taylor approximation of CNAIM PoF

### Generic PoF Composition (`CNAIMPoFModel`)

1. Resolve `asset_category` -> `health_index_asset_category`.
2. Resolve functional failure category for PoF curves.
3. Resolve expected life from `normal_expected_life`.
4. Resolve duty factor from family-specific duty tables.
5. Compute CHS and PoF.

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

### Generic CoF Composition (`CNAIMConsequenceModel`)

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

## Full Table Index

A complete catalog of extracted reference tables (table number, id, source file,
row count) is documented in `docs/REFERENCE_TABLES.md`.

## Typical Usage

```python
from cnaim import (
    CNAIMConsequenceModel,
    CNAIMPoFModel,
    Installation,
    TransformerAsset,
)

asset = TransformerAsset(
    asset_id="TF-100",
    asset_name="Primary Transformer",
    asset_category="33kV Transformer (GM)",
    rated_capacity_kva=30000,
    no_customers=1000,
    kva_per_customer=45,
)
installation = Installation(
    age_years=15,
    utilisation_pct=80,
    tap_operations_per_day=12,
    location_factor=1.0,
)

pof_result = CNAIMPoFModel().calculate_current(asset, installation)
cof_result = CNAIMConsequenceModel().calculate(asset)
```
