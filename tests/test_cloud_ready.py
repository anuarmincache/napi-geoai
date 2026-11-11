"""Prontidão de hospedagem Streamlit Community Cloud (MVP 08)."""

from __future__ import annotations

from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


def test_entrypoint_home_exists() -> None:
    home = REPO / "app" / "Home.py"
    assert home.is_file()
    text = home.read_text(encoding="utf-8")
    assert "NAPI GeoAI" in text
    assert "configure_page" in text


def test_requirements_streamlit_editable_ui() -> None:
    req = REPO / "requirements-streamlit.txt"
    assert req.is_file()
    body = req.read_text(encoding="utf-8")
    assert "-e .[ui]" in body
    dep_lines = [
        ln.strip().lower()
        for ln in body.splitlines()
        if ln.strip() and not ln.strip().startswith("#")
    ]
    assert dep_lines == ["-e .[ui]"]
    assert not any("psycopg" in ln or "supabase" in ln for ln in dep_lines)


def test_python_version_pinned_312() -> None:
    version = (REPO / ".python-version").read_text(encoding="utf-8").strip()
    assert version.startswith("3.12")


def test_streamlit_config_present() -> None:
    cfg = REPO / ".streamlit" / "config.toml"
    assert cfg.is_file()
    text = cfg.read_text(encoding="utf-8")
    assert "primaryColor" in text
    assert "gatherUsageStats = false" in text
    assert "1f4e79" in text


def test_derived_parana_artifacts_tracked() -> None:
    derived = REPO / "data" / "derived"
    for name in (
        "parana_uf_2025.geojson",
        "parana_uf_2025.provenance.json",
        "parana_uf_2025.validation.json",
    ):
        path = derived / name
        assert path.is_file(), f"faltando {name} (necessário na Cloud)"
        assert path.stat().st_size > 0


def test_portal_loads_without_database_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    from geoai.portal import load_parana_layer

    bundle = load_parana_layer(REPO)
    assert bundle.validated_for_map is True
    assert bundle.available is True


def test_deploy_docs_exist() -> None:
    for rel in (
        "docs/MVP08_DEPLOY.md",
        "docs/SUPABASE_FUTURE.md",
        "docs/MVP08_RESULTADOS.md",
    ):
        path = REPO / rel
        assert path.is_file(), rel
        text = path.read_text(encoding="utf-8")
        assert "Supabase" in text or "supabase" in text.lower()
    deploy = (REPO / "docs" / "MVP08_DEPLOY.md").read_text(encoding="utf-8")
    assert "app/Home.py" in deploy
    assert "aprovação explícita" in deploy
    assert "Rollback" in deploy
