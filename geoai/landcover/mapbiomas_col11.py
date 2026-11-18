"""Contrato da Coleção 11 municipal. Não lê arquivo e não calcula o Paraná."""

from __future__ import annotations

import math
from dataclasses import dataclass

# Página do produto e página da tabela. O href direto do .xlsx não foi
# extraído nesta etapa; o nome abaixo é o produto pedido, ainda sem SHA-256.
STATISTICS_PAGE = "https://brasil.mapbiomas.org/downloads/estatisticas/"
COVERAGE_PAGE = (
    "https://brasil.mapbiomas.org/iniciativas-e-produtos/"
    "cobertura-e-uso-da-terra/cobertura-30m/cobertura/"
)
TERMS_PAGE = "https://old-brasil.mapbiomas.org/termos-de-uso/"
PRODUCT_LABEL = "Biomas, Estados e Municípios | Cobertura 30m - Coleção 11"
EXPECTED_FILENAME = "MAPBIOMAS_BRAZIL-COL.11-BIOME_STATE_MUNICIPALITY.xlsx"
COLLECTION = 11
YEAR_MIN = 1985
YEAR_MAX = 2025
UNIT = "ha"
RESOLUTION_M = 30
SENSOR = "Landsat"
LOCAL_FILE = False
CONTENT_SHA256 = None
CONTENT_BYTES = None

# Códigos publicados na página de cobertura da Coleção 11 (nível, id, pai).
_LEGEND_ROWS: tuple[tuple[int, int, int | None, str], ...] = (
    (1, 1, None, "Formação Florestal"),
    (2, 3, 1, "Formação Florestal"),
    (2, 6, 1, "Floresta Alagável"),
    (2, 4, 1, "Formação Savânica"),
    (2, 7, 1, "Savana Alagada (beta)"),
    (2, 5, 1, "Mangue"),
    (2, 49, 1, "Restinga Arbórea"),
    (1, 10, None, "Vegetação Herbácea e Arbustiva"),
    (2, 11, 10, "Campo Alagado e Área Pantanosa"),
    (2, 77, 10, "Formação Herbácea Arbustiva"),
    (2, 12, 10, "Formação Campestre"),
    (2, 84, 10, "Marisma (beta)"),
    (2, 50, 10, "Restinga Herbácea ou Arbustiva"),
    (2, 32, 10, "Apicum"),
    (2, 29, 10, "Afloramento Rochoso"),
    (1, 14, None, "Agropecuária"),
    (2, 15, 14, "Pastagem"),
    (2, 18, 14, "Agricultura"),
    (3, 19, 18, "Lavoura Temporária"),
    (4, 39, 19, "Soja"),
    (4, 20, 19, "Cana"),
    (4, 40, 19, "Arroz"),
    (4, 62, 19, "Algodão (beta)"),
    (4, 41, 19, "Outras Lavouras Temporárias"),
    (3, 36, 18, "Lavoura Perene"),
    (4, 46, 36, "Café"),
    (4, 47, 36, "Citrus"),
    (4, 35, 36, "Dendê"),
    (4, 48, 36, "Outras Lavouras Perenes"),
    (2, 9, 14, "Silvicultura"),
    (2, 21, 14, "Mosaico de Usos"),
    (1, 22, None, "Área não vegetada"),
    (2, 23, 22, "Praia, Duna e Areal"),
    (2, 24, 22, "Área urbanizada"),
    (2, 30, 22, "Mineração"),
    (2, 75, 22, "Usina Fotovoltaica"),
    (2, 91, 22, "Parque eólico (beta)"),
    (2, 25, 22, "Outras Áreas Não Vegetadas"),
    (1, 26, None, "Corpo D'Água"),
    (2, 33, 26, "Rio, Lago e Oceano"),
    (2, 31, 26, "Aquicultura"),
)

CLASS_PARENT: dict[int, int | None] = {
    class_id: parent for _level, class_id, parent, _name in _LEGEND_ROWS
}
CLASS_NAME: dict[int, str] = {
    class_id: name for _level, class_id, _parent, name in _LEGEND_ROWS
}

# Grupos de exibição. Cada grupo lista folhas; o pai não entra no mesmo grupo.
DISPLAY_GROUPS: dict[str, tuple[int, ...]] = {
    "formacao_florestal": (3, 6, 4, 7, 5, 49),
    "vegetacao_herbacea_arbustiva": (11, 77, 12, 84, 50, 32, 29),
    "pastagem": (15,),
    "agricultura": (39, 20, 40, 62, 41, 46, 47, 35, 48),
    "silvicultura": (9,),
    "mosaico_de_usos": (21,),
    "area_urbanizada": (24,),
    "outras_nao_vegetadas": (23, 30, 75, 91, 25),
    "corpo_dagua": (33, 31),
}


class MapBiomasContractError(ValueError):
    """A tabela não pode virar indicador enquanto esta falha existir."""


@dataclass(frozen=True, slots=True)
class CoverageRecord:
    geocode: str
    biome: str
    state: str
    class_id: int
    year: int
    hectares: float


