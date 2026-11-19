"""Inventário agrícola local. Não calcula produção, rendimento nem rebanho."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from geoai.connectors.catalog import get_source
from geoai.connectors.ibge import EXPECTED_PR_MUNICIPALITY_COUNT
from geoai.portal.agro_panel import load_agro_panel_bundle
from geoai.portal.paths import (
    agro_panel_path,
    municipalities_geojson_path,
    municipalities_validation_path,
    repo_root_from_here,
)

__all__ = [
    "AgricultureSourceStatus",
    "agriculture_source_inventory",
]


@dataclass(frozen=True, slots=True)
class AgricultureSourceStatus:
    """Estado de uma base. Moldura territorial não é indicador agrícola."""

    theme_pt: str
    source_id: str | None
    organization: str
    catalogued: bool
    local_file: bool
    validated: bool
    integrated: bool
    supports_agricultural_indicator: bool
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


def agriculture_source_inventory(
    repo_root: Path | None = None,
) -> tuple[AgricultureSourceStatus, ...]:
    """Fontes pedidas para a aba. Nenhum indicador agrícola fica pronto."""

    root = repo_root or repo_root_from_here()
    mesh_file, mesh_ok = _municipal_mesh(root)
    agro_file = agro_panel_path(root).is_file()
    agro_ok = load_agro_panel_bundle(root).available
    pam_id = "ibge.sidra.pam.tabela_5457"
    ppm_id = "ibge.sidra.ppm.tabela_3939"
    return (
        AgricultureSourceStatus(
            theme_pt="Limites municipais",
            source_id="ibge.malhas_municipais.pr_municipios_2025",
            organization="IBGE",
            catalogued=_is_catalogued(
                "ibge.malhas_municipais.pr_municipios_2025"
            ),
            local_file=mesh_file,
            validated=mesh_ok,
            integrated=mesh_ok,
            supports_agricultural_indicator=False,
            note_pt=(
                "Malha municipio_2025, 399 municípios, CRS EPSG:4674, "
                "área oficial AREA_KM2. Serve de moldura. Não é área "
                "plantada, colhida nem produção."
            ),
        ),
        AgricultureSourceStatus(
            theme_pt="Produção Agrícola Municipal",
            source_id=pam_id if agro_ok else None,
            organization="IBGE/SIDRA — PAM",
            catalogued=agro_ok and _is_catalogued(pam_id),
            local_file=agro_file,
            validated=agro_ok,
            integrated=agro_ok,
            supports_agricultural_indicator=agro_ok,
            note_pt=(
                "Tabela 5457 integrada: área plantada, área colhida, "
                "quantidade produzida e rendimento das principais culturas. "
                "Município ausente numa cultura não vira zero."
                if agro_ok
                else "Não está no catálogo e não há tabela local. Área plantada, "
                "área colhida, produção e rendimento ficam indisponíveis. "
                "Município ausente numa cultura não vira zero."
            ),
        ),
        AgricultureSourceStatus(
            theme_pt="Pecuária municipal",
            source_id=ppm_id if agro_ok else None,
            organization="IBGE/SIDRA — PPM",
            catalogued=agro_ok and _is_catalogued(ppm_id),
            local_file=agro_file,
            validated=agro_ok,
            integrated=agro_ok,
            supports_agricultural_indicator=agro_ok,
            note_pt=(
                "Tabelas 3939 e 74 integradas: bovinos, suínos, galináceos e "
                "leite. Efetivo de rebanho não é resíduo disponível."
                if agro_ok
                else "Não está no catálogo e não há tabela local. Rebanho e "
                "produtos de origem animal não são estimados."
            ),
        ),
        AgricultureSourceStatus(
            theme_pt="Séries agrícolas",
            source_id=None,
            organization="CONAB",
            catalogued=False,
            local_file=_has_named_file(root, ("conab",)),
            validated=False,
            integrated=False,
            supports_agricultural_indicator=False,
            note_pt=(
                "Não está no catálogo e não há arquivo local. A granularidade "
                "municipal ainda não foi conferida."
            ),
        ),
        AgricultureSourceStatus(
            theme_pt="Indicadores agropecuários do Paraná",
            source_id=None,
            organization="IPARDES",
            catalogued=False,
            local_file=_has_named_file(root, ("ipardes",)),
            validated=False,
            integrated=False,
            supports_agricultural_indicator=False,
            note_pt=(
                "Não está no catálogo e não há arquivo local. Não substitui "
                "a tabela IBGE enquanto a origem de cada número não for lida."
            ),
        ),
        AgricultureSourceStatus(
            theme_pt="Uso agrícola do solo",
            source_id="mapbiomas.brazil.lulc",
            organization="MapBiomas",
            catalogued=_is_catalogued("mapbiomas.brazil.lulc"),
            local_file=_has_named_file(root, ("mapbiomas",)),
            validated=False,
            integrated=False,
            supports_agricultural_indicator=False,
            note_pt=(
                "Coleção 11 permanece em contrato, sem arquivo. Hectare de "
                "cobertura não é produção, rendimento nem área plantada PAM."
            ),
        ),
    )
