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