def _descendants(class_id: int) -> set[int]:
    children = {
        child for child, parent in CLASS_PARENT.items() if parent == class_id
    }
    found = set(children)
    for child in children:
        found |= _descendants(child)
    return found


def observed_leaves(class_ids: set[int]) -> set[int]:
    """Classes sem descendente também presente. Pai e filho não se somam."""

    return {
        class_id
        for class_id in class_ids
        if not (_descendants(class_id) & class_ids)
    }


def validate_parana_records(
    records: tuple[CoverageRecord, ...] | list[CoverageRecord],
    ibge_codes: set[str],
) -> dict[str, object]:
    """Confere o recorte PR. Não completa município nem classe ausente."""

    if CONTENT_SHA256 is None or not LOCAL_FILE:
        raise MapBiomasContractError(
            "Arquivo oficial ausente: validação de produção bloqueada."
        )
    return _validate_records(records, ibge_codes)


def validate_fixture_records(
    records: tuple[CoverageRecord, ...] | list[CoverageRecord],
    ibge_codes: set[str],
) -> dict[str, object]:
    """Mesmas regras, só para linhas sintéticas de teste."""

    return _validate_records(records, ibge_codes)


def _validate_records(
    records: tuple[CoverageRecord, ...] | list[CoverageRecord],
    ibge_codes: set[str],
) -> dict[str, object]:
    seen: set[tuple[str, str, int, int]] = set()
    present_by_slice: dict[tuple[str, str, int], set[int]] = {}
    geocodes: set[str] = set()
    biomes: set[str] = set()
    years: set[int] = set()
    for record in records:
        code = str(record.geocode).strip()
        biome = str(record.biome).strip()
        state = str(record.state).strip().upper()
        if state not in {"PR", "PARANÁ", "PARANA"}:
            raise MapBiomasContractError(f"Registro fora do Paraná: {state}")
        if len(code) != 7 or not code.startswith("41") or not code.isdigit():
            raise MapBiomasContractError(f"Código IBGE inválido: {code}")
        if not biome:
            raise MapBiomasContractError(f"Bioma vazio em {code}")
        if record.class_id not in CLASS_PARENT:
            raise MapBiomasContractError(f"Classe desconhecida: {record.class_id}")
        if record.year < YEAR_MIN or record.year > YEAR_MAX:
            raise MapBiomasContractError(f"Ano fora da Coleção 11: {record.year}")
        if not math.isfinite(record.hectares) or record.hectares < 0:
            raise MapBiomasContractError(f"Hectare inválido em {code}")
        key = (code, biome, record.class_id, record.year)
        if key in seen:
            raise MapBiomasContractError(f"Chave duplicada: {key}")
        seen.add(key)
        present_by_slice.setdefault((code, biome, record.year), set()).add(
            record.class_id
        )
        geocodes.add(code)
        biomes.add(biome)
        years.add(record.year)
    for slice_key, class_ids in present_by_slice.items():
        for class_id in class_ids:
            overlap = _descendants(class_id) & class_ids
            if overlap:
                raise MapBiomasContractError(
                    f"Pai e filho no mesmo recorte {slice_key}: "
                    f"{class_id} e {sorted(overlap)}"
                )
    missing = sorted(ibge_codes - geocodes)
    extra = sorted(geocodes - ibge_codes)
    if missing or extra:
        raise MapBiomasContractError(
            f"Códigos divergentes da malha: faltam {missing[:5]}, "
            f"sobram {extra[:5]}"
        )
    return {
        "geocode_count": len(geocodes),
        "biomes": tuple(sorted(biomes)),
        "years": tuple(sorted(years)),
        "record_count": len(records),
        "unit": UNIT,
    }


def composition_percent(
    records: tuple[CoverageRecord, ...] | list[CoverageRecord],
) -> dict[int, float] | None:
    """Percentual sobre a soma das folhas, em hectares. Denominador zero fica vazio."""

    class_ids = {record.class_id for record in records}
    for class_id in class_ids:
        overlap = _descendants(class_id) & class_ids
        if overlap:
            raise MapBiomasContractError(
                f"Percentual recusado: classe {class_id} convive com {sorted(overlap)}"
            )
    leaves = observed_leaves(class_ids)
    totals: dict[int, float] = {}
    for record in records:
        if record.class_id not in leaves:
            continue
        totals[record.class_id] = totals.get(record.class_id, 0.0) + record.hectares
    denominator = sum(totals.values())
    if denominator <= 0:
        return None
    return {
        class_id: (hectares / denominator) * 100.0
        for class_id, hectares in totals.items()
    }


def area_difference_km2(
    mapped_hectares: float,
    ibge_area_km2: float,
) -> dict[str, float]:
    """Diferença entre a área mapeada e AREA_KM2. Não reescala nenhum dos lados."""

    mapped_km2 = mapped_hectares / 100.0
    delta = mapped_km2 - ibge_area_km2
    relative = None if ibge_area_km2 == 0 else delta / ibge_area_km2
    return {
        "mapped_km2": mapped_km2,
        "ibge_area_km2": ibge_area_km2,
        "delta_km2": delta,
        "relative_delta": relative if relative is not None else math.nan,
    }
