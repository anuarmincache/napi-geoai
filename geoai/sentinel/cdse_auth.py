"""Acesso OIDC/OData do Copernicus Data Space. Não grava segredo."""

from __future__ import annotations

import json
import os
import re
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
PRODUCT_PREFIX = "/odata/v1/Products("
PROBE_BYTES = 1024
MAX_REDIRECTS = 2
REQUESTED_RANGE_START = 0
REQUESTED_RANGE_END = PROBE_BYTES - 1
_CONTENT_RANGE_RE = re.compile(r"bytes (\d+)-(\d+)/(\d+|\*)\Z")


class RedirectRefused(Exception):
    """O destino do redirecionamento não é um asset OData oficial."""

    def __init__(self, status: int) -> None:
        self.status = status
        super().__init__("redirect_recusado")


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
    path = parsed.path
    official = path.startswith(PRODUCT_PREFIX) and path.endswith("/$value")
    if not official:
        raise ValueError("o caminho precisa ser o $value de um produto OData")


def assert_token_endpoint(url: str) -> None:
    if url != TOKEN_ENDPOINT:
        raise ValueError("token endpoint diferente do oficial")


class _GuardedRedirect(urllib.request.HTTPRedirectHandler):
    """Segue no máximo dois redirecionamentos, só para outro asset OData."""

    max_redirections = MAX_REDIRECTS
    max_repeats = MAX_REDIRECTS

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        if code not in (301, 302, 303, 307, 308):
            raise RedirectRefused(int(code))
        try:
            assert_odata_asset_url(newurl)
        except ValueError:
            raise RedirectRefused(int(code)) from None
        authorization = req.get_header("Authorization")
        if not authorization:
            raise RedirectRefused(int(code))
        range_header = req.get_header("Range") or f"bytes=0-{PROBE_BYTES - 1}"
        return urllib.request.Request(
            newurl,
            headers={"Authorization": authorization, "Range": range_header},
            method="GET",
        )


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        raise RedirectRefused(int(code))


def content_range_matches_request(
    content_range: str | None,
    *,
    content_length: str | None,
    bytes_read: int,
    requested_start: int = REQUESTED_RANGE_START,
    requested_end: int = REQUESTED_RANGE_END,
) -> bool:
    """O intervalo devolvido precisa caber no pedido e bater com os bytes lidos."""

    if content_range is None or requested_end < requested_start:
        return False
    if bytes_read <= 0 or bytes_read > PROBE_BYTES:
        return False
    match = _CONTENT_RANGE_RE.fullmatch(content_range.strip())
    if match is None:
        return False
    start = int(match.group(1))
    end = int(match.group(2))
    complete_raw = match.group(3)
    if start != requested_start or end < start or end > requested_end:
        return False
    span = end - start + 1
    if span != bytes_read:
        return False
    if complete_raw == "*":
        if end != requested_end:
            return False
    else:
        complete = int(complete_raw)
        if complete <= end:
            return False
        short_object = end != requested_end
        if short_object and complete != end + 1:
            return False
    if content_length is None or content_length == "":
        return True
    if not content_length.isdigit() or int(content_length) != span:
        return False
    return True


def classify_probe_response(
    *,
    http_status: int | None,
    content_range: str | None,
    content_length: str | None,
    bytes_read: int,
    requested_start: int = REQUESTED_RANGE_START,
    requested_end: int = REQUESTED_RANGE_END,
) -> dict[str, Any]:
    """Só HTTP 206 com o intervalo pedido honra o Range. HTTP 200 nunca honra."""

    ranged = http_status == 206 and content_range_matches_request(
        content_range,
        content_length=content_length,
        bytes_read=bytes_read,
        requested_start=requested_start,
        requested_end=requested_end,
    )
    if ranged:
        access_status = "authorized"
        range_honored = True
    elif http_status in (401, 403):
        access_status = "blocked_auth"
        range_honored = False
    elif http_status in (200, 206):
        access_status = "range_not_honored"
        range_honored = False
    else:
        access_status = "blocked_auth"
        range_honored = False
    return {
        "access_status": access_status,
        "range_honored": range_honored,
        "bytes_read": bytes_read,
    }


def _token_from_environment() -> str | None:
    flags = credential_flags()
    if flags["bearer_configured"]:
        return os.environ.get("CDSE_ACCESS_TOKEN", "").strip() or None
    if not flags["password_grant_configured"]:
        return None
    assert_token_endpoint(TOKEN_ENDPOINT)
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
    opener = urllib.request.build_opener(_NoRedirect)
    try:
        with opener.open(request, timeout=45) as response:
            payload = json.load(response)
    except RedirectRefused:
        raise PermissionError("token_redirect_recusado") from None
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
        "range_honored": False,
        "access_status": "blocked_auth",
    }


def authorized_probe(url: str) -> dict[str, Any]:
    """Lê no máximo PROBE_BYTES. Sem credencial, não chama a rede."""

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
    opener = urllib.request.build_opener(_GuardedRedirect)
    try:
        with opener.open(request, timeout=45) as response:
            chunk = response.read(PROBE_BYTES)
            content_range = response.headers.get("Content-Range")
            content_length = response.headers.get("Content-Length")
            status = int(response.status)
    except RedirectRefused as error:
        report["http_status"] = error.status
        report["redirect_refused"] = True
        report["access_status"] = "blocked_auth"
        return report
    except urllib.error.HTTPError as error:
        status = int(error.code)
        content_range = error.headers.get("Content-Range") if error.headers else None
        content_length = error.headers.get("Content-Length") if error.headers else None
        chunk = b""
    classified = classify_probe_response(
        http_status=status,
        content_range=content_range,
        content_length=content_length,
        bytes_read=len(chunk),
        requested_start=REQUESTED_RANGE_START,
        requested_end=REQUESTED_RANGE_END,
    )
    report["http_status"] = status
    report["bytes_read"] = classified["bytes_read"]
    report["range_honored"] = classified["range_honored"]
    report["access_status"] = classified["access_status"]
    report["content_range_present"] = bool(content_range)
    chunk = None
    return report
