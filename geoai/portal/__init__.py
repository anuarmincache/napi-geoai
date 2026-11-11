"""Serviços portáveis para interfaces (Streamlit agora; portal/API depois)."""

from geoai.portal.connection_policy import (
    DEFAULT_DEMO_POLICY,
    ConnectionPolicy,
    DataBackendMode,
    demo_connection_policy,
    future_supabase_policy_stub,
)
from geoai.portal.domain_views import (
    DomainAvailability,
    DomainCard,
    build_domain_card,
    list_domain_cards,
    status_label_pt,
)
from geoai.portal.parana_layer import (
    ParanaLayerBundle,
    attribution_lines,
    didactic_copy_text,
    folium_map_html,
    load_parana_layer,
    quality_snapshot_for_demo,
)

__all__ = [
    "ConnectionPolicy",
    "DEFAULT_DEMO_POLICY",
    "DataBackendMode",
    "DomainAvailability",
    "DomainCard",
    "ParanaLayerBundle",
    "attribution_lines",
    "build_domain_card",
    "demo_connection_policy",
    "didactic_copy_text",
    "folium_map_html",
    "future_supabase_policy_stub",
    "list_domain_cards",
    "load_parana_layer",
    "quality_snapshot_for_demo",
    "status_label_pt",
]
