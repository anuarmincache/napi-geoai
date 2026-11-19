"""Descreve o acesso declarado no STAC e o resultado de uma requisição anônima."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse


def _https_alternate(asset: dict[str, Any]) -> dict[str, Any]:
    alternate = asset.get("alternate") or {}
    https = alternate.get("https") or {}
    if not isinstance(https, dict):
        return {}
    return https


def declared_asset_access(asset: dict[str, Any]) -> dict[str, Any]:
    """Metadados de acesso. A query string não entra no catálogo."""

    href = str(asset.get("href") or "")
    https_href = str(_https_alternate(asset).get("href") or "")
    canonical = urlparse(href)
    https = urlparse(https_href)
    return {
        "canonical_scheme": canonical.scheme or None,
        "canonical_host": canonical.hostname,
        "canonical_path_present": bool(canonical.path),
        "auth_refs": list(asset.get("auth:refs") or []),
        "https_auth_refs": list(_https_alternate(asset).get("auth:refs") or []),
        "https_host": https.hostname,
        "https_path": https.path or None,
        "https_query_present": bool(https.query),
    }


def collection_auth_summary(collection: dict[str, Any]) -> dict[str, Any]:
    schemes = collection.get("auth:schemes") or {}
    storage = collection.get("storage:schemes") or {}
    compact_storage = {}
    for key, item in storage.items():
        if not isinstance(item, dict):
            continue
        compact_storage[key] = {
            "type": item.get("type"),
            "platform": item.get("platform"),
            "requester_pays": item.get("requester_pays"),
        }
    return {
        "collection_id": collection.get("id"),
        "auth_schemes": schemes,
        "storage_schemes": compact_storage,
    }


def describe_asset_response(
    *,
    http_status: int | None,
    authorization_sent: bool,
    scheme_names: list[str],
) -> str:
    """O status HTTP vale para a requisição feita. Não aponta um esquema ausente."""

    schemes = ", ".join(scheme_names) if scheme_names else "nenhum esquema listado"
    if authorization_sent:
        sent = "A requisição enviou Authorization."
    else:
        sent = "A requisição não enviou Authorization."
    if http_status is None:
        return (
            f"{sent} Não houve status HTTP. "
            f"A coleção declara: {schemes}."
        )
    return (
        f"{sent} O host HTTPS consultado respondeu HTTP {http_status}. "
        f"A coleção STAC declara os esquemas: {schemes}. "
        "O status descreve essa requisição e não separa os esquemas entre si."
    )
