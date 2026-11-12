"""Reconciliação espacial QGIS (referência) ↔ GeoPandas — fail-closed."""

from __future__ import annotations

from typing import Any

import geopandas as gpd


class SpatialReconciliationError(ValueError):
    """Divergência espacial não explicada entre QGIS e GeoPandas."""


def assignments_from_geopandas(
    joined: gpd.GeoDataFrame,
    *,
    phase: str | None = None,
) -> dict[str, str | None]:
    """Mapa CodCEG → CD_MUN (None se não associado)."""

    work = joined
    if phase is not None and "DscFaseUsina" in work.columns:
        work = work[work["DscFaseUsina"].astype(str) == phase]
    out: dict[str, str | None] = {}
    for _, row in work.iterrows():
        ceg = str(row.get("CodCEG") or "").strip()
        if not ceg:
            continue
        code = row.get("CD_MUN")
        if code is None or (isinstance(code, float) and code != code):
            out[ceg] = None
        else:
            text = str(code).strip()
            out[ceg] = text if text and text.upper() != "NULL" else None
    return out


def assignments_from_qgis_report(report: dict[str, Any]) -> dict[str, str | None]:
    """Lê ``assignments`` do relatório QGIS (CodCEG → CD_MUN|null)."""

    raw = report.get("assignments")
    if not isinstance(raw, list) or not raw:
        raise SpatialReconciliationError(
            "Relatório QGIS sem assignments CodCEG→CD_MUN "
            "(referência espacial ausente)."
        )
    out: dict[str, str | None] = {}
    for item in raw:
        if not isinstance(item, dict):
            continue
        ceg = str(item.get("CodCEG") or "").strip()
        if not ceg:
            continue
        code = item.get("CD_MUN")
        if code is None or str(code).strip() == "" or str(code).upper() == "NULL":
            out[ceg] = None
        else:
            out[ceg] = str(code).strip()
    if not out:
        raise SpatialReconciliationError(
            "assignments QGIS vazios após parse — fail-closed."
        )
    return out


