"""Testes offline do conector ANEEL SIGA."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from geoai.connectors.aneel import (
    ANEEL_SIGA_CSV_URL,
    download_siga_csv,
    parse_siga_csv,
    parse_siga_file,
    validate_siga_csv_file,
)
from geoai.connectors.contracts import ProvenanceRecord
from geoai.connectors.errors import NetworkConnectorError, ValidationConnectorError
from geoai.connectors.http_fetch import sha256_file, write_cache_meta

FIXTURE = Path(__file__).parent / "fixtures" / "aneel_siga_mini.csv"


def test_parse_siga_fixture_filters_pr() -> None:
    rows = parse_siga_file(FIXTURE, uf="PR")
    assert len(rows) == 5
    assert all(r["SigUFPrincipal"] == "PR" for r in rows)
    assert rows[0]["CodCEG"]
    assert "MdaPotenciaOutorgadaKw" in rows[0]


def test_parse_siga_limit_zero_and_negative() -> None:
    text = FIXTURE.read_text(encoding="utf-8")
    assert parse_siga_csv(text, limit=0) == []
    with pytest.raises(ValidationConnectorError, match="negativo"):
        parse_siga_csv(text, limit=-1)


def test_parse_siga_rejects_missing_columns() -> None:
    bad = '"a";"b"\n"1";"2"\n'
    with pytest.raises(ValidationConnectorError, match="sem campos"):
        parse_siga_csv(bad)


def test_validate_siga_rejects_wrong_delimiter(tmp_path: Path) -> None:
    path = tmp_path / "bad.csv"
    path.write_text("a,b,c\n1,2,3\n", encoding="utf-8")
    with pytest.raises(ValidationConnectorError, match="delimitador"):
        validate_siga_csv_file(path)


def test_download_siga_csv_mock(tmp_path: Path) -> None:
    payload = FIXTURE.read_bytes()

    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url).startswith("https://dadosabertos.aneel.gov.br/")
        return httpx.Response(
            200,
            content=payload,
            headers={
                "ETag": '"siga-test"',
                "Last-Modified": "Sun, 01 Nov 2026 05:07:52 GMT",
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    dest = tmp_path / "siga.csv"
    result = download_siga_csv(dest, client=client, use_cache=False)
    client.close()
    assert dest.exists()
    assert result.provenance.content_sha256
    assert result.source_id.startswith("aneel.siga")
    rows = parse_siga_file(dest, uf="PR")
    assert len(rows) == 5


def test_download_rejects_invalid_csv_before_cache(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"not;a;valid;siga\n1;2;3;4\n")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    dest = tmp_path / "siga.csv"
    with pytest.raises(ValidationConnectorError, match="sem campos"):
        download_siga_csv(dest, client=client, use_cache=True)
    client.close()
    assert not dest.exists()
    assert not dest.with_suffix(".csv.cache.json").exists()


def test_download_rejects_invalid_cached_csv(tmp_path: Path) -> None:
    dest = tmp_path / "siga.csv"
    dest.write_text("bad;header\n1;2\n", encoding="utf-8")
    write_cache_meta(
        dest,
        ProvenanceRecord(
            source_id="aneel.siga.empreendimentos_geracao",
            url=ANEEL_SIGA_CSV_URL,
            retrieved_at="2026-11-07T00:00:00+00:00",
            content_sha256=sha256_file(dest),
            content_length=dest.stat().st_size,
            last_checked_at="2026-11-07T00:00:00+00:00",
        ),
    )
    with pytest.raises(ValidationConnectorError):
        download_siga_csv(dest, use_cache=True, cache_ttl_s=86_400, client=None)


def test_download_siga_http_error(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(NetworkConnectorError):
        download_siga_csv(
            tmp_path / "x.csv",
            url=ANEEL_SIGA_CSV_URL,
            client=client,
            retries=2,
            retry_backoff_s=0.01,
            use_cache=False,
        )
    client.close()
