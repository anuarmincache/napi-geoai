"""Worker PyQGIS: join espacial SIGA → municípios IBGE (referência espacial).

Exporta assignments CodCEG→CD_MUN para reconciliação fail-closed.

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


def _ensure_qgis_processing():
    """Inicializa QgsApplication + Processing se não estivermos no Desktop/MCP."""

    try:
        import processing  # type: ignore[import-not-found]

        return processing, None
    except ImportError:
        pass

    import os

    from qgis.core import QgsApplication  # type: ignore[import-not-found]

    prefix = os.environ.get("QGIS_PREFIX_PATH")
    if not prefix:
        # python-qgis-ltr.bat normalmente define; fallback Desktop LTR.
        candidate = Path(r"C:\Program Files\QGIS 3.44.15")
        prefix = str(candidate) if candidate.is_dir() else ""
    if prefix:
        QgsApplication.setPrefixPath(prefix, True)
    qgs = QgsApplication([], False)
    qgs.initQgis()
    plugin_paths = [
        Path(QgsApplication.pkgDataPath()) / "python" / "plugins",
        Path(QgsApplication.qgisSettingsDirPath()) / "python" / "plugins",
    ]
    for plugin_path in plugin_paths:
        text = str(plugin_path)
        if text and text not in sys.path:
            sys.path.append(text)
    # Este import tem de ficar depois do sys.path do plugin. Não reordenar.
    import processing  # type: ignore[import-not-found]  # noqa: I001
    from processing.core.Processing import Processing  # type: ignore[import-not-found]

    Processing.initialize()
    return processing, qgs


def main() -> int:
    processing, qgs_app = _ensure_qgis_processing()
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
    operacao_no_point: list[str] = []
    with CSV.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter=";")
        for row in reader:
            if (row.get("SigUFPrincipal") or "").strip().upper() != "PR":
                continue
            rows_pr += 1
            if (row.get("DscFaseUsina") or "").strip() != "Operação":
                continue
            operacao += 1
            ceg = (row.get("CodCEG") or "").strip()
            lat = _parse_num(row.get("NumCoordNEmpreendimento") or "")
            lon = _parse_num(row.get("NumCoordEEmpreendimento") or "")
            if lat is None or lon is None:
                skipped_coord += 1
                if ceg:
                    operacao_no_point.append(ceg)
                continue
            if not (-35.0 <= lat <= 6.0 and -75.0 <= lon <= -28.0):
                skipped_coord += 1
                if ceg:
                    operacao_no_point.append(ceg)
                continue
            feat = QgsFeature(pts.fields())
            feat.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(lon, lat)))
            feat.setAttribute("CodCEG", ceg)
            feat.setAttribute("fase", (row.get("DscFaseUsina") or "").strip())
            feat.setAttribute("tipo", (row.get("SigTipoGeracao") or "").strip())
            fis = _parse_num(row.get("MdaPotenciaFiscalizadaKw") or "")
            feat.setAttribute("fis_kw", fis if fis is not None else None)
            features.append(feat)
    prov.addFeatures(features)
    pts.updateExtents()
    QgsProject.instance().addMapLayer(pts, False)
    QgsProject.instance().addMapLayer(mun, False)

    joined_within = processing.run(
        "native:joinattributesbylocation",
        {
            "INPUT": pts,
            "PREDICATE": [5],  # within
            "JOIN": mun,
            "JOIN_FIELDS": ["CD_MUN", "NM_MUN"],
            "METHOD": 1,
            "DISCARD_NONMATCHING": False,
            "PREFIX": "",
            "OUTPUT": "memory:",
        },
    )
    out_layer = joined_within["OUTPUT"]
    predicate_used = "within(5)"

    assignments: list[dict[str, str | None]] = []
    matched = 0
    unmatched = 0
    for feat in out_layer.getFeatures():
        ceg = str(feat["CodCEG"] or "").strip()
        code = feat["CD_MUN"]
        if code is None or str(code).strip() == "" or str(code) == "NULL":
            unmatched += 1
            assignments.append({"CodCEG": ceg, "CD_MUN": None, "matched": False})
        else:
            matched += 1
            assignments.append(
                {
                    "CodCEG": ceg,
                    "CD_MUN": str(code).strip(),
                    "NM_MUN": str(feat["NM_MUN"] or "").strip(),
                    "matched": True,
                }
            )
    # Usinas Operação sem ponto válido: assignment explícito None
    for ceg in operacao_no_point:
        assignments.append(
            {
                "CodCEG": ceg,
                "CD_MUN": None,
                "matched": False,
                "reason": "missing_or_invalid_coordinates",
            }
        )

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
                "Referência espacial oficial do MVP 10. "
                "GeoPandas é cruzamento complementar com fail-closed."
            ),
        },
        "results": {
            "rows_pr": rows_pr,
            "operacao": operacao,
            "points_created": len(features),
            "skipped_invalid_coords": skipped_coord,
            "matched": matched,
            "unmatched": unmatched,
            "assignments_n": len(assignments),
        },
        "assignments": assignments,
        "scope_note": (
            "SHA do CSV/ZIP vincula bytes. assignments CodCEG→CD_MUN são a "
            "referência espacial; GeoPandas deve reconciliar por CodCEG."
        ),
        "not_mmgd": True,
        "not_energy_mwh": True,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    OUT.write_text(payload, encoding="utf-8")
    print(f"wrote={OUT}")
    print(
        f"matched={matched} unmatched={unmatched} "
        f"points={len(features)} assignments={len(assignments)}"
    )
    if qgs_app is not None:
        qgs_app.exitQgis()
    return 0


if __name__ == "__main__":
    sys.exit(main())
