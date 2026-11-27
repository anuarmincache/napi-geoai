"""Smoke automatizado da app Streamlit (MVP 07)."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

pytest.importorskip("streamlit")

from geoai.portal.formatos import numero_br as br_num  # noqa: E402
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
    REPO / "app" / "pages" / "7_Ficha_Municipal.py",
    REPO / "app" / "pages" / "8_Energia_MMGD.py",
    REPO / "app" / "pages" / "9_Meio_Ambiente.py",
    REPO / "app" / "pages" / "10_Agricultura.py",
    REPO / "app" / "pages" / "11_Ferramentas.py",
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


def test_ficha_municipal_shows_population_semantics(_streamlit_paths: None) -> None:
    """Ficha exibe estimativa 2026 e deixa claro que não é Censo/MMGD/MWh."""

    from geoai.population.panel import load_population_panel_bundle

    if not load_population_panel_bundle(REPO).available:
        pytest.skip("painel populacional ausente")

    page = REPO / "app" / "pages" / "7_Ficha_Municipal.py"
    at = AppTest.from_file(str(page), default_timeout=120)
    at.run()
    assert not at.exception, at.exception
    blobs = "\n".join(
        [
            *(str(x.value) for x in at.markdown),
            *(str(x.value) for x in at.caption),
            *(str(x.value) for x in at.info),
            *(str(x.value) for x in at.warning),
            *(str(m.label) for m in at.metric),
        ]
    )
    assert "2026" in blobs
    assert "Censo" in blobs or "censo" in blobs.lower()
    assert any("População estimada" in str(m.label) for m in at.metric)
    assert "399" in blobs
    # Semântica energética: status explícito; zero vinculado ≠ absoluto
    assert any("Status energia SIGA" in str(m.label) for m in at.metric)
    joined_warn = "\n".join(str(w.value) for w in at.warning).lower()
    joined_cap = "\n".join(str(c.value) for c in at.caption).lower()
    assert (
        "não associados" in joined_warn
        or "associ" in joined_cap
        or "vinculado" in joined_cap
        or "vinculado" in joined_warn
    )


def test_energy_kpis_follow_technology_filter(_streamlit_paths: None) -> None:
    """KPIs superiores recalculam no escopo da tecnologia (não ficam gerais)."""

    from geoai.portal.energy_panel import energy_scope_totals, load_energy_panel_bundle

    bundle = load_energy_panel_bundle(REPO)
    if not bundle.available:
        pytest.skip(bundle.missing_reason_pt or "painel energético ausente")

    page = REPO / "app" / "pages" / "6_Energia_SIGA.py"
    at = AppTest.from_file(str(page), default_timeout=120)
    at.run()
    assert not at.exception, at.exception

    all_scope = energy_scope_totals(bundle, tipo=None)
    metric_labels = [str(m.label) for m in at.metric]
    # Sem filtro, o recorte aparece na legenda abaixo dos indicadores.
    legenda_inicial = "\n".join(str(c.value) for c in at.caption)
    assert "todas as tecnologias" in legenda_inicial
    assert any(lab.startswith("Usinas em operação") for lab in metric_labels)
    assert any("Municípios no Paraná" in lab for lab in metric_labels)
    values_all = {str(m.label): str(m.value) for m in at.metric}
    assert values_all[
        next(lab for lab in metric_labels if lab.startswith("Usinas em operação"))
    ] == br_num(all_scope["n_empreendimentos_fase"])

    # Primeiro selectbox = tecnologia
    assert at.selectbox
    tech_box = at.selectbox[0]
    options = list(tech_box.options)
    assert "(todas)" in options
    # O filtro mostra o nome junto da sigla, para ser escolhível por quem não
    # conhece o código da ANEEL.
    assert any("UFV" in o and "fotovoltaica" in o.lower() for o in options)
    tech_box.set_value("UFV")
    at.run()
    assert not at.exception, at.exception

    ufv_scope = energy_scope_totals(bundle, tipo="UFV")
    labels_ufv = [str(m.label) for m in at.metric]
    values_ufv = {str(m.label): str(m.value) for m in at.metric}
    # O recorte em uso fica na legenda, não repetido nos quatro rótulos, que
    # ficavam longos demais e apareciam cortados no cartão.
    assert not any("escopo" in lab for lab in labels_ufv)
    usinas = next(lab for lab in labels_ufv if lab.startswith("Usinas em operação"))
    assert values_ufv[usinas] == br_num(ufv_scope["n_empreendimentos_fase"])
    assert ufv_scope["n_empreendimentos_fase"] != all_scope["n_empreendimentos_fase"]
    mun_label = next(
        lab for lab in labels_ufv if lab.startswith("Municípios com usinas")
    )
    assert values_ufv[mun_label] == br_num(ufv_scope["n_municipios_com_usinas"])
    fixed = next(lab for lab in labels_ufv if "Municípios no Paraná" in lab)
    assert "399" in values_ufv[fixed]
    captions = "\n".join(str(c.value) for c in at.caption)
    # A legenda nomeia a tecnologia filtrada sem expor o código interno.
    assert "solares fotovoltaicas" in captions
    assert "tipo:" not in captions
    # A página precisa dizer quantas usinas ficam fora do mapa, em palavras.
    avisos = "\n".join(str(w.value) for w in at.warning).lower()
    assert "não aparecem no mapa" in avisos
    assert "coordenada" in avisos


def test_home_lists_energy_page(_streamlit_paths: None) -> None:
    at = AppTest.from_file(str(HOME), default_timeout=60)
    at.run()
    assert not at.exception, at.exception
    info = "\n".join(str(item.value) for item in at.info)
    assert "Energia" in info
    assert "MMGD" in info
    assert "Meio Ambiente" in info
    assert "Agricultura" in info


def test_mmgd_page_kpis_and_technology_filter(_streamlit_paths: None) -> None:
    from geoai.portal.mmgd_panel import load_mmgd_panel_bundle, mmgd_scope_totals

    if not load_mmgd_panel_bundle(REPO).available:
        pytest.skip("painel MMGD ausente")

    page = REPO / "app" / "pages" / "8_Energia_MMGD.py"
    at = AppTest.from_file(str(page), default_timeout=180)
    at.run()
    assert not at.exception, at.exception
    labels = [str(m.label) for m in at.metric]
    assert any("Empreendimentos" in lab for lab in labels)
    # Verifica a grandeza e a unidade, não a redação: "MW instalada" era o
    # rótulo antigo e prendia o teste a uma frase que a tela já não usa.
    assert any(
        "Potência instalada" in lab and "MW" in lab for lab in labels
    ), labels
    warnings = "\n".join(str(w.value) for w in at.warning)
    assert "rejeitados" in warnings.lower() or "MMGD" in warnings
    captions = "\n".join(str(c.value) for c in at.caption)
    assert "ODbL" in captions or "ANEEL" in captions or "11/2026" in captions

    all_scope = mmgd_scope_totals(load_mmgd_panel_bundle(REPO))
    emp_label = next(lab for lab in labels if lab.startswith("Empreendimentos"))
    values = {str(m.label): str(m.value) for m in at.metric}
    # formatação pt com ponto de milhar
    expected = f"{all_scope['n_empreendimentos']:,}".replace(",", ".")
    assert values[emp_label] == expected

    # Primeiro selectbox = tecnologia
    assert at.selectbox
    tech = at.selectbox[0]
    opcoes = list(tech.options)
    assert "(todas)" in opcoes
    assert any("UFV" in o and "fotovoltaica" in o.lower() for o in opcoes)
    tech.set_value("UFV")
    at.run()
    assert not at.exception, at.exception
    labels_ufv = [str(m.label) for m in at.metric]
    assert any("UFV" in lab or "tipo:UFV" in lab for lab in labels_ufv)
    ufv_scope = mmgd_scope_totals(load_mmgd_panel_bundle(REPO), tipo="UFV")
    values_ufv = {str(m.label): str(m.value) for m in at.metric}
    emp_ufv = next(lab for lab in labels_ufv if lab.startswith("Empreendimentos"))
    expected_ufv = f"{ufv_scope['n_empreendimentos']:,}".replace(",", ".")
    assert values_ufv[emp_ufv] == expected_ufv
    mw_lab = next(
        lab for lab in labels_ufv if lab.startswith("Potência instalada")
    )
    assert "n/d" in values_ufv[mw_lab].lower()


def test_energy_page_searches_any_municipality(_streamlit_paths: None) -> None:
    from geoai.portal.energy_panel import load_energy_panel_bundle

    if not load_energy_panel_bundle(REPO).available:
        pytest.skip("painel energético ausente")

    page = REPO / "app" / "pages" / "6_Energia_SIGA.py"
    at = AppTest.from_file(str(page), default_timeout=120)
    at.run()
    assert not at.exception, at.exception
    assert at.text_input
    labels = [str(metric.label) for metric in at.metric]
    assert "Usinas associadas" in labels
    assert "Potência fiscalizada (MW)" in labels
    assert "Potência outorgada (MW)" in labels
    warnings = "\n".join(str(item.value) for item in at.warning)
    captions = "\n".join(str(item.value) for item in at.caption)
    assert "34" in warnings
    assert "MWh" in warnings
    assert "ANEEL" in captions and "SIGA" in captions
    assert "IBGE" in captions
    assert any(len(list(box.options)) == 399 for box in at.selectbox)
    at.text_input[0].set_value("Virmond")
    at.run()
    assert not at.exception, at.exception
    city = next(
        box
        for box in at.selectbox
        if any(str(option).startswith("Virmond") for option in box.options)
        and len(list(box.options)) < 10
    )
    choice = next(
        option for option in city.options if str(option).startswith("Virmond")
    )
    city.set_value(choice)
    at.run()
    assert not at.exception, at.exception
    focus = "\n".join(str(item.value) for item in at.markdown)
    assert "Virmond" in focus


def test_environment_page_withholds_invented_indicators(
    _streamlit_paths: None,
) -> None:
    from geoai.portal.landcover_panel import load_landcover_bundle

    page = REPO / "app" / "pages" / "9_Meio_Ambiente.py"
    at = AppTest.from_file(str(page), default_timeout=120)
    at.run()
    assert not at.exception, at.exception
    text = "\n".join(
        [
            *(str(item.value) for item in at.markdown),
            *(str(item.value) for item in at.caption),
            *(str(item.value) for item in at.warning),
        ]
    )
    assert "MapBiomas" in text
    assert "não catalogada" in text
    assert "indisponíveis" in text
    assert "desmatamento" in text.lower()
    if load_landcover_bundle(REPO).available:
        # Com a Coleção 11 validada: citação, limites e nada de UC/água.
        assert "Coleção 11" in text
        assert "não é taxa de desmatamento" in text.lower()
        assert "Unidades de conservação e recursos hídricos estão" in text
        assert "não foram reescalados" in text or "reescalado" in text
    else:
        assert "vegetação" in text.lower()


def test_agriculture_page_withholds_invented_indicators(
    _streamlit_paths: None,
) -> None:
    page = REPO / "app" / "pages" / "10_Agricultura.py"
    at = AppTest.from_file(str(page), default_timeout=120)
    at.run()
    assert not at.exception, at.exception
    text = "\n".join(
        [
            *(str(item.value) for item in at.markdown),
            *(str(item.value) for item in at.caption),
            *(str(item.value) for item in at.warning),
            *(str(item.value) for item in at.metric),
        ]
    )
    assert "PAM" in text
    assert "CONAB" in text
    assert "IPARDES" in text
    assert "indisponíve" in text.lower()
    assert "não catalogada" in text
    metrics = {str(item.label): str(item.value) for item in at.metric}
    labels = ("Produção agrícola", "Área plantada", "Rendimento", "Pecuária")
    from geoai.portal.agro_panel import load_agro_panel_bundle

    if load_agro_panel_bundle(REPO).available:
        # Com artefato IBGE validado: valores vêm do painel, com fonte citada.
        assert all(metrics[label] != "indisponível" for label in labels)
        assert "IBGE" in text
        assert "biogás" in text
    else:
        assert all(metrics[label] == "indisponível" for label in labels)


def test_ndvi_page_reports_progress_without_inventing(_streamlit_paths: None) -> None:
    page = REPO / "research" / "ndvi_congelado" / "portal_12_NDVI_Cidades.py"
    at = AppTest.from_file(str(page), default_timeout=120)
    at.run()
    assert not at.exception, at.exception
    metrics = {str(item.label): str(item.value) for item in at.metric}
    assert metrics["Municípios na lista"] == "97"
    from geoai.portal.ndvi_panel import load_ndvi_overview

    counts = load_ndvi_overview(REPO)["counts"]
    assert metrics["Com NDVI publicado"] == str(counts["publicado"])
    text = "\n".join(
        [
            *(str(item.value) for item in at.caption),
            *(str(item.value) for item in at.warning),
            *(str(item.value) for item in at.markdown),
        ]
    )
    assert "não é biomassa" in text
    if counts["publicado"] == 0:
        assert "Nenhum mapa de NDVI está publicado" in text


def test_texto_do_menu_na_home_bate_com_a_navegacao() -> None:
    """A Home lista as áreas em prosa. Essa lista precisa seguir o menu real.

    Esta foi a brecha que deixou «Vegetação por satélite» na tela depois que a
    página saiu da navegação: o nome estava escrito à mão em um st.info, longe
    de NAV_GROUPS, e nenhuma busca por «NDVI» o encontrava. O teste lê o texto
    renderizado, não o código, porque no código a frase vem quebrada em linhas.
    """
    import sys

    sys.path.insert(0, str(REPO / "app"))
    from _bootstrap import NAV_GROUPS

    at = AppTest.from_file(str(REPO / "app" / "Home.py"), default_timeout=240)
    at.run()
    assert not at.exception
    trecho = next(
        (i.value for i in at.info if "menu lateral" in i.value),
        "",
    )
    assert trecho, "a Home não lista mais as áreas do menu"

    rotulos = {
        rotulo
        for _grupo, itens in NAV_GROUPS
        for _caminho, rotulo, _icone in itens
        if rotulo != "Início"
    }
    for rotulo in rotulos:
        assert rotulo in trecho, f"«{rotulo}» está no menu e falta no texto da Home"

    for citado in re.findall(r"\*\*([^*]+)\*\*", trecho):
        nome = citado.split(" (")[0].strip()
        assert nome in rotulos, f"«{nome}» aparece no texto da Home e não está no menu"
