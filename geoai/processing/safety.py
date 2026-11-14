"""Caminhos permitidos e publicação atômica de artefatos."""

from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any

from geoai.processing.contract import JobContractError


def resolve_allowed_path(path: Path, *, roots: list[Path]) -> Path:
    """Resolve o caminho e exige que permaneça sob uma raiz permitida."""

    candidate = Path(path).expanduser()
    try:
        resolved = candidate.resolve(strict=False)
    except OSError as exc:
        raise JobContractError(f"caminho ilegível: {path}") from exc
    for root in roots:
        root_resolved = Path(root).resolve(strict=False)
        try:
            resolved.relative_to(root_resolved)
        except ValueError:
            continue
        return resolved
    raise JobContractError(
        f"caminho fora das raízes permitidas: {resolved}"
    )


def _replace_exclusive(source: Path, destination: Path) -> None:
    """os.replace com nova tentativa. No Windows o alvo pode estar em troca."""

    delay = 0.01
    for attempt in range(8):
        try:
            os.replace(source, destination)
            return
        except PermissionError:
            if attempt == 7:
                raise
            time.sleep(delay)
            delay *= 2


def _unlink_own(path: Path) -> None:
    delay = 0.01
    for _ in range(8):
        try:
            if path.exists():
                path.unlink()
            return
        except PermissionError:
            time.sleep(delay)
            delay *= 2
    if path.exists():
        path.unlink()


def atomic_write_json(destination: Path, payload: dict[str, Any]) -> int:
    """Grava JSON em temporário exclusivo e troca com os.replace.

    Cada chamada cria o seu arquivo no mesmo diretório do destino e apaga
    só esse temporário. Uma falha de validação não altera o destino.
    """

    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    fd, name = tempfile.mkstemp(
        prefix=f".{destination.name}.",
        suffix=".partial",
        dir=destination.parent,
    )
    partial = Path(name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        try:
            reloaded = json.loads(partial.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise JobContractError(
                "JSON de saída inválido; destino anterior preservado"
            ) from exc
        if not isinstance(reloaded, dict):
            raise JobContractError("saída JSON não é objeto")
        _replace_exclusive(partial, destination)
    finally:
        _unlink_own(partial)
    return destination.stat().st_size
