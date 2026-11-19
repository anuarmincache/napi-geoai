"""Integridade de arquivos do catálogo, sem rede e sem reprocessar raster."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

PUBLIC_PATH_TOKENS = (
    "c:\\",
    "c:/",
    "/users/",
    "onedrive",
    "área de trabalho",
    "area de trabalho",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json(payload: dict[str, Any]) -> bytes:
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    return (text + "\n").encode("utf-8")


def assert_public_metadata(payload: dict[str, Any]) -> None:
    """Recusa caminho absoluto ou pasta local em metadado público."""

    text = json.dumps(payload, ensure_ascii=False).lower()
    if any(token in text for token in PUBLIC_PATH_TOKENS):
        raise ValueError("caminho_local_no_catalogo_publico")


def file_record(
    *,
    exists: bool,
    validated: bool,
    reason: str | None,
    filename: str | None = None,
    sha256: str | None = None,
    size: int | None = None,
) -> dict[str, Any]:
    """Separa arquivo existente, arquivo validado e arquivo publicado.

    ``available`` repete a validação local. ``public_download`` só pode ser
    verdadeiro depois de uma publicação explícita, que este módulo não faz.
    """

    return {
        "exists": exists,
        "validated": validated,
        "published": False,
        "public_download": False,
        "available": validated,
        "filename": filename,
        "sha256": sha256,
        "bytes": size,
        "reason": reason,
    }


def product_availability(
    path: Path | None,
    *,
    expected_sha256: str | None = None,
    expected_bytes: int | None = None,
) -> dict[str, Any]:
    """Confere o arquivo. Existir ou validar não publica o download."""

    if path is None or not path.is_file():
        return file_record(exists=False, validated=False, reason="nao_gerado")
    digest = sha256_file(path)
    size = path.stat().st_size
    if expected_sha256 is not None and digest != expected_sha256:
        return file_record(exists=True, validated=False, reason="checksum_divergente")
    if expected_bytes is not None and size != expected_bytes:
        return file_record(exists=True, validated=False, reason="tamanho_divergente")
    return file_record(
        exists=True,
        validated=True,
        reason=None,
        filename=path.name,
        sha256=digest,
        size=size,
    )


def write_json(path: Path, payload: dict[str, Any]) -> bytes:
    body = canonical_json(payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    return body


def integrity_record(public_relative: str, body: bytes) -> dict[str, Any]:
    return {
        "schema": "napi-map-catalog-integrity-1",
        "public_entry": public_relative.replace("\\", "/"),
        "sha256": hashlib.sha256(body).hexdigest(),
        "bytes": len(body),
    }


def verify_integrity(public_path: Path, record: dict[str, Any]) -> None:
    body = public_path.read_bytes()
    digest = hashlib.sha256(body).hexdigest()
    if digest != record["sha256"] or len(body) != record["bytes"]:
        raise RuntimeError("catalogo_publico_divergente")
