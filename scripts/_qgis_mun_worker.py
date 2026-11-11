"""Worker PyQGIS: validade + área elipsoidal independente (MVP 09).

Executar DENTRO do ambiente QGIS, por exemplo:
  - QGIS MCP execute_code (preferencial neste host), ou
  - python-qgis-ltr.bat scripts/_qgis_mun_worker.py

Não importar este módulo no Streamlit Cloud.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
GEOJSON = REPO / "data" / "derived" / "parana_municipios_2025_presentation.geojson"
ZIP = REPO / "data" / "raw" / "ibge" / "PR_Municipios_2025.zip"
OUT = REPO / "data" / "derived" / "parana_municipios_2025_qgis_report.json"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    import processing  # type: ignore[import-not-found]
    from osgeo import gdal, osr
    from qgis.core import (  # type: ignore[import-not-found]
        Qgis,
        QgsDistanceArea,
        QgsProject,
        QgsVectorLayer,
    )

    if ZIP.is_file():
        with zipfile.ZipFile(ZIP) as archive:
            shp = next(
                n
                for n in archive.namelist()
                if n.lower().endswith(".shp") and "municip" in n.lower()
            )
        src_path = f"/vsizip/{ZIP.as_posix()}/{shp}"
        input_kind = "zip_shapefile"
        input_path = ZIP
    else:
        src_path = GEOJSON.as_posix()
        input_kind = "presentation_geojson"
        input_path = GEOJSON

    layer = QgsVectorLayer(src_path, "pr_mun", "ogr")
    if not layer.isValid():
        raise SystemExit(f"camada inválida: {layer.error().summary()}")

    crs = layer.crs()
    validity = processing.run(
        "native:checkvalidity",
        {
            "INPUT_LAYER": layer,
            "METHOD": 2,
            "IGNORE_RING_SELF_INTERSECTION": False,
            "VALID_OUTPUT": "memory:",
            "INVALID_OUTPUT": "memory:",
            "ERROR_OUTPUT": "memory:",
        },
    )
    valid_count = int(validity.get("VALID_COUNT", 0))
    invalid_count = int(validity.get("INVALID_COUNT", 0))
    error_count = int(validity.get("ERROR_COUNT", 0))

    distance = QgsDistanceArea()
    distance.setSourceCrs(crs, QgsProject.instance().transformContext())
    distance.setEllipsoid("EPSG:7019")

    rows: list[dict[str, object]] = []
    prefix_ok = True
    area_attr_ok = True
    for feat in layer.getFeatures():
        code = str(feat["CD_MUN"]).strip()
        name = str(feat["NM_MUN"]).strip()
        area_ibge = float(feat["AREA_KM2"])
        if not code.startswith("41"):
            prefix_ok = False
        if not (math.isfinite(area_ibge) and area_ibge > 0):
            area_attr_ok = False
        area_km2_qgis = distance.measureArea(feat.geometry()) / 1_000_000.0
        rows.append(
            {
                "CD_MUN": code,
                "NM_MUN": name,
                "AREA_KM2_IBGE": area_ibge,
                "AREA_KM2_QGIS_ELLIPSOIDAL": round(area_km2_qgis, 6),
                "ABS_DIFF_KM2": round(abs(area_km2_qgis - area_ibge), 6),
                "REL_DIFF": round(abs(area_km2_qgis - area_ibge) / area_ibge, 8)
                if area_ibge
                else None,
            }
        )

    rows.sort(key=lambda item: item["REL_DIFF"] or 0, reverse=True)
    rel_vals = [float(r["REL_DIFF"]) for r in rows if r["REL_DIFF"] is not None]
    proj = (
        osr.GetPROJVersionMajor(),
        osr.GetPROJVersionMinor(),
        osr.GetPROJVersionMicro(),
    )
    report = {
        "product": "parana_municipios_qgis_validation",
        "generated_at": datetime.now(UTC).isoformat(),
        "engine": {
            "qgis_version": Qgis.QGIS_VERSION,
            "gdal_version": gdal.__version__,
            "proj_version": ".".join(map(str, proj)),
            "execution": "python-qgis-worker",
            "algorithms": [
                "native:checkvalidity",
                "QgsDistanceArea.measureArea",
            ],
        },
        "input": {
            "kind": input_kind,
            "path": input_path.relative_to(REPO).as_posix()
            if input_path.is_relative_to(REPO)
            else input_path.name,
            "sha256": _sha256(input_path),
            "bytes": input_path.stat().st_size,
            "feature_count": int(layer.featureCount()),
            "crs_authid": crs.authid(),
        },
        "parameters": {
            "checkvalidity_method": 2,
            "ignore_ring_self_intersection": False,
            "area_method": "QgsDistanceArea ellipsoidal on source CRS",
            "ellipsoid": "EPSG:7019 (GRS80 / SIRGAS 2000)",
            "area_units": "km2 (m2/1e6)",
            "note_area": (
                "Medição elipsoidal independente. AREA_KM2 IBGE permanece o "
                "atributo oficial; não recalcular área a partir do GeoJSON "
                "simplificado de apresentação."
            ),
        },
        "results": {
            "valid_count": valid_count,
            "invalid_count": invalid_count,
            "error_count": error_count,
            "cd_mun_prefix_41_ok": prefix_ok,
            "area_km2_finite_positive_ok": area_attr_ok,
            "unique_cd_mun": len({str(r["CD_MUN"]) for r in rows}),
            "area_rel_diff_max": max(rel_vals) if rel_vals else None,
            "area_rel_diff_median": sorted(rel_vals)[len(rel_vals) // 2]
            if rel_vals
            else None,
            "worst_rel_diff_top5": rows[:5],
        },
        "scope_note": (
            "SHA-256 comprova vínculo com bytes do input processado. "
            "Validação geométrica/QGIS tem escopo e proveniência próprios e "
            "não substitui o SHA do artefato de apresentação Streamlit."
        ),
        "not_a_solar_suitability_map": True,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    OUT.write_text(payload, encoding="utf-8")
    print(f"wrote={OUT}")
    print(f"valid={valid_count} invalid={invalid_count}")
    return 0


if __name__ == "__main__":
    # Ensure repo root importability is not required; PyQGIS provides runtime.
    sys.exit(main())
