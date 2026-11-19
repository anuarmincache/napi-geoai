"""Otimização do ciclo NDVI: escolher passagens sem desperdiçar download.

Funções puras sobre o que o catálogo STAC devolve. Nada aqui baixa banda.

Três decisões, nesta ordem:

1. **Triagem por nuvem.** Uma passagem só é candidata se a nuvem das tiles
   escolhidas, ponderada pela parcela do município que cada tile cobre,
   ficar no máximo em ``max_cloud``. A nuvem do item é da tile inteira e não
   substitui a fração válida no município: é triagem, não aceite.
2. **Reuso de cena.** Entre as candidatas de um município, vence a que
   acrescenta menos bytes ao que já foi escolhido para os outros. Empate:
   menor nuvem ponderada, depois a mais recente.
3. **SCL primeiro.** A banda SCL (20 m) pesa uma fração de B04 e B08. Com
   ela se mede, por município, o teto da fração válida. Município reprovado
   nesse teto dispensa B04 e B08. O plano separa os dois estágios.

A regra temporal do piloto não muda: uma única passagem por município.
"""

from __future__ import annotations

from typing import Any

DEFAULT_MAX_CLOUD = 40.0
HEAVY_BANDS = ("B04_10m", "B08_10m")
MASK_BAND = "SCL_20m"


def weighted_cloud(tiles: list[dict[str, Any]]) -> float | None:
    """Nuvem do item ponderada pela cobertura do município em cada tile.

    Devolve ``None`` se alguma tile não declara nuvem ou cobertura: sem o
    dado, a passagem não é promovida nem descartada por suposição.
    """

    total = 0.0
    weight = 0.0
    for tile in tiles:
        cloud = tile.get("eo_cloud_cover")
        coverage = tile.get("aoi_coverage")
        if cloud is None or coverage is None or float(coverage) <= 0:
            return None
        total += float(cloud) * float(coverage)
        weight += float(coverage)
    return total / weight if weight > 0 else None


def _tile_bytes(tile: dict[str, Any], bands: tuple[str, ...]) -> int | None:
    sizes = [(tile.get("band_bytes") or {}).get(band) for band in bands]
    if any(size is None for size in sizes):
        return None
    return int(sum(sizes))


def _new_bytes(candidate: dict[str, Any], chosen: set[str]) -> int:
    total = 0
    for tile in candidate["tiles"]:
        if str(tile["product_id"]) in chosen:
            continue
        size = _tile_bytes(tile, (*HEAVY_BANDS, MASK_BAND))
        # tamanho desconhecido pesa como muito caro, nunca como zero
        total += size if size is not None else 10**12
    return total


def optimize_cycle(
    records: dict[str, dict[str, Any]],
    *,
    max_cloud: float = DEFAULT_MAX_CLOUD,
) -> dict[str, dict[str, Any]]:
    """Escolhe uma passagem por município. Devolve a seleção por código."""

    eligible: dict[str, list[dict[str, Any]]] = {}
    for code, record in records.items():
        options = []
        for candidate in record.get("candidates") or []:
            cloud = weighted_cloud(candidate["tiles"])
            if cloud is None or cloud > max_cloud:
                continue
            options.append({**candidate, "weighted_cloud": round(cloud, 2)})
        eligible[code] = options

    chosen_products: set[str] = set()
    selection: dict[str, dict[str, Any]] = {}
    # menos opções primeiro: quem tem pouca escolha fixa as cenas compartilhadas
    order = sorted(records, key=lambda c: (len(eligible[c]), c))
    for code in order:
        options = eligible[code]
        if not options:
            candidates = records[code].get("candidates") or []
            selection[code] = {
                "selected_acquisition": None,
                "reason": "sem_passagem_cobrindo"
                if not candidates
                else "todas_acima_do_limite_de_nuvem",
                "candidates_covering": len(candidates),
                "tiles": [],
            }
            continue
        best = min(
            options,
            key=lambda c: (
                _new_bytes(c, chosen_products),
                c["weighted_cloud"],
                # mais recente primeiro
                tuple(-ord(ch) for ch in str(c["sensing_time_utc"])),
            ),
        )
        chosen_products.update(str(t["product_id"]) for t in best["tiles"])
        selection[code] = {
            "selected_acquisition": best["acquisition_id"],
            "sensing_time_utc": best["sensing_time_utc"],
            "weighted_cloud": best["weighted_cloud"],
            "mosaic_required": len(best["tiles"]) > 1,
            "reason": "selecionada",
            "candidates_covering": len(records[code].get("candidates") or []),
            "candidates_eligible": len(options),
            "tiles": best["tiles"],
        }
    return selection


def summarize_selection(
    selection: dict[str, dict[str, Any]], names: dict[str, str]
) -> dict[str, Any]:
    """Cenas distintas e bytes por estágio. Cada cena conta uma vez."""

    products: dict[str, dict[str, Any]] = {}
    for item in selection.values():
        for tile in item["tiles"]:
            products.setdefault(str(tile["product_id"]), tile)
    mask_sizes = [_tile_bytes(t, (MASK_BAND,)) for t in products.values()]
    heavy_sizes = [_tile_bytes(t, HEAVY_BANDS) for t in products.values()]
    unknown = sum(s is None for s in (*mask_sizes, *heavy_sizes))
    mask_bytes = sum(s for s in mask_sizes if s is not None)
    heavy_bytes = sum(s for s in heavy_sizes if s is not None)
    clouds = [
        float(t["eo_cloud_cover"])
        for t in products.values()
        if t.get("eo_cloud_cover") is not None
    ]
    without = sorted(
        names.get(code, code)
        for code, item in selection.items()
        if not item["selected_acquisition"]
    )
    return {
        "targets": len(selection),
        "targets_with_pass": len(selection) - len(without),
        "targets_without_pass": without,
        "targets_needing_mosaic": sum(
            1 for item in selection.values() if item.get("mosaic_required")
        ),
        "distinct_products": len(products),
        "distinct_mgrs_tiles": sorted({t["mgrs_tile"] for t in products.values()}),
        "distinct_acquisitions": sorted(
            {
                str(item["selected_acquisition"])
                for item in selection.values()
                if item["selected_acquisition"]
            }
        ),
        "scenes_with_cloud_above_50": sum(c > 50 for c in clouds),
        "stage1_mask_bytes": int(mask_bytes),
        "stage2_bands_bytes_max": int(heavy_bytes),
        "official_bytes_known": int(mask_bytes + heavy_bytes),
        "band_files": 3 * len(products),
        "band_files_without_official_size": int(unknown),
        "bytes_note_pt": (
            "Estágio 1: só a banda SCL das cenas distintas, para medir o teto "
            "da fração válida por município. Estágio 2: B04 e B08, no máximo "
            "o valor indicado; cenas que só servem municípios reprovados no "
            "estágio 1 não são baixadas. Cada cena conta uma vez."
        ),
    }
