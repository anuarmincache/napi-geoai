"""Localização de clientes PostgreSQL (PATH nativo ou WSL Ubuntu)."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class PgTool:
    name: str
    argv_prefix: tuple[str, ...]
    via_wsl: bool


def _wsl_distro() -> str:
    return os.environ.get("NAPI_WSL_DISTRO", "Ubuntu-24.04")


def find_pg_tool(name: str) -> PgTool | None:
    """Prefere binário no PATH; fallback para WSL Ubuntu se disponível."""
    local = shutil.which(name)
    if local:
        return PgTool(name=name, argv_prefix=(local,), via_wsl=False)

    wsl = shutil.which("wsl")
    if not wsl:
        return None
    distro = _wsl_distro()
    probe = subprocess.run(
        [wsl, "-d", distro, "--", "which", name],
        check=False,
        capture_output=True,
        text=True,
    )
    if probe.returncode != 0 or not probe.stdout.strip():
        return None
    return PgTool(
        name=name,
        argv_prefix=(wsl, "-d", distro, "--", name),
        via_wsl=True,
    )


def require_pg_tool(name: str) -> PgTool:
    tool = find_pg_tool(name)
    if tool is None:
        raise RuntimeError(
            f"Ferramenta {name!r} não encontrada no PATH nem no WSL "
            f"({_wsl_distro()}). No Ubuntu: sudo apt install postgresql-client-16"
        )
    return tool


def run_pg_tool(
    tool: PgTool,
    args: list[str],
    *,
    env: dict[str, str] | None = None,
    check: bool = True,
    binary: bool = False,
) -> subprocess.CompletedProcess[Any]:
    cmd = [*tool.argv_prefix, *args]
    merged = os.environ.copy()
    if env:
        merged.update(env)
    # WSL não herda env do Windows por padrão — propagar via WSLENV.
    if tool.via_wsl and env:
        keys = [k for k in env if k]
        if keys:
            existing = merged.get("WSLENV", "")
            parts = [p for p in existing.split(":") if p]
            for key in keys:
                token = f"{key}/u"
                if token not in parts and key not in parts:
                    parts.append(token)
            merged["WSLENV"] = ":".join(parts)
    result = subprocess.run(
        cmd,
        check=False,
        capture_output=True,
        text=not binary,
        env=merged,
    )
    if check and result.returncode != 0:
        raw_err = result.stderr or result.stdout or b""
        if isinstance(raw_err, bytes):
            err = raw_err.decode("utf-8", errors="replace").strip()
        else:
            err = str(raw_err).strip()
        raise RuntimeError(
            f"{tool.name} falhou (exit {result.returncode}): {err[:500]}"
        )
    return result


def parse_pg_tool_major(version_text: str) -> int:
    """Extrai major version de saída ``pg_dump (PostgreSQL) X.Y``."""
    match = re.search(r"\(PostgreSQL\)\s+(\d+)\.", version_text)
    if not match:
        match = re.search(r"(\d+)\.\d+", version_text)
    if not match:
        raise RuntimeError(f"não foi possível interpretar versão: {version_text!r}")
    return int(match.group(1))


def pg_tool_major(name: str) -> int:
    tool = require_pg_tool(name)
    result = run_pg_tool(tool, ["--version"], check=True)
    text = result.stdout or result.stderr or ""
    if isinstance(text, bytes):
        text = text.decode("utf-8", errors="replace")
    return parse_pg_tool_major(str(text))


def server_major_from_url(database_url: str) -> int:
    import psycopg

    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute("SHOW server_version_num")
            return int(cur.fetchone()[0]) // 10_000


def assert_pg_client_matches_server(
    database_url: str,
    *,
    tools: tuple[str, ...] = ("pg_dump", "pg_restore"),
) -> None:
    """Garante major do cliente = major do servidor (evita transaction_timeout etc.)."""
    server_major = server_major_from_url(database_url)
    mismatches: list[str] = []
    for name in tools:
        try:
            client_major = pg_tool_major(name)
        except RuntimeError as exc:
            mismatches.append(f"{name}: {exc}")
            continue
        if client_major != server_major:
            mismatches.append(
                f"{name} major={client_major} != server major={server_major}"
            )
    if mismatches:
        raise RuntimeError(
            "cliente PostgreSQL incompatível com o servidor: "
            + "; ".join(mismatches)
            + ". Instale postgresql-client-"
            + str(server_major)
            + " (ou alinhe PATH a /usr/lib/postgresql/"
            + str(server_major)
            + "/bin)."
        )


def to_wsl_path(path: Path) -> str:
    """Converte caminho Windows para /mnt/... quando o tool roda via WSL."""
    resolved = path.resolve()
    s = str(resolved)
    if len(s) >= 2 and s[1] == ":":
        drive = s[0].lower()
        rest = s[2:].replace("\\", "/")
        return f"/mnt/{drive}{rest}"
    return s.replace("\\", "/")


def wsl_write_bytes(remote_path: str, data: bytes) -> None:
    """Grava bytes em um caminho do filesystem Linux via WSL stdin."""
    wsl = shutil.which("wsl")
    if not wsl:
        raise RuntimeError("wsl não encontrado")
    distro = _wsl_distro()
    result = subprocess.run(
        [wsl, "-d", distro, "--", "bash", "-c", f"cat > {remote_path}"],
        input=data,
        check=False,
        capture_output=True,
    )
    if result.returncode != 0:
        err = result.stderr.decode("utf-8", errors="replace")
        raise RuntimeError(f"falha ao gravar {remote_path} no WSL: {err[:300]}")


def wsl_read_bytes(remote_path: str) -> bytes:
    wsl = shutil.which("wsl")
    if not wsl:
        raise RuntimeError("wsl não encontrado")
    distro = _wsl_distro()
    result = subprocess.run(
        [wsl, "-d", distro, "--", "cat", remote_path],
        check=False,
        capture_output=True,
    )
    if result.returncode != 0:
        err = result.stderr.decode("utf-8", errors="replace")
        raise RuntimeError(f"falha ao ler {remote_path} no WSL: {err[:300]}")
    return result.stdout


def wsl_rm(remote_path: str) -> None:
    wsl = shutil.which("wsl")
    if not wsl:
        return
    distro = _wsl_distro()
    subprocess.run(
        [wsl, "-d", distro, "--", "rm", "-f", remote_path],
        check=False,
        capture_output=True,
    )
