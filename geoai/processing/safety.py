"""Caminhos permitidos e publicação atômica de artefatos."""

from __future__ import annotations

import json
import os
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


def atomic_write_json(destination: Path, payload: dict[str, Any]) -> int:
    """Grava JSON via arquivo temporário e troca atômica.

    Se a validação falhar, o destino anterior permanece intacto.
    """

    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_name(destination.name + ".partial")
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    partial.write_text(text, encoding="utf-8")
    try:
        reloaded = json.loads(partial.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        partial.unlink(missing_ok=True)
        raise JobContractError(
            "JSON de saída inválido; destino anterior preservado"
        ) from exc
    if not isinstance(reloaded, dict):
        partial.unlink(missing_ok=True)
        raise JobContractError("saída JSON não é objeto")
    os.replace(partial, destination)
    return destination.stat().st_size
