"""packages.txt na Cloud: sem comentários (apt trata cada token como pacote)."""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def test_packages_txt_tem_zero_pacotes_apt() -> None:
    path = REPO / "packages.txt"
    assert path.is_file()
    # Qualquer token (inclusive após #) vira tentativa de apt-get na Cloud.
    for i, bruta in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        assert not bruta.strip(), (
            f"packages.txt linha {i} não está vazia: {bruta!r}. "
            "A Streamlit Cloud não ignora comentários neste arquivo."
        )
