"""Coverage tests for table-driven generic PoF and CoF models."""

from __future__ import annotations

from cnaim import (
    AssetCatalog,
    CableAsset,
    CNAIMConsequenceModel,
    CNAIMPoFModel,
    Installation,
    LowVoltageAsset,
    NetworkAsset,
    OverheadLineAsset,
    SwitchgearAsset,
    TransformerAsset,
)
from cnaim.enums import AssetFamily


def _build_asset(
    family: AssetFamily,
    asset_category: str,
    index: int,
) -> NetworkAsset:
    """Create a valid test asset instance for the requested family/category."""
    asset_id = f"A-{index}"
    asset_name = f"Asset {index}"

    if family == AssetFamily.TRANSFORMER:
        return TransformerAsset(
            asset_id=asset_id,
            asset_name=asset_name,
            asset_category=asset_category,
            rated_capacity_kva=750,
            no_customers=500,
            kva_per_customer=50,
            proximity_to_water_m=100,
            bunded=True,
        )
    if family == AssetFamily.CABLE:
        return CableAsset(
            asset_id=asset_id,
            asset_name=asset_name,
            asset_category=asset_category,
            rated_capacity_kva=750,
            no_customers=500,
            kva_per_customer=50,
            proximity_to_water_m=100,
            bunded=True,
        )
    if family == AssetFamily.SWITCHGEAR:
        return SwitchgearAsset(
            asset_id=asset_id,
            asset_name=asset_name,
            asset_category=asset_category,
            rated_capacity_kva=750,
            no_customers=500,
            kva_per_customer=50,
            proximity_to_water_m=100,
            bunded=True,
        )
    if family == AssetFamily.OVERHEAD_LINE:
        return OverheadLineAsset(
            asset_id=asset_id,
            asset_name=asset_name,
            asset_category=asset_category,
            rated_capacity_kva=750,
            no_customers=500,
            kva_per_customer=50,
            proximity_to_water_m=100,
            bunded=True,
        )
    if family == AssetFamily.LOW_VOLTAGE:
        return LowVoltageAsset(
            asset_id=asset_id,
            asset_name=asset_name,
            asset_category=asset_category,
            rated_capacity_kva=750,
            no_customers=500,
            kva_per_customer=50,
            proximity_to_water_m=100,
            bunded=True,
        )

    raise ValueError(f"Unsupported family in test fixture: {family}")


def test_generic_models_cover_all_registry_asset_categories() -> None:
    """Ensure generic models evaluate every asset category in the registry."""
    catalog = AssetCatalog()
    pof_model = CNAIMPoFModel()
    consequence_model = CNAIMConsequenceModel()

    installation = Installation(
        age_years=12,
        utilisation_pct=75,
        operating_voltage_pct=80,
        tap_operations_per_day=10,
        location_factor=1.0,
    )

    evaluated = 0
    for family_name in catalog.list_families():
        family = AssetFamily(family_name)
        for category in catalog.list_asset_types(family):
            asset = _build_asset(family, category, evaluated)
            pof_result = pof_model.calculate_current(
                asset=asset,
                installation=installation,
            )
            consequence = consequence_model.calculate(asset)

            assert pof_result.pof >= 0
            assert 0.5 <= pof_result.chs <= 10
            assert consequence.total >= 0
            evaluated += 1

    assert evaluated == 61
