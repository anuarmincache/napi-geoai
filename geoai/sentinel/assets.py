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


def https_path_matches(
    https_path: str,
    product_id: str,
    tile: str,
    band: str,
) -> bool:
    """O caminho precisa ser o $value oficial daquele produto, tile e banda."""

    if band not in BANDS or not product_id or not tile:
        return False
    try:
        official_asset_url(https_path)
    except ValueError:
        return False
    filename = {
        "B04_10m": "B04_10m.jp2",
        "B08_10m": "B08_10m.jp2",
        "SCL_20m": "SCL_20m.jp2",
    }[band]
    resolution = "R20m" if band == "SCL_20m" else "R10m"
    return (
        f"Nodes({product_id}.SAFE)" in https_path
        and f"T{tile}_" in https_path
        and f"Nodes({resolution})" in https_path
        and https_path.endswith(f"{filename})/$value")
    )


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
