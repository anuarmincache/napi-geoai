"""Identidade do piloto. Área, bbox e geometria vêm da malha oficial."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

PILOT_CD_MUN = "4115200"
PILOT_REPOSITORY = "napi-geoai-mvp04"
REUSE_ENV = "NAPI_VALIDATED_B04"
B04_RELATIVE = (
    "data/raw/sentinel/S2B_20261112T133149_R081/22KCV/B04_10m.jp2"
)
MESH_RELATIVE = "data/raw/ibge/PR_Municipios_2025.zip"
CATALOG_NAME = "sentinel_maringa_pilot.json"

# Cobertura do footprint sobre o polígono. Não é fração de pixels válidos.
MIN_FOOTPRINT_COVERAGE = 0.999
# Aceite só depois da máscara SCL na AOI. Não é o cloud cover do item.
MIN_VALID_PIXEL_FRACTION = 0.70

STAC_SEARCH_URL = "https://stac.dataspace.copernicus.eu/v1/search"
STAC_COLLECTION_URL = (
    "https://stac.dataspace.copernicus.eu/v1/collections/sentinel-2-l2a"
)
STAC_COLLECTION = "sentinel-2-l2a"


def pipeline_b04(repo: Path) -> Path:
    """B04 dentro da raiz que executa o pipeline. Não aponta para outro checkout."""

    return repo / B04_RELATIVE


def configured_reuse_b04() -> Path | None:
    """Caminho explícito. Sem a variável, nenhum checkout vizinho é consultado."""

    raw = os.environ.get(REUSE_ENV, "").strip()
    if not raw:
        return None
    return Path(raw)


def _jp2_identity(path: Path, expected_bytes: int) -> str:
    if not path.is_file():
        return "missing"
    if path.stat().st_size != expected_bytes:
        return "size_mismatch"
    header = path.read_bytes()[:64]
    if b"ftypjp2" not in header and b"jP  " not in header:
        return "not_jp2"
    return "verified"


def _expected_b04_bytes(catalog: dict[str, Any]) -> int:
    probe = catalog.get("access_probe_scene") or {}
    table = catalog.get("official_band_bytes") or probe.get("official_band_bytes") or {}
    raw = (table.get("22KCV") or {}).get("B04_10m")
    if isinstance(raw, int) and raw > 0:
        return raw
    raise ValueError("b04_tamanho_ausente")


def reuse_report(repo: Path, catalog: dict[str, Any]) -> dict[str, str]:
    """Reuso só com tamanho oficial e assinatura JP2. Não copia nem apaga."""

    expected = _expected_b04_bytes(catalog)
    local_state = _jp2_identity(pipeline_b04(repo), expected)
    if local_state == "verified":
        return {"status": "local_verified"}
    if local_state != "missing":
        return {"status": "local_preserved"}
    external = configured_reuse_b04()
    if external is None:
        return {"status": "not_configured"}
    external_state = _jp2_identity(external, expected)
    if external_state == "verified":
        return {"status": "external_verified"}
    if external_state == "missing":
        return {"status": "external_missing"}
    return {"status": "external_rejected"}


def band_read_path(local: Path, external: Path | None) -> Path:
    """Usa o JP2 local ou, se ele não existir, o caminho explícito já conferido."""

    if local.is_file():
        return local
    if external is not None and external.is_file():
        return external
    return local
