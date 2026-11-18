"""Inventário ambiental local. Não calcula cobertura, desmatamento ou aptidão."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from geoai.connectors.catalog import get_source
from geoai.connectors.ibge import EXPECTED_PR_MUNICIPALITY_COUNT
from geoai.portal.paths import (
    municipalities_geojson_path,
    municipalities_validation_path,
    repo_root_from_here,
)

__all__ = [
    "EnvironmentSourceStatus",
    "environment_source_inventory",
]


@dataclass(frozen=True, slots=True)
class EnvironmentSourceStatus:
    """Estado de uma base. Catalogada não significa arquivo utilizável."""

    theme_pt: str
    source_id: str | None
    organization: str
    catalogued: bool
    local_file: bool
    validated: bool
    integrated: bool
    supports_environmental_indicator: bool
    note_pt: str


def _is_catalogued(source_id: str) -> bool:
    try:
        get_source(source_id)
    except KeyError:
        return False
    return True


def _has_named_file(root: Path, tokens: tuple[str, ...]) -> bool:
    for base in (root / "data" / "raw", root / "data" / "derived"):
        if not base.is_dir():
            continue
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            name = path.name.casefold()
            if any(token in name for token in tokens):
                return True
    return False


def _municipal_mesh(root: Path) -> tuple[bool, bool]:
    geojson = municipalities_geojson_path(root)
    validation_path = municipalities_validation_path(root)
    local_file = geojson.is_file()
    if not validation_path.is_file() or not local_file:
        return local_file, False
    validation = json.loads(validation_path.read_text(encoding="utf-8"))
    full = validation.get("validation_full") or {}
    validated = (
        validation.get("feature_count") == EXPECTED_PR_MUNICIPALITY_COUNT
        and validation.get("unique_cd_mun") == EXPECTED_PR_MUNICIPALITY_COUNT
        and validation.get("validation_exportable") is True
        and full.get("all_valid") is True
    )
    return True, validated


def environment_source_inventory(
    repo_root: Path | None = None,
) -> tuple[EnvironmentSourceStatus, ...]:
    """Quatro temas pedidos. Nenhum indicador ambiental é marcado como pronto."""

    root = repo_root or repo_root_from_here()
    mesh_file, mesh_ok = _municipal_mesh(root)
    mapbiomas_id = "mapbiomas.brazil.lulc"
    return (
        EnvironmentSourceStatus(
            theme_pt="Limites municipais",
            source_id="ibge.malhas_municipais.pr_municipios_2025",
            organization="IBGE",
            catalogued=_is_catalogued(
                "ibge.malhas_municipais.pr_municipios_2025"
            ),
            local_file=mesh_file,
            validated=mesh_ok,
            integrated=mesh_ok,
            supports_environmental_indicator=False,
            note_pt=(
                "Malha municipio_2025, 399 municípios, CRS EPSG:4674, "
                "área oficial AREA_KM2. Serve de moldura territorial. "
                "Não é cobertura do solo."
            ),
        ),
        EnvironmentSourceStatus(
            theme_pt="Uso e cobertura da terra",
            source_id=mapbiomas_id,
            organization="MapBiomas",
            catalogued=_is_catalogued(mapbiomas_id),
            local_file=_has_named_file(root, ("mapbiomas",)),
            validated=False,
            integrated=False,
            supports_environmental_indicator=False,
            note_pt=(
                "Coleção 11 identificada na página oficial de estatísticas "
                "(1985–2025, hectares). Arquivo, SHA-256 e indicador ausentes. "
                "Percentual de vegetação não pode ser exibido."
            ),
        ),
        EnvironmentSourceStatus(
            theme_pt="Unidades de conservação",
            source_id=None,
            organization="MMA/ICMBio/IAT",
            catalogued=False,
            local_file=_has_named_file(
                root, ("cnuc", "icmbio", "unidade_conservacao")
            ),
            validated=False,
            integrated=False,
            supports_environmental_indicator=False,
            note_pt=(
                "Não está no catálogo de fontes e não há arquivo local. "
                "Nenhuma UC é atribuída a município."
            ),
        ),
        EnvironmentSourceStatus(
            theme_pt="Recursos hídricos",
            source_id=None,
            organization="ANA/IAT",
            catalogued=False,
            local_file=_has_named_file(
                root, ("snirh", "ottocod", "bacia_hidrografica")
            ),
            validated=False,
            integrated=False,
            supports_environmental_indicator=False,
            note_pt=(
                "Não está no catálogo de fontes e não há arquivo local. "
                "Não há indicador de disponibilidade hídrica."
            ),
        ),
    )
