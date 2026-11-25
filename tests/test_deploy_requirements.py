"""O manifesto que a Streamlit Community Cloud instala precisa ser resolvível.

Contexto: o primeiro deploy quebrou com «Error installing requirements».
A causa foi `-e ..[ui]` em app/requirements.txt. O pip resolve caminho relativo
de um arquivo de requirements a partir do diretório de trabalho, e não do
diretório do arquivo. A Cloud roda o pip na raiz do repositório, então `..`
apontava para fora do clone.

O comentário dentro do próprio arquivo afirmava o contrário, o que mostra que
suposição escrita em comentário não substitui verificação.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
MANIFESTO = REPO / "app" / "requirements.txt"


def _linhas_uteis(caminho: Path) -> list[str]:
    linhas = []
    for bruta in caminho.read_text(encoding="utf-8").splitlines():
        linha = bruta.split("#", 1)[0].strip()
        if linha:
            linhas.append(linha)
    return linhas


def test_manifesto_do_entrypoint_existe() -> None:
    """A Cloud detecta o requirements que está junto do entrypoint."""
    assert MANIFESTO.exists()
    assert (REPO / "app" / "Home.py").exists()


def test_caminho_editavel_resolve_a_partir_da_raiz() -> None:
    """Como o pip resolve a partir do diretório de trabalho, `..` quebraria."""
    for linha in _linhas_uteis(MANIFESTO):
        achado = re.match(r"-e\s+(\S+)", linha)
        if not achado:
            continue
        alvo = achado.group(1).split("[")[0]
        resolvido = (REPO / alvo).resolve()
        assert resolvido.is_relative_to(REPO.resolve()), (
            f"«{linha}» aponta para {resolvido}, fora do repositório. "
            "O pip resolve a partir da raiz, onde a Cloud executa."
        )
        assert (resolvido / "pyproject.toml").exists(), (
            f"«{linha}» aponta para {resolvido}, que não tem pyproject.toml"
        )


def test_extras_pedidos_existem_no_pyproject() -> None:
    """Pedir um extra inexistente passa no pip e deixa a app sem dependência."""
    import tomllib

    config = tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))
    disponiveis = set(config["project"].get("optional-dependencies", {}))
    for linha in _linhas_uteis(MANIFESTO):
        for extras in re.findall(r"\[([^\]]+)\]", linha):
            for extra in extras.split(","):
                nome = extra.strip()
                assert nome in disponiveis, (
                    f"extra «{nome}» não existe em pyproject.toml "
                    f"(disponíveis: {sorted(disponiveis)})"
                )


def test_dependencias_da_interface_cobrem_o_que_a_app_importa() -> None:
    """O extra ui precisa trazer streamlit e o mapa, que as páginas usam."""
    import tomllib

    config = tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))
    ui = " ".join(config["project"]["optional-dependencies"]["ui"]).lower()
    assert "streamlit" in ui
    assert "folium" in ui
