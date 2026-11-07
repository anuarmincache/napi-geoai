"""Testes do conector IBGE com HTTP mockado (sem rede)."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import httpx
import pytest
from geoai.connectors.errors import NetworkConnectorError
from geoai.connectors.ibge import (
    IBGE_PR_UF_2025_URL,
    download_ibge_zip,
    write_provenance,
)


def _tiny_zip_bytes() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("readme.txt", "fixture zip for connector unit test\n")
    return buffer.getvalue()


def test_download_ibge_zip_records_provenance(tmp_path: Path) -> None:
    payload = _tiny_zip_bytes()

    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url).startswith("https://geoftp.ibge.gov.br/")
        return httpx.Response(
            200,
            content=payload,
            headers={
                "ETag": '"test-etag"',
                "Last-Modified": "Thu, 26 Feb 2026 20:02:50 GMT",
            },
        )

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport)
    dest = tmp_path / "PR_UF_2025.zip"
    source = download_ibge_zip(
        IBGE_PR_UF_2025_URL, dest, client=client, use_cache=False
    )
    client.close()

    assert dest.exists()
    assert source.content_length == dest.stat().st_size
    assert len(source.content_sha256) == 64
    assert source.expected_crs == "EPSG:4674"
    assert source.territory.startswith("Paraná")
    assert "IBGE" in source.license_note

    meta = write_provenance(source, tmp_path / "prov.json")
    text = meta.read_text(encoding="utf-8")
    assert "content_sha256" in text
    assert IBGE_PR_UF_2025_URL in text


def test_download_rejects_http_error(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, request=request)

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport)
    with pytest.raises(NetworkConnectorError):
        download_ibge_zip(
            IBGE_PR_UF_2025_URL,
            tmp_path / "x.zip",
            client=client,
            retries=2,
            use_cache=False,
        )
    client.close()
