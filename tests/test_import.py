"""Testes de importação e metadados do pacote geoai."""

from __future__ import annotations

import geoai
from geoai import get_version


def test_package_import() -> None:
    assert geoai.package_name == "geoai"


def test_version_string() -> None:
    version = get_version()
    assert isinstance(version, str)
    assert version == geoai.__version__
    assert version.count(".") >= 2
