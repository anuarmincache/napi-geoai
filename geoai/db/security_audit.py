"""Auditoria de segurança local — somente leitura; não altera configs globais."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

from geoai.db.config import DatabaseConfig
from geoai.db.url_safety import parse_database_url, redact_database_url

Severity = Literal["ok", "warn", "info", "crit"]


@dataclass
class SecurityFinding:
    name: str
    severity: Severity
    message: str
    recommendation: str = ""
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class SecurityReport:
    database_url_redacted: str
    findings: list[SecurityFinding]

    def to_dict(self) -> dict[str, Any]:
        return {
            "database_url": self.database_url_redacted,
            "findings": [asdict(f) for f in self.findings],
        }


def run_security_audit(
    cfg: DatabaseConfig,
    *,
    repo_root: Path | None = None,
    backup_dir: Path | None = None,
) -> SecurityReport:
    """
    Revisa exposição, privilégios e higiene de segredos.

    Não modifica ``postgresql.conf``, ``pg_hba.conf`` nem roles de outros
    projetos. Achados com mudança necessária vêm como *recommendation*.
    """
    try:
        import psycopg
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("psycopg não instalado") from exc

    findings: list[SecurityFinding] = []
    redacted = redact_database_url(cfg.database_url)
    parts = parse_database_url(cfg.database_url)
    root = repo_root or Path(__file__).resolve().parents[2]

    # --- higiene de repositório ---
    env_file = root / ".env"
    if env_file.is_file():
        findings.append(
            SecurityFinding(
                "dotenv_present",
                "info",
                ".env local presente (ok se no .gitignore)",
                "Nunca commitar .env; rotacionar senha se vazou.",
            )
        )
    gitignore = (root / ".gitignore").read_text(encoding="utf-8")
    if ".env" not in gitignore:
        findings.append(
            SecurityFinding(
                "gitignore_env",
                "crit",
                ".env não aparece no .gitignore",
                "Adicionar .env ao .gitignore.",
            )
        )
    else:
        findings.append(
            SecurityFinding("gitignore_env", "ok", ".env coberto pelo .gitignore")
        )
    if "backups/" not in gitignore and "*.dump" not in gitignore:
        findings.append(
            SecurityFinding(
                "gitignore_dumps",
                "warn",
                "dumps/backups podem não estar no .gitignore",
                "Ignorar backups/ e *.dump.",
            )
        )
    else:
        findings.append(
            SecurityFinding(
                "gitignore_dumps",
                "ok",
                "padrões de dump/backup presentes no .gitignore",
            )
        )

    # senha de exemplo conhecida do MVP04
    if parts.password in {"napi_local_dev_only", "napi_ci"}:
        findings.append(
            SecurityFinding(
                "example_password",
                "warn",
                "senha de exemplo/MVP em uso",
                "Rotacionar antes de qualquer exposição de rede ou compartilhamento.",
            )
        )

    if parts.host not in {None, "127.0.0.1", "localhost"}:
        findings.append(
            SecurityFinding(
                "host_not_loopback",
                "warn",
                f"host {parts.host!r} não é loopback",
                "Preferir 127.0.0.1 para desenvolvimento local.",
                {"host": parts.host},
            )
        )
    else:
        findings.append(
            SecurityFinding(
                "host_loopback",
                "ok",
                f"conexão via loopback ({parts.host or 'default'})",
            )
        )

    if parts.port == 5433:
        findings.append(
            SecurityFinding(
                "port_5433",
                "info",
                "porta 5433 (cluster WSL nativo deste ambiente)",
            )
        )

    bdir = backup_dir or (root / "backups")
    if bdir.is_dir():
        try:
            mode = bdir.stat().st_mode & 0o777
            if mode & 0o077:
                findings.append(
                    SecurityFinding(
                        "backup_dir_perms",
                        "warn",
                        f"backups/ permissões amplas ({oct(mode)})",
                        "chmod 700 no diretório de backups.",
                        {"mode": oct(mode)},
                    )
                )
            else:
                findings.append(
                    SecurityFinding(
                        "backup_dir_perms",
                        "ok",
                        "diretório de backups com permissões restritas",
                    )
                )
        except OSError:
            findings.append(
                SecurityFinding(
                    "backup_dir_perms",
                    "info",
                    "não foi possível ler permissões de backups/ (Windows comum)",
                )
            )

    with psycopg.connect(cfg.database_url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT current_user, session_user")
            current_user, session_user = cur.fetchone()
            findings.append(
                SecurityFinding(
                    "session_user",
                    "ok",
                    f"conectado como {current_user}",
                    details={
                        "current_user": current_user,
                        "session_user": session_user,
                    },
                )
            )

            cur.execute(
                """
                SELECT rolsuper, rolcreaterole, rolcreatedb
                FROM pg_roles
                WHERE rolname = current_user
                """
            )
            row = cur.fetchone()
            if row:
                superuser, createrole, createdb = row
                if superuser:
                    findings.append(
                        SecurityFinding(
                            "role_superuser",
                            "warn",
                            "role atual é superuser",
                            "Preferir role de aplicação sem superuser em produção.",
                        )
                    )
                else:
                    findings.append(
                        SecurityFinding(
                            "role_superuser",
                            "ok",
                            "role atual não é superuser",
                            details={
                                "rolcreaterole": createrole,
                                "rolcreatedb": createdb,
                            },
                        )
                    )

            # listen_addresses — pode exigir privilégio
            try:
                cur.execute("SHOW listen_addresses")
                listen = str(cur.fetchone()[0])
                if listen.strip() in {"localhost", "127.0.0.1"}:
                    findings.append(
                        SecurityFinding(
                            "listen_addresses",
                            "ok",
                            f"listen_addresses={listen}",
                        )
                    )
                elif listen.strip() == "*":
                    findings.append(
                        SecurityFinding(
                            "listen_addresses",
                            "warn",
                            "listen_addresses=* (todas interfaces)",
                            "Propor alteração para localhost se não houver necessidade "
                            "de acesso remoto. Não aplicar sem autorização "
                            "(pode afetar outros serviços).",
                            {"listen_addresses": listen},
                        )
                    )
                else:
                    findings.append(
                        SecurityFinding(
                            "listen_addresses",
                            "info",
                            f"listen_addresses={listen}",
                            "Revisar se o valor é o mínimo necessário.",
                            {"listen_addresses": listen},
                        )
                    )
            except Exception as exc:  # noqa: BLE001
                findings.append(
                    SecurityFinding(
                        "listen_addresses",
                        "info",
                        f"não foi possível ler listen_addresses: {type(exc).__name__}",
                    )
                )

            try:
                cur.execute(
                    """
                    SELECT type, database, user_name, address, auth_method
                    FROM pg_hba_file_rules
                    ORDER BY line_number
                    """
                )
                rules = [
                    {
                        "type": r[0],
                        "database": r[1],
                        "user": r[2],
                        "address": r[3],
                        "auth": r[4],
                    }
                    for r in cur.fetchall()
                ]
                risky = [
                    r
                    for r in rules
                    if r["auth"] in {"trust", "password"}
                    and (r["address"] not in {None, "127.0.0.1/32", "::1/128"})
                ]
                if risky:
                    findings.append(
                        SecurityFinding(
                            "pg_hba",
                            "warn",
                            f"{len(risky)} regra(s) potencialmente amplas",
                            "Propor endurecimento (scram-sha-256 + loopback) sem "
                            "alterar unilateralmente regras de outros projetos.",
                            {"risky_count": len(risky)},
                        )
                    )
                else:
                    findings.append(
                        SecurityFinding(
                            "pg_hba",
                            "ok",
                            (
                                f"{len(rules)} regra(s) pg_hba lidas; "
                                "sem trust remoto óbvio"
                            ),
                            details={"rule_count": len(rules)},
                        )
                    )
            except Exception as exc:  # noqa: BLE001
                findings.append(
                    SecurityFinding(
                        "pg_hba",
                        "info",
                        f"pg_hba_file_rules indisponível: {type(exc).__name__}",
                        "Revisar pg_hba.conf manualmente no WSL.",
                    )
                )

    findings.append(
        SecurityFinding(
            "supabase_policy",
            "ok",
            "política MVP05: não usar Supabase remoto nesta etapa",
        )
    )
    findings.append(
        SecurityFinding(
            "no_unilateral_global_changes",
            "info",
            "esta auditoria não altera postgresql.conf/pg_hba/roles globais",
            "Qualquer mudança de listen/hba deve ser proposta e aprovada antes.",
        )
    )

    return SecurityReport(database_url_redacted=redacted, findings=findings)


def format_security_report(report: SecurityReport, *, as_json: bool = False) -> str:
    if as_json:
        return json.dumps(report.to_dict(), ensure_ascii=False, indent=2)
    lines = [
        "db security-audit (somente leitura)",
        f"database: {report.database_url_redacted}",
        "",
    ]
    for f in report.findings:
        rec = f" → {f.recommendation}" if f.recommendation else ""
        lines.append(f"[{f.severity}] {f.name}: {f.message}{rec}")
    return "\n".join(lines)
