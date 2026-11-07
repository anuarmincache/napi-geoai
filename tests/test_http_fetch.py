"""Testes do download HTTP compartilhado (cache e retries)."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from geoai.connectors.errors import NetworkConnectorError
from geoai.connectors.http_fetch import download_http_file, sha256_file


def test_download_and_reuse_cache(tmp_path: Path) -> None:
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
    )
    second = download_http_file(
        "https://example.test/blob.bin",
        dest,
        source_id="test.blob",
        client=client,
        use_cache=True,
    )
    client.close()
    assert calls["n"] == 1
    assert first.content_sha256 == sha256_file(dest)
    assert second.content_sha256 == first.content_sha256


def test_download_retries_then_fails(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
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
