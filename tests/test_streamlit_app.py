"""Smoke automatizado da app Streamlit (MVP 07)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

pytest.importorskip("streamlit")

from streamlit.testing.v1 import AppTest  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
HOME = REPO / "app" / "Home.py"
PAGES = (
    REPO / "app" / "pages" / "1_Dominios.py",
    REPO / "app" / "pages" / "2_Mapa_Parana.py",
    REPO / "app" / "pages" / "3_Fontes_e_qualidade.py",
    REPO / "app" / "pages" / "4_Sobre_e_deploy.py",
    REPO / "app" / "pages" / "5_Explorador_Territorial.py",
    REPO / "app" / "pages" / "6_Energia_SIGA.py",
)


@pytest.fixture()
def _streamlit_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    """Garante imports ``_bootstrap`` e ``geoai`` como no ``streamlit run``."""

    monkeypatch.chdir(REPO)
    app_dir = str(REPO / "app")
    if app_dir not in sys.path:
        sys.path.insert(0, app_dir)
    repo = str(REPO)
    if repo not in sys.path:
        sys.path.insert(0, repo)


@pytest.mark.parametrize("script", [HOME, *PAGES], ids=lambda p: p.name)
def test_streamlit_script_smoke(
    script: Path,
    _streamlit_paths: None,
) -> None:
    """Executa cada script Streamlit e falha se houver exception de runtime."""

    assert script.is_file()
    # Caminho absoluto: AppTest resolve relativos contra tests/.
    at = AppTest.from_file(str(script), default_timeout=60)
    at.run()
    assert not at.exception, f"{script.name} levantou: {at.exception}"


def test_home_shows_napi_branding(_streamlit_paths: None) -> None:
    at = AppTest.from_file(str(HOME), default_timeout=60)
    at.run()
    assert not at.exception
    blobs = [str(x.value) for x in at.markdown]
    joined = "\n".join(blobs)
    assert "NAPI GeoAI" in joined or any(
        "NAPI" in str(getattr(t, "value", t)) for t in at.title
    )


def test_explorer_search_ux_no_false_fallback(_streamlit_paths: None) -> None:
    """Busca sem resultado não reinstaura silenciosamente os 399."""

    explorer = REPO / "app" / "pages" / "5_Explorador_Territorial.py"
    at = AppTest.from_file(str(explorer), default_timeout=90)
    at.run()
    assert not at.exception, at.exception

    # Campo de busca (primeiro text_input da página)
    assert at.text_input
    at.text_input[0].set_value("cidade-inexistente-xyz")
    at.run()
    assert not at.exception, at.exception
    warning_text = "\n".join(str(w.value) for w in at.warning)
    assert "Nenhum município encontrado" in warning_text

    # Contagem visível não deve alegar 399 resultados para essa consulta
    md = "\n".join(str(m.value) for m in at.markdown)
    assert "0 de 399" in md.replace("**", "")


def test_explorer_starts_without_forced_city(_streamlit_paths: None) -> None:
    explorer = REPO / "app" / "pages" / "5_Explorador_Territorial.py"
    at = AppTest.from_file(str(explorer), default_timeout=90)
    at.run()
    assert not at.exception, at.exception
    info_blobs = "\n".join(str(x.value) for x in at.info)
    assert "Mapa geral" in info_blobs or "399" in info_blobs
