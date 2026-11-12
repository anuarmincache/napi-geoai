"""Worker PyQGIS: join espacial SIGA → municípios IBGE (alta fidelidade).

Preferir QGIS MCP execute_code neste host, ou:
  python-qgis-ltr.bat scripts/_qgis_siga_join_worker.py
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CSV = REPO / "data" / "raw" / "aneel" / "siga-empreendimentos-geracao.csv"
ZIP = REPO / "data" / "raw" / "ibge" / "PR_Municipios_2025.zip"
OUT = REPO / "data" / "derived" / "siga_pr_qgis_join_report.json"
PANEL = REPO / "data" / "derived" / "siga_pr_energy_panel.json"


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _parse_num(text: str) -> float | None:
    text = (text or "").strip()
    if not text:
        return None
    try:
        value = float(text.replace(",", "."))
    except ValueError:
        return None
    return value if math.isfinite(value) else None


def main() -> int:
    import processing  # type: ignore[import-not-found]
    from osgeo import gdal, osr
    from qgis.core import (  # type: ignore[import-not-found]
        Qgis,
        QgsFeature,
        QgsField,
        QgsGeometry,
        QgsPointXY,
        QgsProject,
        QgsVectorLayer,
    )
    from qgis.PyQt.QtCore import QVariant  # type: ignore[import-not-found]

    if not CSV.is_file() or not ZIP.is_file():
        raise SystemExit("CSV SIGA ou ZIP municipal ausente")

    with zipfile.ZipFile(ZIP) as archive:
        shp = next(
            n
            for n in archive.namelist()
            if n.lower().endswith(".shp") and "municip" in n.lower()
        )
    mun_uri = f"/vsizip/{ZIP.as_posix()}/{shp}"
    mun = QgsVectorLayer(mun_uri, "pr_mun", "ogr")
    if not mun.isValid():
        raise SystemExit(mun.error().summary())

    # Camada de pontos em memória (CRS da malha).
    pts = QgsVectorLayer(f"Point?crs={mun.crs().authid()}", "siga_pts", "memory")
    prov = pts.dataProvider()
    prov.addAttributes(
        [
            QgsField("CodCEG", QVariant.String),
            QgsField("fase", QVariant.String),
            QgsField("tipo", QVariant.String),
            QgsField("fis_kw", QVariant.Double),
        ]
    )
    pts.updateFields()

    features: list[QgsFeature] = []
    rows_pr = 0
    operacao = 0
    skipped_coord = 0
    with CSV.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter=";")
        for row in reader:
            if (row.get("SigUFPrincipal") or "").strip().upper() != "PR":
                continue
            rows_pr += 1
            if (row.get("DscFaseUsina") or "").strip() != "Operação":
                continue
            operacao += 1
            lat = _parse_num(row.get("NumCoordNEmpreendimento") or "")
            lon = _parse_num(row.get("NumCoordEEmpreendimento") or "")
            if lat is None or lon is None:
                skipped_coord += 1
                continue
            if not (-35.0 <= lat <= 6.0 and -75.0 <= lon <= -28.0):
                skipped_coord += 1
                continue
            feat = QgsFeature(pts.fields())
            feat.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(lon, lat)))
            feat.setAttribute("CodCEG", (row.get("CodCEG") or "").strip())
            feat.setAttribute("fase", (row.get("DscFaseUsina") or "").strip())
            feat.setAttribute("tipo", (row.get("SigTipoGeracao") or "").strip())
            fis = _parse_num(row.get("MdaPotenciaFiscalizadaKw") or "")
            feat.setAttribute("fis_kw", fis if fis is not None else None)
            features.append(feat)
    prov.addFeatures(features)
    pts.updateExtents()
    QgsProject.instance().addMapLayer(pts, False)
    QgsProject.instance().addMapLayer(mun, False)

    joined = processing.run(
        "native:joinattributesbylocation",
        {
            "INPUT": pts,
            "PREDICATE": [0],  # intersects; within=5 in some builds — use within
            "JOIN": mun,
            "JOIN_FIELDS": ["CD_MUN", "NM_MUN"],
            "METHOD": 0,
            "DISCARD_NONMATCHING": False,
            "PREFIX": "",
            "OUTPUT": "memory:",
        },
    )
    # Prefer within if available via separate call
    try:
        joined_within = processing.run(
            "native:joinattributesbylocation",
            {
                "INPUT": pts,
                "PREDICATE": [5],  # within
                "JOIN": mun,
                "JOIN_FIELDS": ["CD_MUN", "NM_MUN"],
                "METHOD": 1,  # take first
                "DISCARD_NONMATCHING": False,
                "PREFIX": "",
                "OUTPUT": "memory:",
            },
        )
        out_layer = joined_within["OUTPUT"]
        predicate_used = "within(5)"
    except Exception:
        out_layer = joined["OUTPUT"]
        predicate_used = "intersects(0)-fallback"

    matched = 0
    unmatched = 0
    for feat in out_layer.getFeatures():
        code = feat["CD_MUN"]
        if code is None or str(code).strip() == "" or str(code) == "NULL":
            unmatched += 1
        else:
            matched += 1

    panel_totals = {}
    if PANEL.is_file():
        panel = json.loads(PANEL.read_text(encoding="utf-8"))
        panel_totals = panel.get("totals") or {}

    proj = (
        osr.GetPROJVersionMajor(),
        osr.GetPROJVersionMinor(),
        osr.GetPROJVersionMicro(),
    )
    report = {
        "product": "siga_pr_qgis_spatial_join",
        "generated_at": datetime.now(UTC).isoformat(),
        "engine": {
            "qgis_version": Qgis.QGIS_VERSION,
            "gdal_version": gdal.__version__,
            "proj_version": ".".join(map(str, proj)),
            "execution": "qgis_worker",
            "algorithms": ["native:joinattributesbylocation"],
            "predicate": predicate_used,
        },
        "input": {
            "siga_csv": "data/raw/aneel/siga-empreendimentos-geracao.csv",
            "siga_sha256": _sha(CSV),
            "municipios_zip": "data/raw/ibge/PR_Municipios_2025.zip",
            "municipios_sha256": _sha(ZIP),
            "municipios_crs": mun.crs().authid(),
            "points_crs": pts.crs().authid(),
        },
        "parameters": {
            "uf": "PR",
            "phase": "Operação",
            "discard_nonmatching": False,
            "note": (
                "Point-in-polygon sobre malha IBGE de alta fidelidade (ZIP). "
                "GeoJSON de apresentação Streamlit não é usado."
            ),
        },
        "results": {
            "rows_pr": rows_pr,
            "operacao": operacao,
            "points_created": len(features),
            "skipped_invalid_coords": skipped_coord,
            "matched": matched,
            "unmatched": unmatched,
            "panel_totals_geopandas": panel_totals,
        },
        "scope_note": (
            "SHA do CSV/ZIP vincula bytes. Join QGIS tem proveniência própria "
            "e complementa o join GeoPandas do prepare."
        ),
        "not_mmgd": True,
        "not_energy_mwh": True,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    OUT.write_text(payload, encoding="utf-8")
    print(f"wrote={OUT}")
    print(f"matched={matched} unmatched={unmatched} points={len(features)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
