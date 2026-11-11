"""Domínios temáticos do NAPI GeoAI (registro e indicadores-contrato)."""

from geoai.domains.indicators import (
    INDICATOR_CATALOG,
    IndicatorSpec,
    get_indicator,
    list_indicators,
)
from geoai.domains.registry import (
    DOMAIN_REGISTRY,
    DomainId,
    DomainSpec,
    get_domain,
    list_domains,
)

__all__ = [
    "DOMAIN_REGISTRY",
    "DomainId",
    "DomainSpec",
    "INDICATOR_CATALOG",
    "IndicatorSpec",
    "get_domain",
    "get_indicator",
    "list_domains",
    "list_indicators",
]
