"""Testes dos serviços portáveis da UI (sem Streamlit)."""

from __future__ import annotations

from pathlib import Path

import pytest
from geoai.domains import DomainId
from geoai.portal import (
    DataBackendMode,
    attribution_lines,
    build_domain_card,
    demo_connection_policy,
    didactic_copy_text,
    future_supabase_policy_stub,
    list_domain_cards,
    load_parana_layer,
    quality_snapshot_for_demo,
    status_label_pt,
)
from geoai.presentation import AudienceLevel

REPO = Path(__file__).resolve().parents[1]


def test_demo_policy_is_local_artifacts() -> None:
    policy = demo_connection_policy()
    assert policy.mode == DataBackendMode.LOCAL_ARTIFACTS
    assert policy.requires_secret is False
    future = future_supabase_policy_stub()
    assert future.mode == DataBackendMode.REMOTE_SUPABASE_FUTURE
    assert future.requires_secret is True


def test_domain_cards_cover_four_domains() -> None:
    cards = list_domain_cards()
    assert {c.spec.domain_id for c in cards} == set(DomainId)
    energy = build_domain_card(DomainId.ENERGY)
    assert energy.availability.status == "partial"
    assert status_label_pt("planned") == "Planejado"


def test_load_parana_layer_from_versioned_artifacts() -> None:
    bundle = load_parana_layer(REPO)
    assert bundle.available is True
    assert bundle.feature_count == 1
    assert bundle.crs_epsg in {"EPSG:4674"}
    assert bundle.content_sha256_ok is True
    title, desc = didactic_copy_text(bundle, AudienceLevel.BASIC)
    assert "Paraná" in title or "Paraná" in desc
    lines = attribution_lines(bundle)
    assert any("Fonte:" in line for line in lines)
    assert any("Edição:" in line for line in lines)
    snap = quality_snapshot_for_demo(bundle)
    assert snap["status"] == "valid"
    assert snap["validation_all_valid"] is True


def test_load_parana_missing_geojson(tmp_path: Path) -> None:
    bundle = load_parana_layer(tmp_path)
    assert bundle.available is False
    assert bundle.missing_reason_pt
    snap = quality_snapshot_for_demo(bundle)
    assert snap["status"] == "rejected"


def test_folium_html_optional() -> None:
    folium = pytest.importorskip("folium")
    assert folium is not None
    from geoai.portal import folium_map_html

    bundle = load_parana_layer(REPO)
    html = folium_map_html(bundle, fill_opacity=0.2, line_weight=1.5)
    assert "Paraná" in html or "folium" in html.lower() or "<html" in html.lower()
    assert len(html) > 500
