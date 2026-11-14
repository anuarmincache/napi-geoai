"""URLs das bandas B04, B08 e SCL. A query string não é aceita na origem."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlunparse

from geoai.sentinel.cdse_auth import DOWNLOAD_HOST, assert_odata_asset_url

BANDS = ("B04_10m", "B08_10m", "SCL_20m")


def official_asset_url(https_path: str) -> str:
    url = urlunparse(("https", DOWNLOAD_HOST, https_path, "", "", ""))
    assert_odata_asset_url(url)
    return url


def https_band_urls(feature: dict[str, Any]) -> dict[str, str]:
    """Três bandas de um item STAC. Falha se alguma URL não for o $value oficial."""

    assets = feature.get("assets") or {}
    urls: dict[str, str] = {}
    for key in BANDS:
        asset = assets.get(key) or {}
        alternate = (asset.get("alternate") or {}).get("https") or {}
        href = str(alternate.get("href") or "")
        assert_odata_asset_url(href)
        urls[key] = href
    return urls
