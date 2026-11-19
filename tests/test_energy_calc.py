"""Ferramentas determinísticas de cálculo (Issue #38)."""

from __future__ import annotations

import pytest
from geoai.tools import (
    ApplianceUse,
    appliance_monthly_kwh,
    monthly_cost_brl,
    pv_preliminary_sizing,
    total_monthly_kwh,
)


def test_appliance_monthly_kwh_formula() -> None:
    item = ApplianceUse("Chuveiro", power_w=5500, hours_per_day=0.5)
    assert appliance_monthly_kwh(item) == pytest.approx(82.5)


def test_total_and_cost() -> None:
    items = [
        ApplianceUse("A", 1000, 2, 30, 1),
        ApplianceUse("B", 100, 10, 20, 3),
    ]
    total = total_monthly_kwh(items)
    assert total == pytest.approx(60 + 60)
    assert monthly_cost_brl(total, 0.9) == pytest.approx(108.0)


@pytest.mark.parametrize(
    "item",
    [
        ApplianceUse("x", -1, 1),
        ApplianceUse("x", 100, 25),
        ApplianceUse("x", 100, 1, 32),
        ApplianceUse("x", float("nan"), 1),
    ],
)
def test_appliance_rejects_invalid(item: ApplianceUse) -> None:
    with pytest.raises(ValueError):
        appliance_monthly_kwh(item)


def test_pv_sizing_formula_and_modules() -> None:
    res = pv_preliminary_sizing(450, 4.5, 0.75, module_wp=550)
    assert res.power_kwp == pytest.approx(450 / (4.5 * 30 * 0.75))
    assert res.module_count == 9
    assert res.installed_kwp == pytest.approx(4.95)
    assert res.expected_monthly_kwh == pytest.approx(4.95 * 4.5 * 30 * 0.75)
    assert res.expected_monthly_kwh >= 450


def test_pv_sizing_exact_module_multiple_not_overcounted() -> None:
    # 4,4 kWp exatos com módulos de 550 Wp → 8 módulos, não 9.
    energy = 4.4 * 5.0 * 30 * 0.8
    res = pv_preliminary_sizing(energy, 5.0, 0.8, module_wp=550)
    assert res.module_count == 8


def test_pv_sizing_without_module() -> None:
    res = pv_preliminary_sizing(300, 5, 0.8)
    assert res.module_count is None
    assert res.installed_kwp is None


@pytest.mark.parametrize(
    ("hsp", "pr"),
    [(0, 0.8), (-1, 0.8), (5, 0), (5, 1.2), (float("inf"), 0.8)],
)
def test_pv_sizing_rejects_invalid(hsp: float, pr: float) -> None:
    with pytest.raises(ValueError):
        pv_preliminary_sizing(300, hsp, pr)


def test_tariff_never_defaulted() -> None:
    with pytest.raises(ValueError):
        monthly_cost_brl(100, None)  # type: ignore[arg-type]
