"""Simple example runner for CNAIM models.

Constructs an example TransformerAsset, computes PoF and CoF, and prints
the derived RiskProfile. Run with `python main.py`.
"""

from cnaim import (
    CNAIMConsequenceModel,
    CNAIMPoFModel,
    Installation,
    RiskProfile,
    TransformerAsset,
)


def main() -> None:
    """Run a small end-to-end risk profile example."""

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

    pof_model = CNAIMPoFModel()
    consequence_model = CNAIMConsequenceModel()

    pof_result = pof_model.calculate_current(asset=asset, installation=installation)
    consequence = consequence_model.calculate(asset)
    risk_profile = RiskProfile.from_results(
        asset_id=asset.asset_id, pof_result=pof_result, consequence=consequence
    )

    print(
        f"Asset {risk_profile.asset_id}: PoF={risk_profile.pof:.6f}, "
        f"CoF={risk_profile.total_cof:.2f}, "
        f"Risk={risk_profile.monetary_risk:.2f}, "
        f"Level={risk_profile.risk_level}"
    )


if __name__ == "__main__":
    main()
