"""Testes unitários de ops (sem PostGIS)."""

from __future__ import annotations

import pytest
from geoai.db.backup import (
    PROTECTED_DB_NAMES,
    assert_safe_temp_dbname,
    filter_restore_toc_exclude_extensions,
)
from geoai.db.url_safety import (
    database_url_with_dbname,
    parse_database_url,
    redact_database_url,
)


def test_redact_database_url_hides_password() -> None:
    url = "postgresql://napi:secret@127.0.0.1:5433/napi_geoai"
    red = redact_database_url(url)
    assert "secret" not in red
    assert "napi:***@" in red
    assert "5433" in red
    assert red.endswith("/napi_geoai")


def test_parse_and_swap_dbname() -> None:
    url = "postgresql://napi:x@127.0.0.1:5433/napi_geoai"
    parts = parse_database_url(url)
    assert parts.dbname == "napi_geoai"
    assert parts.port == 5433
    swapped = database_url_with_dbname(url, "napi_geoai_tmp_abc")
    assert swapped.endswith("/napi_geoai_tmp_abc")
    assert "napi_geoai_tmp_abc" in swapped


def test_temp_dbname_guards() -> None:
    assert_safe_temp_dbname("napi_geoai_tmp_test1")
    for bad in sorted(PROTECTED_DB_NAMES) + ["napi_geoai_tmp_", "other_db", "NAPI"]:
        with pytest.raises(ValueError):
            assert_safe_temp_dbname(bad)


def test_filter_restore_toc_excludes_extension() -> None:
    toc = """\
;
; Selected TOC Entries:
;
210; 3079 16386 EXTENSION - postgis
211; 0 0 COMMENT - EXTENSION postgis
3461; 0 18322 TABLE DATA public spatial_ref_sys postgres
345; 1259 16400 TABLE geoai territorial_units napi
"""
    filtered = filter_restore_toc_exclude_extensions(toc)
    assert "territorial_units" in filtered
    assert "EXTENSION" not in filtered.upper()
    assert "spatial_ref_sys" not in filtered.lower()
    assert "postgis" not in filtered.lower()


def test_doctor_format_json_roundtrip_structure() -> None:
    from geoai.db.doctor import DoctorCheck, DoctorReport, format_doctor_report

    report = DoctorReport(
        database_url_redacted="postgresql://napi:***@127.0.0.1:5433/napi_geoai",
        overall="ok",
        checks=[DoctorCheck("x", "ok", "y")],
        exit_code=0,
    )
    text = format_doctor_report(report, as_json=True)
    assert "napi_geoai" in text
    assert "secret" not in text
