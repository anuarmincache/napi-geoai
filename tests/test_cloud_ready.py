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


def test_cloud_requirements_next_to_entrypoint() -> None:
    """Community Cloud detecta requirements.txt junto ao entrypoint."""

    req = REPO / "app" / "requirements.txt"
    assert req.is_file()
    body = req.read_text(encoding="utf-8")
    dep_lines = [
        ln.strip()
        for ln in body.splitlines()
        if ln.strip() and not ln.strip().startswith("#")
    ]
    assert dep_lines == ["-e ..[ui]"], dep_lines
    assert not any("psycopg" in ln.lower() for ln in dep_lines)
    assert not any("supabase" in ln.lower() for ln in dep_lines)
    # pyproject da raiz (não de app/) é o alvo do editável.
    assert (REPO / "pyproject.toml").is_file()
    assert not (REPO / "app" / "pyproject.toml").exists()


def test_local_streamlit_requirements_alias() -> None:
    req = REPO / "requirements-streamlit.txt"
    assert req.is_file()
    body = req.read_text(encoding="utf-8")
    assert "app/requirements.txt" in body
    dep_lines = [
        ln.strip().lower()
        for ln in body.splitlines()
        if ln.strip() and not ln.strip().startswith("#")
    ]
    assert dep_lines == ["-e .[ui]"]


def test_python_version_pinned_312() -> None:
    version = (REPO / ".python-version").read_text(encoding="utf-8").strip()
    assert version.startswith("3.12")


def test_streamlit_config_cors_xsrf() -> None:
    cfg = REPO / ".streamlit" / "config.toml"
    assert cfg.is_file()
    text = cfg.read_text(encoding="utf-8")
    assert "primaryColor" in text
    assert "gatherUsageStats = false" in text
    assert "1f4e79" in text
    assert "enableXsrfProtection = true" in text
    # enableCORS=false removido: default true é mais compatível com a Cloud.
    assert "enableCORS = false" not in text


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
    assert "app/requirements.txt" in deploy
    assert "aprovação explícita" in deploy
    assert "Rollback" in deploy


def test_editable_ui_extra_resolves_from_app_requirements() -> None:
    """Sanidade: pip interpreta -e ..[ui] a partir de app/requirements.txt."""

    import subprocess
    import sys

    req = REPO / "app" / "requirements.txt"
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--dry-run",
            "-r",
            str(req),
        ],
        cwd=REPO / "app",
        capture_output=True,
        text=True,
        check=False,
    )
    # dry-run pode falhar em pips antigos; aceitar sucesso ou mensagem clara.
    joined = (proc.stdout or "") + (proc.stderr or "")
    if proc.returncode != 0 and "dry-run" in joined.lower():
        pytest.skip("pip sem suporte a --dry-run neste ambiente")
    assert proc.returncode == 0, joined
    assert "napi-geoai" in joined.lower() or "napi_geoai" in joined.lower()
