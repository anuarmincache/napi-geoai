#!/usr/bin/env python3
"""Operações de robustez PostGIS: doctor, backup, restore-verify, security-audit."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from geoai.db.backup import (  # noqa: E402
    create_backup,
    summarize_restore,
    verify_restore,
)
from geoai.db.config import require_database_url  # noqa: E402
from geoai.db.doctor import format_doctor_report, run_doctor  # noqa: E402
from geoai.db.security_audit import (  # noqa: E402
    format_security_report,
    run_security_audit,
)
from geoai.db.url_safety import redact_database_url  # noqa: E402


def cmd_doctor(args: argparse.Namespace) -> int:
    cfg = require_database_url()
    report = run_doctor(cfg)
    print(format_doctor_report(report, as_json=args.json))
    return report.exit_code


def cmd_backup(args: argparse.Namespace) -> int:
    cfg = require_database_url()
    out = Path(args.output_dir)
    result = create_backup(cfg, output_dir=out, filename=args.filename)
    print(
        json.dumps(
            {
                "dump_path": str(result.dump_path),
                "manifest_path": str(result.manifest_path),
                "sha256": result.sha256,
                "bytes": result.bytes,
                "source_db": result.source_db,
                "created_at": result.created_at,
                "database_url": redact_database_url(cfg.database_url),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def cmd_restore_verify(args: argparse.Namespace) -> int:
    cfg = require_database_url()
    dump = Path(args.dump)
    if not dump.is_file():
        print(f"dump ausente: {dump}", file=sys.stderr)
        return 2
    result = verify_restore(
        cfg,
        dump_path=dump,
        keep_temp=args.keep_temp,
        temp_suffix=args.temp_suffix,
    )
    print(
        json.dumps(
            summarize_restore(result, primary_url=cfg.database_url),
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if result.match else 2


def cmd_security(args: argparse.Namespace) -> int:
    cfg = require_database_url()
    report = run_security_audit(
        cfg,
        repo_root=ROOT,
        backup_dir=Path(args.backup_dir) if args.backup_dir else ROOT / "backups",
    )
    print(format_security_report(report, as_json=args.json))
    if any(f.severity == "crit" for f in report.findings):
        return 2
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_doc = sub.add_parser("doctor", help="Diagnóstico não destrutivo")
    p_doc.add_argument("--json", action="store_true")
    p_doc.set_defaults(func=cmd_doctor)

    p_bak = sub.add_parser("backup", help="pg_dump -Fc para diretório local")
    p_bak.add_argument(
        "--output-dir",
        default=str(ROOT / "backups"),
        help="Diretório fora do Git (padrão: ./backups)",
    )
    p_bak.add_argument("--filename", default=None)
    p_bak.set_defaults(func=cmd_backup)

    p_rv = sub.add_parser(
        "restore-verify",
        help="Restaura dump em banco temporário e compara com a origem",
    )
    p_rv.add_argument("--dump", required=True, help="Caminho do arquivo .dump")
    p_rv.add_argument(
        "--keep-temp",
        action="store_true",
        help="Não remove o banco temporário (apenas debug)",
    )
    p_rv.add_argument("--temp-suffix", default=None)
    p_rv.set_defaults(func=cmd_restore_verify)

    p_sec = sub.add_parser(
        "security-audit",
        help="Auditoria local somente leitura (não altera configs)",
    )
    p_sec.add_argument("--json", action="store_true")
    p_sec.add_argument("--backup-dir", default=None)
    p_sec.set_defaults(func=cmd_security)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
