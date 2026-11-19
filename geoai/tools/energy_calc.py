"""Cálculos energéticos determinísticos e auditáveis (Issue #38).

Todas as funções são puras: recebem apenas entradas explícitas do usuário
e hipóteses declaradas. Nenhum parâmetro é inferido, estimado por IA ou
preenchido silenciosamente. Entradas inválidas levantam ``ValueError``.

Fórmulas
--------
Consumo mensal de um equipamento (kWh/mês)::

    E = P[W] × h[h/dia] × d[dias/mês] × n / 1000

Custo mensal (R$)::

    C = E[kWh] × tarifa[R$/kWh]

Potência fotovoltaica preliminar (kWp)::

    P = E_mês / (HSP × dias × PR)

onde HSP são as horas de sol pleno (kWh/m²/dia no plano dos módulos,
numericamente iguais às horas a 1 kW/m²) e PR é a taxa de desempenho
do sistema (adimensional, 0 < PR ≤ 1).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

DAYS_PER_MONTH_DEFAULT = 30


def _finite(value: float, name: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} deve ser numérico") from exc
    if not math.isfinite(number):
        raise ValueError(f"{name} deve ser finito")
    return number


@dataclass(frozen=True, slots=True)
class ApplianceUse:
    """Uso de um equipamento informado pelo usuário."""

    name: str
    power_w: float
    hours_per_day: float
    days_per_month: float = DAYS_PER_MONTH_DEFAULT
    quantity: float = 1


def appliance_monthly_kwh(item: ApplianceUse) -> float:
    power = _finite(item.power_w, "potência (W)")
    hours = _finite(item.hours_per_day, "horas por dia")
    days = _finite(item.days_per_month, "dias por mês")
    qty = _finite(item.quantity, "quantidade")
    if power < 0 or qty < 0:
        raise ValueError("potência e quantidade não podem ser negativas")
    if not 0 <= hours <= 24:
        raise ValueError("horas por dia deve estar entre 0 e 24")
    if not 0 <= days <= 31:
        raise ValueError("dias por mês deve estar entre 0 e 31")
    return power * hours * days * qty / 1000.0


def total_monthly_kwh(items: list[ApplianceUse]) -> float:
    return math.fsum(appliance_monthly_kwh(item) for item in items)


def monthly_cost_brl(energy_kwh: float, tariff_brl_per_kwh: float) -> float:
    energy = _finite(energy_kwh, "energia (kWh)")
    tariff = _finite(tariff_brl_per_kwh, "tarifa (R$/kWh)")
    if energy < 0 or tariff < 0:
        raise ValueError("energia e tarifa não podem ser negativas")
    return energy * tariff


@dataclass(frozen=True, slots=True)
class PvSizingResult:
    """Resultado do dimensionamento preliminar (simulação, classe C)."""

    monthly_kwh: float
    hsp_kwh_m2_day: float
    performance_ratio: float
    days: float
    power_kwp: float
    module_wp: float | None
    module_count: int | None
    installed_kwp: float | None
    expected_monthly_kwh: float | None


def pv_preliminary_sizing(
    monthly_kwh: float,
    hsp_kwh_m2_day: float,
    performance_ratio: float,
    *,
    module_wp: float | None = None,
    days: float = DAYS_PER_MONTH_DEFAULT,
) -> PvSizingResult:
    """Potência de pico necessária para compensar ``monthly_kwh``.

    Não considera custo de disponibilidade, sombreamento, orientação,
    degradação, limites de conexão nem aspectos econômicos.
    """

    energy = _finite(monthly_kwh, "consumo mensal (kWh)")
    hsp = _finite(hsp_kwh_m2_day, "HSP (kWh/m²/dia)")
    pr = _finite(performance_ratio, "taxa de desempenho (PR)")
    n_days = _finite(days, "dias")
    if energy < 0:
        raise ValueError("consumo mensal não pode ser negativo")
    if hsp <= 0:
        raise ValueError("HSP deve ser maior que zero")
    if not 0 < pr <= 1:
        raise ValueError("PR deve estar no intervalo (0, 1]")
    if n_days <= 0:
        raise ValueError("dias deve ser maior que zero")

    power_kwp = energy / (hsp * n_days * pr)
    count: int | None = None
    installed: float | None = None
    expected: float | None = None
    wp: float | None = None
    if module_wp is not None:
        wp = _finite(module_wp, "potência do módulo (Wp)")
        if wp <= 0:
            raise ValueError("potência do módulo deve ser maior que zero")
        count = math.ceil(round(power_kwp * 1000.0 / wp, 9))
        installed = count * wp / 1000.0
        expected = installed * hsp * n_days * pr
    return PvSizingResult(
        monthly_kwh=energy,
        hsp_kwh_m2_day=hsp,
        performance_ratio=pr,
        days=n_days,
        power_kwp=power_kwp,
        module_wp=wp,
        module_count=count,
        installed_kwp=installed,
        expected_monthly_kwh=expected,
    )