def reconcile_spatial_assignments(
    *,
    qgis_assignments: dict[str, str | None],
    geopandas_assignments: dict[str, str | None],
    qgis_input: dict[str, Any],
    provenance: dict[str, Any],
    phase: str,
) -> dict[str, Any]:
    """Compara mapas CodCEG→CD_MUN e hashes de entrada.

    Retorna relatório. Levanta ``SpatialReconciliationError`` se houver
    divergência de município não explicada ou hash divergente.
    """

    problems: list[str] = []
    explained: list[dict[str, Any]] = []

    csv_sha_q = qgis_input.get("siga_sha256")
    csv_sha_p = provenance.get("content_sha256")
    zip_sha_q = qgis_input.get("municipios_sha256")
    zip_sha_p = provenance.get("municipios_zip_sha256")
    if not csv_sha_q or not csv_sha_p:
        problems.append("SHA do CSV SIGA ausente em QGIS ou proveniência")
    elif csv_sha_q != csv_sha_p:
        problems.append(
            f"SHA CSV QGIS ({csv_sha_q[:12]}…) != proveniência ({csv_sha_p[:12]}…)"
        )
    if not zip_sha_q or not zip_sha_p:
        problems.append("SHA do ZIP municipal ausente em QGIS ou proveniência")
    elif zip_sha_q != zip_sha_p:
        problems.append(
            f"SHA ZIP QGIS ({zip_sha_q[:12]}…) != proveniência ({zip_sha_p[:12]}…)"
        )

    q_keys = set(qgis_assignments)
    g_keys = set(geopandas_assignments)
    # GeoPandas pode ter todas as fases; restringimos ao universo QGIS (fase).
    only_gpd = sorted(g_keys - q_keys)
    only_qgis = sorted(q_keys - g_keys)
    for ceg in only_gpd:
        explained.append(
            {
                "CodCEG": ceg,
                "reason": "fora_do_universo_qgis_fase",
                "detail": (
                    f"Presente no GeoPandas mas ausente no join QGIS da fase "
                    f"{phase} (ex.: outra fase ou sem ponto no worker)."
                ),
                "geopandas_cd_mun": geopandas_assignments.get(ceg),
            }
        )
    if only_qgis:
        problems.append(
            f"{len(only_qgis)} CodCEG só no QGIS (ausentes no GeoPandas fase): "
            f"{only_qgis[:5]}"
        )

    matched_both = 0
    unmatched_both = 0
    diverge_cd_mun: list[dict[str, str | None]] = []
    for ceg in sorted(q_keys & g_keys):
        q_code = qgis_assignments[ceg]
        g_code = geopandas_assignments[ceg]
        if q_code is None and g_code is None:
            unmatched_both += 1
            continue
        if q_code is not None and g_code is not None and q_code == g_code:
            matched_both += 1
            continue
        if q_code != g_code:
            diverge_cd_mun.append(
                {
                    "CodCEG": ceg,
                    "qgis_cd_mun": q_code,
                    "geopandas_cd_mun": g_code,
                }
            )

    if diverge_cd_mun:
        problems.append(
            f"{len(diverge_cd_mun)} CodCEG com CD_MUN divergente QGIS≠GeoPandas "
            f"(ex.: {diverge_cd_mun[:3]})"
        )

    q_matched = sum(1 for v in qgis_assignments.values() if v is not None)
    q_unmatched = sum(1 for v in qgis_assignments.values() if v is None)
    g_matched = sum(
        1
        for ceg, v in geopandas_assignments.items()
        if ceg in q_keys and v is not None
    )
    g_unmatched = sum(
        1
        for ceg, v in geopandas_assignments.items()
        if ceg in q_keys and v is None
    )

    report = {
        "ok": not problems,
        "phase": phase,
        "spatial_reference": "qgis",
        "complementary_engine": "geopandas.sjoin/within",
        "qgis_n": len(qgis_assignments),
        "geopandas_n_in_qgis_universe": len(q_keys & g_keys),
        "agreement": {
            "same_cd_mun_matched": matched_both,
            "both_unmatched": unmatched_both,
            "cd_mun_divergences": len(diverge_cd_mun),
        },
        "counts": {
            "qgis_matched": q_matched,
            "qgis_unmatched": q_unmatched,
            "geopandas_matched_in_universe": g_matched,
            "geopandas_unmatched_in_universe": g_unmatched,
        },
        "hashes": {
            "siga_sha256_match": bool(
                csv_sha_q and csv_sha_p and csv_sha_q == csv_sha_p
            ),
            "municipios_sha256_match": bool(
                zip_sha_q and zip_sha_p and zip_sha_q == zip_sha_p
            ),
        },
        "explained_out_of_universe": explained[:50],
        "explained_out_of_universe_n": len(explained),
        "divergences_sample": diverge_cd_mun[:20],
        "problems": problems,
        "note": (
            "Agregação municipal usa CD_MUN do QGIS como referência. "
            "GeoPandas é cruzamento; divergência não explicada → fail-closed."
        ),
    }
    if problems:
        raise SpatialReconciliationError(
            "Reconciliação espacial falhou: " + "; ".join(problems)
        )
    return report


def apply_qgis_assignments_to_frame(
    joined: gpd.GeoDataFrame,
    qgis_assignments: dict[str, str | None],
    *,
    phase: str,
) -> gpd.GeoDataFrame:
    """Sobrescreve CD_MUN/match_status com a referência QGIS (fase filtrada)."""

    work = joined.copy()
    if "DscFaseUsina" in work.columns:
        in_phase = work["DscFaseUsina"].astype(str) == phase
        out_phase = work.loc[~in_phase].copy()
        work = work.loc[in_phase].copy()
    else:
        out_phase = work.iloc[0:0].copy()

    cd_list: list[str | None] = []
    status_list: list[str] = []
    for _, row in work.iterrows():
        ceg = str(row.get("CodCEG") or "").strip()
        if ceg not in qgis_assignments:
            # Sem ponto no worker QGIS → não associado (explicável).
            cd_list.append(None)
            status_list.append("missing_in_qgis_points")
            continue
        code = qgis_assignments[ceg]
        cd_list.append(code)
        status_list.append("matched" if code else "unmatched_geometry")

    work = work.copy()
    work["CD_MUN"] = cd_list
    work["match_status"] = status_list
    # NM_MUN do GeoPandas pode ficar desatualizado; agregador usa catálogo IBGE.
    if len(out_phase):
        import pandas as pd

        return gpd.GeoDataFrame(
            pd.concat([work, out_phase], ignore_index=True),
            crs=joined.crs,
        )
    return work
