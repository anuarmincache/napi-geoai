"""Integração opcional com QGIS/PyQGIS (local). Não usada no Streamlit Cloud."""

from geoai.qgis.discover import discover_qgis, qgis_available
from geoai.qgis.municipal_report import (
    EXPECTED_SOURCE_CRS,
    load_qgis_municipal_report,
    report_path,
    validate_qgis_report_contract,
)

__all__ = [
    "EXPECTED_SOURCE_CRS",
    "discover_qgis",
    "load_qgis_municipal_report",
    "qgis_available",
    "report_path",
    "validate_qgis_report_contract",
]
