"""Downloads públicos permanecem fechados. O teste local é explícito."""

from __future__ import annotations

LOOPBACK = "127.0.0.1"


def public_downloads_enabled() -> bool:
    """Esta versão não serve arquivo nenhum fora da máquina local."""

    return False


def local_downloads_enabled(requested: bool, server_address: str | None) -> bool:
    """Exige a opção de teste e o servidor preso a 127.0.0.1."""

    return bool(requested) and (server_address or "") == LOOPBACK
