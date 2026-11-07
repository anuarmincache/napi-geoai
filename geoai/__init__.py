"""Pacote científico do NAPI GeoAI.

Expõe metadados do pacote e submódulos de conectores/limites territoriais.
Interfaces web e orquestração pesada ficam fora desta fase.
"""

from __future__ import annotations

__all__ = ["__version__", "package_name"]

__version__ = "0.1.0"
package_name = "geoai"


def get_version() -> str:
    """Retorna a versão semântica do pacote."""
    return __version__
