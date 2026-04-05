"""Regression tests for transformer diagnostics condition modifiers."""

from __future__ import annotations

import pytest

from cnaim import dga_test_modifier, ffa_test_modifier, oil_test_modifier


def test_dga_modifier_default_matches_baseline_case() -> None:
    """Validate default DGA modifier outputs for the baseline case."""
    modifier = dga_test_modifier()

    assert modifier.factor == pytest.approx(1.0)
    assert modifier.cap == pytest.approx(10.0)
    assert modifier.collar == pytest.approx(1.0)


def test_oil_modifier_matches_baseline_case() -> None:
    """Validate oil-test modifier outputs for a representative input case."""
    modifier = oil_test_modifier(
        moisture_ppm=15,
        acidity_mg_koh_g=0.15,
        bd_strength_kv=30,
        transformer_type_all="20kV Transformer (GM)",
    )

    assert modifier.factor == pytest.approx(1.4)
    assert modifier.cap == pytest.approx(10.0)
    assert modifier.collar == pytest.approx(5.5)


def test_ffa_modifier_matches_baseline_case() -> None:
    """Validate FFA modifier outputs for a representative input case."""
    modifier = ffa_test_modifier(furfuraldehyde_ppm=50)

    assert modifier.factor == pytest.approx(1.6)
    assert modifier.cap == pytest.approx(10.0)
    assert modifier.collar == pytest.approx(7.0)
