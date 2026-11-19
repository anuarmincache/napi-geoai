"""Contrato local do catálogo de mapas, sem rede e sem raster real obrigatório."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest
from geoai.catalog.entry import build_catalog_entry, frontend_view
from geoai.catalog.integrity import (
    integrity_record,
    sha256_file,
    verify_integrity,
    write_json,
)
from geoai.catalog.maringa import (
    ACQUISITION_ID,
    APPROVED_FRACTION,
    MUNICIPALITY_IBGE,
    build_maringa_pilot,
)
from geoai.catalog.style import DISPLAY_MAX, DISPLAY_MIN, ndvi_style
from geoai.catalog.updates import (
    AcquisitionSnapshot,
    CoverageRequest,
    attempt_is_due,
    decide_update,
    scene_tile_plan,
)

REPO = Path(__file__).resolve().parents[1]
PUBLIC = REPO / "catalog" / "public" / "4115200.json"
INTEGRITY = REPO / "catalog" / "integrity" / "4115200.json"


def _manifest() -> dict:
    return {
        "schema": "napi-ndvi-local-manifest-1",
        "algorithm": "napi-ndvi-block-writer-1",
        "ndvi_published": False,
        "peak_rss_mb": None,
        "peak_rss_status": "not_measured",
        "rule": "first_valid_tile_in_declared_order",
        "rows": 4,
        "cols": 4,
        "resolution_m": 10.0,
        "geotransform": [0.0, 10.0, 0.0, 100.0, 0.0, -10.0],
        "epsg": 32722,
        "gdal_version": "3.13.3",
        "nodata": -9999.0,
        "ndvi_dtype": "float32",
        "provenance_dtype": "uint8",
        "provenance_values": {"0": "nao_selecionado", "1": "22KCV", "2": "22KDV"},
        "counts": {
            "n_aoi": 10,
            "n_valid": 8,
            "pixels_per_tile": [5, 3],
            "overlap_both_valid": 2,
            "finite_ndvi_pixels": 8,
            "provenance_histogram": {"0": 8, "1": 5, "2": 3},
            "pixel_equation": "5 + 3 = 8",
        },
        "products": {
            "ndvi": {"name": "ndvi-demo.tif", "sha256": "", "bytes": 0},
            "provenance": {"name": "provenance-demo.tif", "sha256": "", "bytes": 0},
        },
    }


def _write_product(directory: Path, manifest: dict, role: str, payload: bytes) -> None:
    path = directory / manifest["products"][role]["name"]
    path.write_bytes(payload)
    manifest["products"][role]["sha256"] = sha256_file(path)
    manifest["products"][role]["bytes"] = len(payload)


def test_style_is_fixed_yellow_to_green_and_does_not_edit_values() -> None:
    style = ndvi_style()
    assert style["display_min"] == DISPLAY_MIN == 0.0
    assert style["display_max"] == DISPLAY_MAX == 0.8
    assert style["stops"][0]["hex"] == "#F4E04D"
    assert style["stops"][-1]["hex"] == "#1B5E20"
    assert style["nodata_display"] == "transparent"
    assert style["source_values_modified"] is False
    assert style["below_display_min"]["display"] == "endpoint_yellow"
    assert style["above_display_max"]["display"] == "endpoint_green"
    assert style["above_display_max"]["denser_vegetation"] is False
    assert style["outside_physical_interval"]["hex"] == "#7A7A7A"
    assert style["outside_physical_interval"]["denser_vegetation"] is False
    assert "saúde" not in style["legend_note_pt"]
    assert "produtividade" not in style["legend_note_pt"]


def test_missing_png_and_csv_stay_unavailable(tmp_path: Path) -> None:
    manifest = _manifest()
    _write_product(tmp_path, manifest, "ndvi", b"ndvi")
    _write_product(tmp_path, manifest, "provenance", b"prov")
    entry = build_catalog_entry(
        manifest,
        ibge="4115200",
        municipality="Maringá",
        acquisition_id=ACQUISITION_ID,
        processed_at="2026-11-17T00:18:08.8872919Z",
        product_dir=tmp_path,
        quality_status="approved",
        quality_note_pt="Fração válida suficiente.",
        fraction_gate_passed=True,
    )
    assert entry["downloads"]["geotiff"]["available"] is True
    assert entry["downloads"]["geotiff"]["filename"] == "ndvi-demo.tif"
    assert entry["downloads"]["png"]["available"] is False
    assert entry["downloads"]["csv"]["reason"] == "nao_gerado"
    assert entry["publication_state"] == "nao_publicado"
    assert entry["ndvi_published"] is False
    assert entry["update_policy"]["scheduler_active"] is False
    assert entry["update_policy"]["guarantees_new_valid_scene"] is False
    view = frontend_view(entry)
    assert view["published"] is False
    assert view["public_downloads"] == []
    assert view["files"]["geotiff"] == {
        "exists": True,
        "validated": True,
        "published": False,
    }
    assert view["files"]["png"] == {
        "exists": False,
        "validated": False,
        "published": False,
    }
    assert view["files"]["csv"]["exists"] is False
    assert view["files"]["json"]["published"] is False


def test_tampered_geotiff_is_not_offered(tmp_path: Path) -> None:
    manifest = _manifest()
    _write_product(tmp_path, manifest, "ndvi", b"ndvi")
    _write_product(tmp_path, manifest, "provenance", b"prov")
    manifest["products"]["ndvi"]["sha256"] = "0" * 64
    entry = build_catalog_entry(
        manifest,
        ibge="4115200",
        municipality="Maringá",
        acquisition_id=ACQUISITION_ID,
        processed_at="2026-11-17T00:18:08.8872919Z",
        product_dir=tmp_path,
        quality_status="approved",
        quality_note_pt="Fração válida suficiente.",
        fraction_gate_passed=True,
    )
    assert entry["downloads"]["geotiff"]["exists"] is True
    assert entry["downloads"]["geotiff"]["validated"] is False
    assert entry["downloads"]["geotiff"]["public_download"] is False
    assert entry["downloads"]["geotiff"]["reason"] == "checksum_divergente"
    assert frontend_view(entry)["public_downloads"] == []


def test_overlap_is_not_subtracted_from_the_sum(tmp_path: Path) -> None:
    manifest = _manifest()
    manifest["counts"]["pixel_equation"] = "5 - 2 + 3 = 8"
    manifest["counts"]["n_valid"] = 6
    _write_product(tmp_path, manifest, "ndvi", b"ndvi")
    _write_product(tmp_path, manifest, "provenance", b"prov")
    with pytest.raises(ValueError, match="soma_das_tiles_divergente"):
        build_catalog_entry(
            manifest,
            ibge="4115200",
            municipality="Maringá",
            acquisition_id=ACQUISITION_ID,
            processed_at="2026-11-17T00:18:08.8872919Z",
            product_dir=tmp_path,
            quality_status="approved",
            quality_note_pt="Fração válida suficiente.",
            fraction_gate_passed=True,
        )


def test_public_entry_rejects_a_local_path(tmp_path: Path) -> None:
    manifest = _manifest()
    _write_product(tmp_path, manifest, "ndvi", b"ndvi")
    _write_product(tmp_path, manifest, "provenance", b"prov")
    manifest["algorithm"] = r"C:\Users\Admin\ndvi"
    with pytest.raises(ValueError, match="caminho_local_no_catalogo_publico"):
        build_catalog_entry(
            manifest,
            ibge="4115200",
            municipality="Maringá",
            acquisition_id=ACQUISITION_ID,
            processed_at="2026-11-17T00:18:08.8872919Z",
            product_dir=tmp_path,
            quality_status="approved",
            quality_note_pt="Fração válida suficiente.",
            fraction_gate_passed=True,
        )


def test_publication_flag_is_refused(tmp_path: Path) -> None:
    manifest = _manifest()
    _write_product(tmp_path, manifest, "ndvi", b"ndvi")
    _write_product(tmp_path, manifest, "provenance", b"prov")
    with pytest.raises(PermissionError, match="publicacao_recusada"):
        build_catalog_entry(
            manifest,
            ibge="4115200",
            municipality="Maringá",
            acquisition_id=ACQUISITION_ID,
            processed_at="2026-11-17T00:18:08.8872919Z",
            product_dir=tmp_path,
            quality_status="approved",
            quality_note_pt="Fração válida suficiente.",
            fraction_gate_passed=True,
            publish=True,
        )


def test_tile_plan_downloads_a_shared_scene_once() -> None:
    jobs = scene_tile_plan(
        (
            CoverageRequest("4115200", ACQUISITION_ID, "22KCV"),
            CoverageRequest("4106902", ACQUISITION_ID, "22KCV"),
            CoverageRequest("4115200", ACQUISITION_ID, "22KDV"),
        )
    )
    assert len(jobs) == 2
    shared = jobs[0]
    assert shared.tile_id == "22KCV"
    assert shared.municipalities == ("4106902", "4115200")


def test_failed_new_scene_keeps_the_approved_map() -> None:
    current = AcquisitionSnapshot(
        ACQUISITION_ID,
        "2026-11-12",
        "approved_with_reservations",
        "napi-ndvi-block-writer-1",
    )
    decision = decide_update(
        current_acquisition_id=ACQUISITION_ID,
        candidate_acquisition_id="S2B_20261127T133149_R081",
        candidate_valid_fraction=0.42,
        candidate_validated=False,
        current=current,
    )
    assert decision.action == "manter"
    assert decision.retained_acquisition_id == ACQUISITION_ID
    assert decision.preserved == current
    assert decision.scheduler_active is False
    assert decision.guarantees_new_valid_scene is False
    assert "mais recente" in decision.user_message_pt
    assert "última imagem válida" in decision.user_message_pt
    assert "não garante" in decision.user_message_pt


def test_validated_new_scene_replaces_without_deleting_history() -> None:
    current = AcquisitionSnapshot(
        ACQUISITION_ID,
        "2026-11-12",
        "approved_with_reservations",
        "napi-ndvi-block-writer-1",
    )
    decision = decide_update(
        current_acquisition_id=ACQUISITION_ID,
        candidate_acquisition_id="S2B_20261127T133149_R081",
        candidate_valid_fraction=0.81,
        candidate_validated=True,
        current=current,
    )
    assert decision.action == "substituir"
    assert decision.preserved == current
    assert decision.preserved.image_date == "2026-11-12"
    assert decision.preserved.quality_status == "approved_with_reservations"
    assert decision.preserved.algorithm_version == "napi-ndvi-block-writer-1"
    assert "histórico" in decision.user_message_pt


def test_attempt_uses_the_fifteen_day_interval_only() -> None:
    assert attempt_is_due(date(2026, 11, 17), date(2026, 12, 1)) is False
    assert attempt_is_due(date(2026, 11, 17), date(2026, 12, 2)) is True
    with pytest.raises(ValueError, match="intervalo_recusado"):
        attempt_is_due(None, date(2026, 11, 17), interval_days=1)


def test_committed_maringa_catalog_matches_the_real_manifest() -> None:
    entry = json.loads(PUBLIC.read_text(encoding="utf-8"))
    record = json.loads(INTEGRITY.read_text(encoding="utf-8"))
    verify_integrity(PUBLIC, record)
    assert entry["municipality"]["ibge"] == MUNICIPALITY_IBGE
    assert entry["acquisition_id"] == ACQUISITION_ID
    assert entry["image_date"] == "2026-11-12"
    assert entry["valid_pixel_fraction"] == APPROVED_FRACTION
    assert entry["counts"]["n_valid"] == 3_565_350
    assert entry["counts"]["pixels_per_tile"]["22KCV"] == 3_086_107
    assert entry["counts"]["overlap_both_valid"] == 2_034_052
    assert entry["counts"]["pixel_equation"] == "3086107 + 479243 = 3565350"
    assert entry["downloads"]["geotiff"]["sha256"].startswith("4b0a50e4")
    assert entry["downloads"]["png"]["available"] is False
    assert entry["downloads"]["csv"]["available"] is False
    assert entry["downloads"]["json"]["validated"] is True
    assert entry["downloads"]["json"]["public_download"] is False
    assert entry["downloads"]["geotiff"]["public_download"] is False
    assert frontend_view(entry)["public_downloads"] == []
    assert entry["acquisitions"][0]["algorithm_version"] == "napi-ndvi-block-writer-1"
    assert entry["acquisitions"][0]["quality_status"] == "approved_with_reservations"
    assert entry["ndvi_published"] is False
    assert entry["previous_acquisitions"] == []
    assert entry["quality"]["outside_unit_interval"]["count"] == 686
    text = PUBLIC.read_text(encoding="utf-8").lower()
    assert "c:\\" not in text
    assert "onedrive" not in text
    assert record["public_entry"] == "catalog/public/4115200.json"


def test_maringa_builder_accepts_only_the_approved_measurement(
    tmp_path: Path,
) -> None:
    manifest = {
        "epsg": 32722,
        "resolution_m": 10.0,
        "counts": {
            "n_aoi": 4_876_416,
            "n_valid": 3_565_349,
            "pixels_per_tile": [3_086_107, 479_243],
            "overlap_both_valid": 2_034_052,
        },
    }
    with pytest.raises(RuntimeError, match="medicao_nao_aprovada"):
        build_maringa_pilot(manifest, tmp_path)


def test_rewritten_public_entry_has_the_same_integrity_contract(
    tmp_path: Path,
) -> None:
    entry = {"schema": "napi-map-catalog-1", "ibge": "4115200"}
    body = write_json(tmp_path / "4115200.json", entry)
    record = integrity_record("catalog/public/4115200.json", body)
    write_json(tmp_path / "integrity.json", record)
    verify_integrity(tmp_path / "4115200.json", record)
