"""Orquestra validação municipal via QGIS (local).

Preferências de execução (fail-closed se nenhuma funcionar):
1. ``python-qgis-ltr.bat scripts/_qgis_mun_worker.py`` (PyQGIS do Desktop)
2. QGIS MCP ``execute_code`` (quando o Desktop está aberto)

Não importar PyQGIS no Streamlit Cloud. O relatório versionado
``data/derived/parana_municipios_2025_qgis_report.json`` é a evidência CI.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from geoai.qgis.discover import discover_qgis  # noqa: E402
from geoai.qgis.municipal_report import (  # noqa: E402
    load_qgis_municipal_report,
    report_path,
    validate_qgis_report_contract,
)


def _run_worker_via_python_bat() -> int:
    install = discover_qgis()
    if install is None or install.python_bat is None:
        print("QGIS python-qgis*.bat não encontrado.", file=sys.stderr)
        return 2
    worker = REPO / "scripts" / "_qgis_mun_worker.py"
    cmd = [str(install.python_bat), str(worker)]
    print("exec:", " ".join(cmd))
    completed = subprocess.run(cmd, cwd=str(REPO), check=False)
    return int(completed.returncode)


def main() -> int:
    print(f"repo={REPO}")
    install = discover_qgis()
    print(f"qgis_install={install}")
    code = _run_worker_via_python_bat()
    report = load_qgis_municipal_report(REPO)
    if report is None:
        print(
            "Relatório ausente após tentativa local. "
            "Abra o QGIS Desktop + MCP e rode o worker via execute_code, "
            f"ou verifique Device Guard bloqueando {install}.",
            file=sys.stderr,
        )
        return code if code else 3
    problems = validate_qgis_report_contract(report)
    out = report_path(REPO)
    print(f"report={out}")
    summary = {"contract_problems": problems, "engine": report.get("engine")}
    print(json.dumps(summary, indent=2))
    if problems:
        return 4
    return 0 if code == 0 else code


if __name__ == "__main__":
    raise SystemExit(main())
