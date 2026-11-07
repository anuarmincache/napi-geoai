"""Download HTTP com retries, checksum e cache local simples."""

from __future__ import annotations

import hashlib
import json
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx

from geoai.connectors.contracts import ProvenanceRecord
from geoai.connectors.errors import (
    CacheConnectorError,
    NetworkConnectorError,
    ValidationConnectorError,
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _cache_meta_path(destination: Path) -> Path:
    return destination.with_suffix(destination.suffix + ".cache.json")


def read_cache_meta(destination: Path) -> dict[str, object] | None:
    meta = _cache_meta_path(destination)
    if not meta.exists():
        return None
    try:
        return json.loads(meta.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CacheConnectorError(f"cache inválido: {meta}") from exc


def write_cache_meta(destination: Path, provenance: ProvenanceRecord) -> Path:
    meta = _cache_meta_path(destination)
    try:
        meta.write_text(
            json.dumps(provenance.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except OSError as exc:
        raise CacheConnectorError(f"falha ao gravar cache: {meta}") from exc
    return meta


def download_http_file(
    url: str,
    destination: Path,
    *,
    source_id: str,
    license_note: str = "",
    timeout_s: float = 120.0,
    retries: int = 3,
    retry_backoff_s: float = 0.5,
    use_cache: bool = True,
    client: httpx.Client | None = None,
    extra: dict[str, object] | None = None,
) -> ProvenanceRecord:
    """Baixa um arquivo HTTP com retries e cache opcional por ETag/tamanho.

    Se ``use_cache`` e o arquivo local existir com metadados compatíveis
    (ETag ou SHA-256), reutiliza o artefato sem novo download completo.
    """

    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)

    owns_client = client is None
    http = client or httpx.Client(follow_redirects=True, timeout=timeout_s)
    last_error: Exception | None = None

    try:
        if use_cache and destination.exists():
            cached = read_cache_meta(destination)
            if cached and cached.get("content_sha256") == sha256_file(destination):
                return ProvenanceRecord(
                    source_id=str(cached.get("source_id", source_id)),
                    url=str(cached.get("url", url)),
                    retrieved_at=str(cached.get("retrieved_at", "")),
                    content_sha256=str(cached["content_sha256"]),
                    content_length=int(cached.get("content_length", 0)),
                    http_etag=(
                        str(cached["http_etag"])
                        if cached.get("http_etag") is not None
                        else None
                    ),
                    http_last_modified=(
                        str(cached["http_last_modified"])
                        if cached.get("http_last_modified") is not None
                        else None
                    ),
                    license_note=str(cached.get("license_note", license_note)),
                    local_path=str(destination.resolve()),
                    extra=dict(cached.get("extra") or {}),
                )

        for attempt in range(1, retries + 1):
            try:
                with http.stream("GET", url) as response:
                    try:
                        response.raise_for_status()
                    except httpx.HTTPStatusError as exc:
                        raise NetworkConnectorError(
                            f"HTTP {exc.response.status_code} para {url}"
                        ) from exc
                    etag = response.headers.get("ETag")
                    last_modified = response.headers.get("Last-Modified")
                    with destination.open("wb") as handle:
                        for chunk in response.iter_bytes():
                            handle.write(chunk)
                sha = sha256_file(destination)
                size = destination.stat().st_size
                if size <= 0:
                    raise ValidationConnectorError(f"arquivo vazio: {destination}")
                provenance = ProvenanceRecord(
                    source_id=source_id,
                    url=url,
                    retrieved_at=datetime.now(UTC).isoformat(),
                    content_sha256=sha,
                    content_length=size,
                    http_etag=etag,
                    http_last_modified=last_modified,
                    license_note=license_note,
                    local_path=str(destination.resolve()),
                    extra=dict(extra or {}),
                )
                if use_cache:
                    write_cache_meta(destination, provenance)
                return provenance
            except (httpx.HTTPError, NetworkConnectorError, OSError) as exc:
                last_error = exc
                if attempt >= retries:
                    break
                time.sleep(retry_backoff_s * attempt)
    finally:
        if owns_client:
            http.close()

    raise NetworkConnectorError(
        f"falha ao baixar {url} após {retries} tentativas: {last_error}"
    )
