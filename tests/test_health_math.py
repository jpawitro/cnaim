"""Unit tests for core health-math helper functions."""

from __future__ import annotations

import pytest

from cnaim.health import beta_1, current_health, initial_health


def test_beta_1_matches_reference_values() -> None:
    """Check beta_1 against known numeric reference values."""
    assert beta_1(10) == pytest.approx(0.239789527, rel=1e-6)
    assert beta_1(5) == pytest.approx(0.479579055, rel=1e-6)


def test_initial_health_uncapped() -> None:
    """Verify initial health computation when cap is not reached."""
    assert initial_health(1, 2) == pytest.approx(3.694528049, rel=1e-9)


def test_initial_health_capped() -> None:
    """Verify initial health is capped at the CNAIM upper bound."""
    assert initial_health(100, 200) == pytest.approx(5.5)


def test_current_health_caps_and_collars() -> None:
    """Validate current health cap/collar behavior across edge inputs."""
    assert current_health(2, 3) == pytest.approx(6)
    assert current_health(2, 3, reliability_factor=20) == pytest.approx(10)
    assert current_health(200, 300) == pytest.approx(10)
