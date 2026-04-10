"""PDF-first regression tests for baseline consistency checks."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from cnaim import Installation, Transformer11To20kVPoFModel, TransformerAsset
from cnaim.health import mmi

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PDF_PATH = PROJECT_ROOT / "docs" / "dno_common_network_asset_indices_methodology_v2.1_final_01-04-2021.pdf"
README_PATH = PROJECT_ROOT / "README.md"


def _read_readme_text() -> str:
    """Load the README text used as the PDF-first baseline documentation."""
    return README_PATH.read_text(encoding="utf-8")


def test_pdf_first_reference_artifacts_exist() -> None:
    """Ensure the canonical PDF and README baseline files are available."""
    assert PDF_PATH.exists()
    assert README_PATH.exists()


def test_readme_contains_expected_pdf_first_coverage_markers() -> None:
    """Validate key completeness markers documented in README snapshot."""
    readme = _read_readme_text()
    assert "Coverage: 61/61 (100%)." in readme
    assert "240/241 (99.6%)" in readme
    assert "Table 112 mapping" in readme


def test_mmi_matches_documented_reference_cases() -> None:
    """Verify MMI outputs for deterministic reference input combinations."""
    assert mmi([1, 1.5], 1.5, 1.5, 1) == pytest.approx(1.5)
    assert mmi([1, 1], 1.0, 1.0, 0) == pytest.approx(1.0)
    assert mmi([0.75, 0.5], 1.0, 2.0, 0) == pytest.approx(0.375)
    assert mmi([1, 2, 3, 4, 5, 6], 2.0, 1.0, 4) == pytest.approx(10.5)
    assert mmi([9, 8, 7, 6, 5, 4], 5.0, 1.0, 1) == pytest.approx(9.0)
    assert mmi([9, math.nan, 3, 3, 3, 1], 6.0, 1.0, 20) == pytest.approx(10.0)
    assert mmi([9, math.nan, 1, 1, 1, 1], 6.0, 1.0, 20) == pytest.approx(9.0)


def test_future_transformer_projection_matches_pdf_baseline_snapshot() -> None:
    """Lock selected future-PoF points for the current PDF-first baseline setup."""
    model = Transformer11To20kVPoFModel()
    asset = TransformerAsset(asset_id="A-PDF", asset_name="PDF Baseline")
    installation = Installation(age_years=12)

    result = model.calculate_future(
        asset=asset,
        installation=installation,
        simulation_end_year=100,
    )

    assert len(result.future_points) == 101
    assert result.future_points[0].pof == pytest.approx(0.0022230351544959997, rel=1e-9)
    assert result.future_points[75].pof == pytest.approx(0.012253502042715044, rel=1e-9)
    assert result.future_points[100].pof == pytest.approx(0.068069594419125, rel=1e-9)
    assert result.future_points[100].future_health_score == pytest.approx(
        20.15813706958846,
        rel=1e-9,
    )
