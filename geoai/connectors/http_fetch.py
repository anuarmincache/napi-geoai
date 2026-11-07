"""Download HTTP atômico com retries seletivos, cache e revalidação."""

from __future__ import annotations

import hashlib
import json
import os
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx

from geoai.connectors.contracts import ProvenanceRecord
from geoai.connectors.errors import (
    CacheConnectorError,
    NetworkConnectorError,
    ValidationConnectorError,
)

ContentValidator = Callable[[Path], None]

# HTTP status em que novas tentativas fazem sentido.
_RETRYABLE_STATUS = frozenset({408, 429, 500, 502, 503, 504})


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


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _parse_iso(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


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


def _cache_matches_request(
    cached: dict[str, object],
    *,
    url: str,
    source_id: str,
    destination: Path,
) -> bool:
    if str(cached.get("url", "")) != url:
        return False
    if str(cached.get("source_id", "")) != source_id:
        return False
    if not destination.exists():
        return False
    sha = cached.get("content_sha256")
    return isinstance(sha, str) and sha == sha256_file(destination)


def _within_ttl(cached: dict[str, object], cache_ttl_s: float | None) -> bool:
    if cache_ttl_s is None:
        return False
    stamp = str(cached.get("last_checked_at") or cached.get("retrieved_at") or "")
    checked = _parse_iso(stamp)
    if checked is None:
        return False
    if checked.tzinfo is None:
        checked = checked.replace(tzinfo=UTC)
    return datetime.now(UTC) - checked <= timedelta(seconds=cache_ttl_s)


def _provenance_from_cache(
    cached: dict[str, object],
    *,
    destination: Path,
    last_checked_at: str,
    cache_hit: bool,
    not_modified: bool,
) -> ProvenanceRecord:
    return ProvenanceRecord(
        source_id=str(cached["source_id"]),
        url=str(cached["url"]),
        retrieved_at=str(cached.get("retrieved_at", "")),
        content_sha256=str(cached["content_sha256"]),
        content_length=int(cached.get("content_length", 0)),
        http_etag=(
            str(cached["http_etag"]) if cached.get("http_etag") is not None else None
        ),
        http_last_modified=(
            str(cached["http_last_modified"])
            if cached.get("http_last_modified") is not None
            else None
        ),
        license_note=str(cached.get("license_note", "")),
        local_path=str(destination.resolve()),
        last_checked_at=last_checked_at,
        cache_hit=cache_hit,
        not_modified=not_modified,
        extra=dict(cached.get("extra") or {}),
    )


def _should_retry_status(status_code: int) -> bool:
    return status_code in _RETRYABLE_STATUS


def _retry_after_seconds(response: httpx.Response, fallback: float) -> float:
    raw = response.headers.get("Retry-After")
    if raw is None:
        return fallback
    try:
        return max(0.0, float(raw))
    except ValueError:
        return fallback


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
    force_refresh: bool = False,
    cache_ttl_s: float | None = 86_400.0,
    content_validator: ContentValidator | None = None,
    client: httpx.Client | None = None,
    extra: dict[str, object] | None = None,
) -> ProvenanceRecord:
    """Baixa um arquivo HTTP com cache revalidável e escrita atômica.

    Política de cache:
    - Integridade (SHA-256) ≠ atualidade.
    - Reuso sem rede só se ``url``+``source_id`` batem, SHA ok e TTL de
      ``last_checked_at`` ainda válido (não afirma que o remoto mudou).
    - Fora do TTL (ou ``cache_ttl_s=None``): conditional GET (ETag/
      Last-Modified); 304 atualiza ``last_checked_at`` sem redownload.
    - ``force_refresh=True`` ignora TTL e força GET completo.
    """

    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(destination.suffix + ".partial")

    owns_client = client is None
    http = client or httpx.Client(follow_redirects=True, timeout=timeout_s)
    last_error: Exception | None = None
    cached = read_cache_meta(destination) if destination.exists() else None
    cache_ok = (
        use_cache
        and not force_refresh
        and cached is not None
        and _cache_matches_request(
            cached, url=url, source_id=source_id, destination=destination
        )
    )

    try:
        if cache_ok and cached is not None and _within_ttl(cached, cache_ttl_s):
            now = _now_iso()
            record = _provenance_from_cache(
                cached,
                destination=destination,
                last_checked_at=str(cached.get("last_checked_at") or now),
                cache_hit=True,
                not_modified=False,
            )
            return record

        for attempt in range(1, retries + 1):
            headers: dict[str, str] = {}
            conditional = (
                cache_ok
                and cached is not None
                and not force_refresh
                and (
                    cached.get("http_etag") is not None
                    or cached.get("http_last_modified") is not None
                )
            )
            if conditional and cached is not None:
                if cached.get("http_etag"):
                    headers["If-None-Match"] = str(cached["http_etag"])
                if cached.get("http_last_modified"):
                    headers["If-Modified-Since"] = str(cached["http_last_modified"])

            try:
                with http.stream("GET", url, headers=headers) as response:
                    status = response.status_code
                    if status == 304 and cache_ok and cached is not None:
                        now = _now_iso()
                        record = _provenance_from_cache(
                            cached,
                            destination=destination,
                            last_checked_at=now,
                            cache_hit=True,
                            not_modified=True,
                        )
                        write_cache_meta(destination, record)
                        return record

                    if status >= 400:
                        if not _should_retry_status(status) or attempt >= retries:
                            raise NetworkConnectorError(
                                f"HTTP {status} para {url}"
                            )
                        time.sleep(
                            _retry_after_seconds(
                                response, retry_backoff_s * attempt
                            )
                        )
                        continue

                    try:
                        if partial.exists():
                            partial.unlink()
                        with partial.open("wb") as handle:
                            for chunk in response.iter_bytes():
                                handle.write(chunk)
                    except Exception:
                        if partial.exists():
                            partial.unlink(missing_ok=True)
                        raise

                    size = partial.stat().st_size
                    if size <= 0:
                        partial.unlink(missing_ok=True)
                        raise ValidationConnectorError(f"arquivo vazio: {url}")

                    if content_validator is not None:
                        try:
                            content_validator(partial)
                        except Exception:
                            partial.unlink(missing_ok=True)
                            raise

                    sha = sha256_file(partial)
                    etag = response.headers.get("ETag")
                    last_modified = response.headers.get("Last-Modified")
                    now = _now_iso()
                    os.replace(partial, destination)
                    provenance = ProvenanceRecord(
                        source_id=source_id,
                        url=url,
                        retrieved_at=now,
                        content_sha256=sha,
                        content_length=size,
                        http_etag=etag,
                        http_last_modified=last_modified,
                        license_note=license_note,
                        local_path=str(destination.resolve()),
                        last_checked_at=now,
                        cache_hit=False,
                        not_modified=False,
                        extra=dict(extra or {}),
                    )
                    if use_cache:
                        write_cache_meta(destination, provenance)
                    return provenance
            except ValidationConnectorError:
                raise
            except NetworkConnectorError as exc:
                last_error = exc
                if partial.exists():
                    partial.unlink(missing_ok=True)
                msg = str(exc)
                # 4xx não retryable (exceto 408/429 já tratados no loop).
                if "HTTP 4" in msg and "HTTP 408" not in msg and "HTTP 429" not in msg:
                    raise
                if attempt >= retries:
                    break
                time.sleep(retry_backoff_s * attempt)
            except (httpx.HTTPError, OSError) as exc:
                last_error = exc
                if partial.exists():
                    partial.unlink(missing_ok=True)
                if attempt >= retries:
                    break
                time.sleep(retry_backoff_s * attempt)
    finally:
        if owns_client:
            http.close()
        if partial.exists():
            partial.unlink(missing_ok=True)

    raise NetworkConnectorError(
        f"falha ao baixar {url} após {retries} tentativas: {last_error}"
    )
