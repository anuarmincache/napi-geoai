"""Pacote científico do NAPI GeoAI.

Nesta fase o pacote expõe apenas metadados básicos e um ponto de entrada
testável. Processamento geoespacial, conectores e interfaces virão em
issues posteriores.
"""

from __future__ import annotations

__all__ = ["__version__", "package_name"]

__version__ = "0.1.0"
package_name = "geoai"


def get_version() -> str:
    """Retorna a versão semântica do pacote."""
    return __version__
