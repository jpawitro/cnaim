"""Foundation package for a CNAIM-aligned risk assessment module."""

from .assets import (
    Asset,
    AssetCatalog,
    CableAsset,
    LowVoltageAsset,
    NetworkAsset,
    OverheadLineAsset,
    SwitchgearAsset,
    TransformerAsset,
)
from .consequences import (
    ConsequenceBreakdown,
    Transformer11kVConsequenceModel,
)
from .diagnostics import (
    dga_test_modifier,
    ffa_test_modifier,
    oil_test_modifier,
)
from .generic_models import (
    AssetConditionInput,
    CNAIMConsequenceModel,
    CNAIMPoFModel,
)
from .installation import Installation, ResolvedInstallation
from .pof import (
    PoFResult,
    Transformer11To20kVPoFModel,
    TransformerConditionInput,
)
from .risk_profile import RiskProfile

__all__ = [
    "Asset",
    "AssetCatalog",
    "AssetConditionInput",
    "CNAIMConsequenceModel",
    "CNAIMPoFModel",
    "CableAsset",
    "ConsequenceBreakdown",
    "dga_test_modifier",
    "ffa_test_modifier",
    "Installation",
    "LowVoltageAsset",
    "NetworkAsset",
    "oil_test_modifier",
    "OverheadLineAsset",
    "PoFResult",
    "ResolvedInstallation",
    "RiskProfile",
    "SwitchgearAsset",
    "Transformer11To20kVPoFModel",
    "Transformer11kVConsequenceModel",
    "TransformerAsset",
    "TransformerConditionInput",
]
