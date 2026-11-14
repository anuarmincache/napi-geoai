"""Acesso OIDC/OData do Copernicus Data Space. Não grava segredo."""

from __future__ import annotations

import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

TOKEN_ENDPOINT = (
    "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/"
    "protocol/openid-connect/token"
)
PUBLIC_CLIENT_ID = "cdse-public"
DOWNLOAD_HOST = "download.dataspace.copernicus.eu"
# Um bloco curto. Não é o JP2.
PROBE_BYTES = 1024


def credential_flags() -> dict[str, bool]:
    """Só indica presença. Os valores não saem desta função."""

    user = os.environ.get("CDSE_USERNAME") or ""
    password = os.environ.get("CDSE_PASSWORD") or ""
    token = os.environ.get("CDSE_ACCESS_TOKEN") or ""
    return {
        "password_grant_configured": bool(user.strip() and password.strip()),
        "bearer_configured": bool(token.strip()),
    }


def assert_odata_asset_url(url: str) -> None:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != DOWNLOAD_HOST:
        raise ValueError("o asset precisa ser HTTPS no host OData oficial")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("a URL do asset não pode carregar segredo")


def _token_from_environment() -> str | None:
    flags = credential_flags()
    if flags["bearer_configured"]:
        return os.environ.get("CDSE_ACCESS_TOKEN", "").strip() or None
    if not flags["password_grant_configured"]:
        return None
    form = urllib.parse.urlencode(
        {
            "client_id": PUBLIC_CLIENT_ID,
            "username": os.environ.get("CDSE_USERNAME", ""),
            "password": os.environ.get("CDSE_PASSWORD", ""),
            "grant_type": "password",
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        TOKEN_ENDPOINT,
        data=form,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            import json

            payload = json.load(response)
    except urllib.error.HTTPError as error:
        raise PermissionError(f"token_endpoint_http_{error.code}") from None
    token = payload.get("access_token") if isinstance(payload, dict) else None
    if not isinstance(token, str) or not token:
        raise PermissionError("token_endpoint_sem_access_token")
    return token


def unattempted_report() -> dict[str, Any]:
    """Relatório sem rede. Não inclui usuário, senha nem token."""

    flags = credential_flags()
    return {
        "method": "oidc_odata",
        "token_endpoint": TOKEN_ENDPOINT,
        "public_client_id": PUBLIC_CLIENT_ID,
        "password_grant_configured": flags["password_grant_configured"],
        "bearer_configured": flags["bearer_configured"],
        "authorized_attempted": False,
        "authorization_sent": False,
        "http_status": None,
        "bytes_read": 0,
        "body_stored": False,
        "access_status": "blocked_auth",
    }


def authorized_probe(url: str) -> dict[str, Any]:
    """Lê no máximo PROBE_BYTES de um asset. Sem credencial, não chama a rede."""

    flags = credential_flags()
    report = unattempted_report()
    if not (flags["password_grant_configured"] or flags["bearer_configured"]):
        return report
    assert_odata_asset_url(url)
    token = _token_from_environment()
    if not token:
        return report
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Range": f"bytes=0-{PROBE_BYTES - 1}",
        },
        method="GET",
    )
    report["authorized_attempted"] = True
    report["authorization_sent"] = True
    token = None
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            chunk = response.read(PROBE_BYTES)
            report["http_status"] = int(response.status)
            report["bytes_read"] = len(chunk)
    except urllib.error.HTTPError as error:
        report["http_status"] = int(error.code)
        report["bytes_read"] = 0
    chunk = None
    if report["http_status"] is not None and 200 <= int(report["http_status"]) < 300:
        report["access_status"] = "authorized"
    else:
        report["access_status"] = "blocked_auth"
    return report
