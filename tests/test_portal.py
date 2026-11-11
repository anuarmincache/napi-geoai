"""Testes dos serviços portáveis da UI (sem Streamlit)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import geopandas as gpd
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
from shapely.geometry import box

REPO = Path(__file__).resolve().parents[1]
DERIVED = REPO / "data" / "derived"


def _stage_derived(tmp_path: Path) -> Path:
    dest = tmp_path / "data" / "derived"
    dest.mkdir(parents=True)
    for name in (
        "parana_uf_2025.geojson",
        "parana_uf_2025.provenance.json",
        "parana_uf_2025.validation.json",
    ):
        shutil.copy2(DERIVED / name, dest / name)
    return tmp_path


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
    assert bundle.validated_for_map is True
    assert bundle.feature_count == 1
    assert bundle.crs_epsg == "EPSG:4674"
    assert bundle.content_sha256_ok is True
    title, desc = didactic_copy_text(bundle, AudienceLevel.BASIC)
    assert "Paraná" in title or "Paraná" in desc
    lines = attribution_lines(bundle)
    assert any("Fonte:" in line for line in lines)
    assert any("Edição:" in line for line in lines)
    snap = quality_snapshot_for_demo(bundle)
    assert snap["status"] == "valid"
    assert snap["determined"] is True
    assert snap["validation_all_valid"] is True
    assert snap["retrieved_at"]
    assert "ibge_code" not in snap


def test_load_parana_missing_geojson(tmp_path: Path) -> None:
    bundle = load_parana_layer(tmp_path)
    assert bundle.available is False
    assert bundle.missing_reason_pt
    snap = quality_snapshot_for_demo(bundle)
    assert snap["layer_validated_for_display"] is False
    assert snap["determined"] is False


def test_fail_closed_on_sha_mismatch(tmp_path: Path) -> None:
    root = _stage_derived(tmp_path)
    prov_path = root / "data" / "derived" / "parana_uf_2025.provenance.json"
    prov = json.loads(prov_path.read_text(encoding="utf-8"))
    prov["derived_geojson_sha256"] = "0" * 64
    prov_path.write_text(json.dumps(prov), encoding="utf-8")
    bundle = load_parana_layer(root)
    assert bundle.available is False
    assert bundle.content_sha256_ok is False
    assert "SHA-256" in (bundle.missing_reason_pt or "")
    with pytest.raises(FileNotFoundError):
        from geoai.portal import folium_map_html

        folium_map_html(bundle)


def test_fail_closed_without_crs_evidence(tmp_path: Path) -> None:
    root = _stage_derived(tmp_path)
    geo_path = root / "data" / "derived" / "parana_uf_2025.geojson"
    gdf = gpd.GeoDataFrame({"id": [1]}, geometry=[box(-54, -26, -48, -22)])
    # Sem CRS no arquivo.
    gdf.to_file(geo_path, driver="GeoJSON")
    val_path = root / "data" / "derived" / "parana_uf_2025.validation.json"
    val = json.loads(val_path.read_text(encoding="utf-8"))
    val.pop("source_crs", None)
    val_path.write_text(json.dumps(val), encoding="utf-8")
    # Proveniência: recalcular sha para não falhar antes do CRS.
    import hashlib

    digest = hashlib.sha256(geo_path.read_bytes()).hexdigest()
    prov_path = root / "data" / "derived" / "parana_uf_2025.provenance.json"
    prov = json.loads(prov_path.read_text(encoding="utf-8"))
    prov["derived_geojson_sha256"] = digest
    prov_path.write_text(json.dumps(prov), encoding="utf-8")

    bundle = load_parana_layer(root)
    assert bundle.available is False
    assert "CRS" in (bundle.missing_reason_pt or "")


def test_quality_snapshot_partial_provenance_undetermined(tmp_path: Path) -> None:
    root = _stage_derived(tmp_path)
    prov_path = root / "data" / "derived" / "parana_uf_2025.provenance.json"
    prov = json.loads(prov_path.read_text(encoding="utf-8"))
    prov.pop("retrieved_at", None)
    prov_path.write_text(json.dumps(prov), encoding="utf-8")
    bundle = load_parana_layer(root)
    # SHA ainda ok → mapa pode ficar disponível, mas qualidade não determinada.
    assert bundle.available is True
    snap = quality_snapshot_for_demo(bundle)
    assert snap["status"] == "undetermined"
    assert snap["determined"] is False
    assert "retrieved_at" in snap["missing_provenance_fields"]
    assert snap["retrieved_at"] is None
    assert "ibge_code" not in snap


def test_folium_html_optional() -> None:
    folium = pytest.importorskip("folium")
    assert folium is not None
    from geoai.portal import folium_map_html

    bundle = load_parana_layer(REPO)
    html = folium_map_html(bundle, fill_opacity=0.2, line_weight=1.5)
    assert "Paraná" in html or "folium" in html.lower() or "<html" in html.lower()
    assert len(html) > 500
