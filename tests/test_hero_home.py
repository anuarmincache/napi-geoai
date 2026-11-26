"""A ilustração do topo entra como imagem, e o texto continua sendo texto."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

REPO = Path(__file__).resolve().parents[1]


def test_arquivo_da_ilustracao_existe_e_e_leve() -> None:
    arquivo = REPO / "assets" / "hero-parana.webp"
    assert arquivo.is_file(), "a ilustração do topo não está no repositório"
    kib = arquivo.stat().st_size / 1024
    # A imagem vai embutida na página, então peso vira tempo de carregamento.
    assert kib < 400, f"ilustração com {kib:.0f} KB, grande demais para embutir"


def test_ilustracoes_dos_cartoes_existem_e_sao_leves() -> None:
    """As três artes dos cartões de público entram embutidas na página."""
    total = 0.0
    for nome in ("empreendedores", "pesquisadores", "gestores"):
        arquivo = REPO / "assets" / f"card-{nome}.webp"
        assert arquivo.is_file(), f"falta a ilustração do cartão {nome}"
        total += arquivo.stat().st_size / 1024
    assert total < 300, f"as três somam {total:.0f} KB, peso demais para embutir"


def test_titulo_do_topo_continua_sendo_texto() -> None:
    """Título dentro da imagem não é lido por leitor de tela nem reflui.

    A arte recebida trazia o título desenhado. Só a paisagem entra como
    imagem; a frase fica na página.
    """
    sys.path.insert(0, str(REPO / "app"))
    at = AppTest.from_file(str(REPO / "app" / "Home.py"), default_timeout=240)
    at.run()
    assert not at.exception

    html = "\n".join(
        m.value for m in at.markdown if isinstance(getattr(m, "value", None), str)
    )
    assert "<h1>NAPI GeoAI: onde investigar" in html
    assert "Território, população, energia, lavouras" in html
    assert 'class="scene"' in html
    assert "data:image/webp;base64," in html
    # A imagem precisa de descrição para quem usa leitor de tela.
    inicio = html.index('class="scene"')
    assert "aria-label" in html[inicio : inicio + 400]

    # Cada cartão de público traz a ilustração com descrição, e o título e o
    # texto continuam na página, não dentro do arquivo.
    assert html.count('class="art"') == 3
    for titulo in (
        "Empreendedores e empresas",
        "Pesquisadores e universidades",
        "Gestores públicos e cooperativas",
    ):
        assert f"<h4>{titulo}</h4>" in html
    for trecho in html.split('<img class="art"')[1:]:
        cabeca = trecho[:300]
        assert 'alt="' in cabeca and 'alt=""' not in cabeca
        assert "data:image/webp;base64," in cabeca


BANNERS_DAS_PAGINAS = {
    "6_Energia_SIGA.py": "banner-siga.webp",
    "8_Energia_MMGD.py": "banner-mmgd.webp",
    "11_Ferramentas.py": "banner-calculadoras.webp",
    "10_Agricultura.py": "banner-agricultura.webp",
    "9_Meio_Ambiente.py": "banner-cobertura.webp",
    "3_Fontes_e_qualidade.py": "banner-fontes.webp",
    "4_Sobre_e_deploy.py": "banner-sobre.webp",
    "7_Ficha_Municipal.py": "banner-ficha.webp",
}


def test_banners_das_paginas_existem_e_somam_pouco() -> None:
    total = 0.0
    for arquivo in BANNERS_DAS_PAGINAS.values():
        caminho = REPO / "assets" / arquivo
        assert caminho.is_file(), f"falta {arquivo}"
        total += caminho.stat().st_size / 1024
    # Cada página embute o seu, mas o repositório carrega todos.
    assert total < 800, f"os banners somam {total:.0f} KB"


@pytest.mark.parametrize(
    ("pagina", "banner"), sorted(BANNERS_DAS_PAGINAS.items()), ids=lambda v: str(v)
)
def test_pagina_usa_o_banner_e_mantem_o_titulo_como_texto(
    pagina: str, banner: str
) -> None:
    """Mesma regra do topo: a arte entra como imagem, o texto fica na página."""
    sys.path.insert(0, str(REPO / "app"))
    at = AppTest.from_file(str(REPO / "app" / "pages" / pagina), default_timeout=240)
    at.run()
    assert not at.exception

    html = "\n".join(
        m.value for m in at.markdown if isinstance(getattr(m, "value", None), str)
    )
    cabecalho = html[html.index('class="ezc-header"') :][:4000]
    assert "<h1>" in cabecalho, "o título precisa continuar sendo texto"
    assert "data:image/webp;base64," in cabecalho, f"{pagina} não carregou {banner}"
    inicio = cabecalho.index('class="art"')
    trecho = cabecalho[inicio : inicio + 300]
    assert 'alt="' in trecho and 'alt=""' not in trecho, "a arte precisa de descrição"
