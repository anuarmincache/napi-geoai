"""Resolução de caminhos de artefatos versionados (sem framework de UI)."""

from __future__ import annotations

from pathlib import Path


def repo_root_from_here() -> Path:
    """Raiz do repositório a partir de ``geoai/portal``."""

    return Path(__file__).resolve().parents[2]


def derived_dir(repo_root: Path | None = None) -> Path:
    root = repo_root or repo_root_from_here()
    return root / "data" / "derived"


def parana_geojson_path(repo_root: Path | None = None) -> Path:
    return derived_dir(repo_root) / "parana_uf_2025.geojson"


def parana_provenance_path(repo_root: Path | None = None) -> Path:
    return derived_dir(repo_root) / "parana_uf_2025.provenance.json"


def parana_validation_path(repo_root: Path | None = None) -> Path:
    return derived_dir(repo_root) / "parana_uf_2025.validation.json"


def municipalities_geojson_path(repo_root: Path | None = None) -> Path:
    return derived_dir(repo_root) / "parana_municipios_2025_presentation.geojson"


def municipalities_provenance_path(repo_root: Path | None = None) -> Path:
    return derived_dir(repo_root) / "parana_municipios_2025.provenance.json"


def municipalities_validation_path(repo_root: Path | None = None) -> Path:
    return derived_dir(repo_root) / "parana_municipios_2025.validation.json"


def municipalities_qgis_report_path(repo_root: Path | None = None) -> Path:
    return derived_dir(repo_root) / "parana_municipios_2025_qgis_report.json"


def energy_panel_path(repo_root: Path | None = None) -> Path:
    return derived_dir(repo_root) / "siga_pr_energy_panel.json"


def energy_provenance_path(repo_root: Path | None = None) -> Path:
    return derived_dir(repo_root) / "siga_pr_energy.provenance.json"


def energy_quality_path(repo_root: Path | None = None) -> Path:
    return derived_dir(repo_root) / "siga_pr_energy.quality.json"


def energy_qgis_report_path(repo_root: Path | None = None) -> Path:
    return derived_dir(repo_root) / "siga_pr_qgis_join_report.json"


def population_panel_path(repo_root: Path | None = None) -> Path:
    return derived_dir(repo_root) / "ibge_pr_population_2026_panel.json"


def population_provenance_path(repo_root: Path | None = None) -> Path:
    return derived_dir(repo_root) / "ibge_pr_population_2026.provenance.json"


def population_quality_path(repo_root: Path | None = None) -> Path:
    return derived_dir(repo_root) / "ibge_pr_population_2026.quality.json"


def mmgd_panel_path(repo_root: Path | None = None) -> Path:
    return derived_dir(repo_root) / "mmgd_pr_panel.json"


def mmgd_provenance_path(repo_root: Path | None = None) -> Path:
    return derived_dir(repo_root) / "mmgd_pr.provenance.json"


def mmgd_quality_path(repo_root: Path | None = None) -> Path:
    return derived_dir(repo_root) / "mmgd_pr.quality.json"


def agro_panel_path(repo_root: Path | None = None) -> Path:
    return derived_dir(repo_root) / "agro_pr_panel.json"


def agro_provenance_path(repo_root: Path | None = None) -> Path:
    return derived_dir(repo_root) / "agro_pr.provenance.json"


def agro_quality_path(repo_root: Path | None = None) -> Path:
    return derived_dir(repo_root) / "agro_pr.quality.json"


def landcover_panel_path(repo_root: Path | None = None) -> Path:
    return derived_dir(repo_root) / "mapbiomas_pr_landcover_panel.json"


def landcover_provenance_path(repo_root: Path | None = None) -> Path:
    return derived_dir(repo_root) / "mapbiomas_pr_landcover.provenance.json"


def landcover_quality_path(repo_root: Path | None = None) -> Path:
    return derived_dir(repo_root) / "mapbiomas_pr_landcover.quality.json"
