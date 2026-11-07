"""Testes do download HTTP (cache, TTL, atômico, retries)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from geoai.connectors.contracts import ProvenanceRecord
from geoai.connectors.errors import NetworkConnectorError, ValidationConnectorError
from geoai.connectors.http_fetch import (
    download_http_file,
    read_cache_meta,
    sha256_file,
    write_cache_meta,
)


def test_download_reuses_cache_within_ttl(tmp_path: Path) -> None:
    payload = b"hello-napi-geoai"
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(200, content=payload, headers={"ETag": '"abc"'})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    dest = tmp_path / "blob.bin"
    first = download_http_file(
        "https://example.test/blob.bin",
        dest,
        source_id="test.blob",
        client=client,
        use_cache=True,
        cache_ttl_s=3600,
    )
    second = download_http_file(
        "https://example.test/blob.bin",
        dest,
        source_id="test.blob",
        client=client,
        use_cache=True,
        cache_ttl_s=3600,
    )
    client.close()
    assert calls["n"] == 1
    assert second.cache_hit is True
    assert first.content_sha256 == sha256_file(dest)


def test_cache_rejects_url_mismatch(tmp_path: Path) -> None:
    payload = b"payload-a"
    dest = tmp_path / "blob.bin"
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        body = payload if "blob-a" in str(request.url) else b"payload-b"
        return httpx.Response(200, content=body, headers={"ETag": f'"{calls["n"]}"'})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    download_http_file(
        "https://example.test/blob-a.bin",
        dest,
        source_id="test.blob",
        client=client,
        cache_ttl_s=3600,
    )
    download_http_file(
        "https://example.test/blob-b.bin",
        dest,
        source_id="test.blob",
        client=client,
        cache_ttl_s=3600,
    )
    client.close()
    assert calls["n"] == 2
    assert dest.read_bytes() == b"payload-b"


def test_conditional_get_304_updates_last_checked(tmp_path: Path) -> None:
    dest = tmp_path / "blob.bin"
    dest.write_bytes(b"stable")
    past = (datetime.now(UTC) - timedelta(hours=48)).isoformat()
    write_cache_meta(
        dest,
        ProvenanceRecord(
            source_id="test.blob",
            url="https://example.test/blob.bin",
            retrieved_at=past,
            content_sha256=sha256_file(dest),
            content_length=dest.stat().st_size,
            http_etag='"abc"',
            last_checked_at=past,
        ),
    )
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        assert request.headers.get("If-None-Match") == '"abc"'
        return httpx.Response(304, headers={"ETag": '"abc"'})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    result = download_http_file(
        "https://example.test/blob.bin",
        dest,
        source_id="test.blob",
        client=client,
        cache_ttl_s=0,  # força revalidação
    )
    client.close()
    assert calls["n"] == 1
    assert result.not_modified is True
    assert result.cache_hit is True
    assert result.retrieved_at == past
    assert result.last_checked_at != past


def test_partial_download_preserves_existing_file(tmp_path: Path) -> None:
    dest = tmp_path / "blob.bin"
    dest.write_bytes(b"good-cache")
    write_cache_meta(
        dest,
        ProvenanceRecord(
            source_id="test.blob",
            url="https://example.test/blob.bin",
            retrieved_at=_iso_hours_ago(1),
            content_sha256=sha256_file(dest),
            content_length=10,
            http_etag='"old"',
            last_checked_at=_iso_hours_ago(1),
        ),
    )

    def handler(request: httpx.Request) -> httpx.Response:
        def boom() -> bytes:
            yield b"bad"
            raise httpx.ReadError("stream cut")

        return httpx.Response(200, content=boom(), headers={"ETag": '"new"'})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(NetworkConnectorError):
        download_http_file(
            "https://example.test/blob.bin",
            dest,
            source_id="test.blob",
            client=client,
            force_refresh=True,
            retries=1,
            use_cache=True,
        )
    client.close()
    assert dest.read_bytes() == b"good-cache"
    assert not dest.with_suffix(".bin.partial").exists()


def test_validator_failure_does_not_promote(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"nope")

    def validator(path: Path) -> None:
        raise ValidationConnectorError("conteúdo inválido")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    dest = tmp_path / "x.bin"
    with pytest.raises(ValidationConnectorError):
        download_http_file(
            "https://example.test/x.bin",
            dest,
            source_id="test.x",
            client=client,
            content_validator=validator,
            use_cache=False,
        )
    client.close()
    assert not dest.exists()


def test_http_404_not_retried(tmp_path: Path) -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(404, request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(NetworkConnectorError, match="HTTP 404"):
        download_http_file(
            "https://example.test/missing",
            tmp_path / "x.bin",
            source_id="test.missing",
            client=client,
            retries=3,
            retry_backoff_s=0.01,
            use_cache=False,
        )
    client.close()
    assert calls["n"] == 1


def test_download_retries_5xx_then_fails(tmp_path: Path) -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(500, request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(NetworkConnectorError):
        download_http_file(
            "https://example.test/fail",
            tmp_path / "x.bin",
            source_id="test.fail",
            client=client,
            retries=2,
            retry_backoff_s=0.01,
            use_cache=False,
        )
    client.close()
    assert calls["n"] == 2


def _iso_hours_ago(hours: int) -> str:
    return (datetime.now(UTC) - timedelta(hours=hours)).isoformat()


def test_read_write_cache_roundtrip(tmp_path: Path) -> None:
    dest = tmp_path / "a.bin"
    dest.write_bytes(b"x")
    record = ProvenanceRecord(
        source_id="s",
        url="https://example.test/a.bin",
        retrieved_at=_iso_hours_ago(0),
        content_sha256=sha256_file(dest),
        content_length=1,
        last_checked_at=_iso_hours_ago(0),
    )
    write_cache_meta(dest, record)
    meta = read_cache_meta(dest)
    assert meta is not None
    assert meta["source_id"] == "s"
