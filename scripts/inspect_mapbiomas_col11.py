"""Baixa a tabela municipal MapBiomas Coleção 11 e registra a sua estrutura.

Uso (na raiz do repositório):
  python scripts/inspect_mapbiomas_col11.py

Primeira etapa do contrato em docs/MAPBIOMAS_COLECAO11.md: o layout das
colunas só é fixado com o arquivo aberto. Este script não calcula indicador
e não grava nada em data/derived. Ele salva o .xlsx em data/raw/mapbiomas/
(fora do Git), calcula SHA-256 e tamanho, e descreve abas, cabeçalhos e
amostras em data/raw/mapbiomas/inspecao_col11.json.

O link vem da página oficial de estatísticas (botão "Baixar" da linha
"Biomas, Estados e Municípios | Cobertura 30m - Coleção 11"), lido em
2026-11-19. Se o download automático falhar, baixe o arquivo pelo navegador
nessa página e salve com o nome esperado na pasta indicada.
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from geoai.landcover.mapbiomas_col11 import (  # noqa: E402
    EXPECTED_FILENAME,
    STATISTICS_PAGE,
)

DRIVE_FILE_ID = "1otOqymHuixvkRGVl65zTTNyfaHo46Gqk"
OFFICIAL_LINK = f"https://drive.google.com/uc?id={DRIVE_FILE_ID}&export=download"
CANDIDATE_URLS = (
    OFFICIAL_LINK,
    "https://drive.usercontent.google.com/download"
    f"?id={DRIVE_FILE_ID}&export=download&confirm=t",
)
RAW_DIR = REPO / "data" / "raw" / "mapbiomas"
TARGET = RAW_DIR / EXPECTED_FILENAME
REPORT = RAW_DIR / "inspecao_col11.json"
SAMPLE_ROWS = 6
SCAN_ROWS = 400_000


def _is_xlsx(path: Path) -> bool:
    with path.open("rb") as handle:
        return handle.read(4) == b"PK\x03\x04"


def _download() -> str | None:
    import httpx

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    partial = TARGET.with_suffix(".xlsx.partial")
    for url in CANDIDATE_URLS:
        print(f"tentando {url.split('?')[0]} …", flush=True)
        try:
            with httpx.Client(follow_redirects=True, timeout=600.0) as client:
                with client.stream("GET", url) as response:
                    response.raise_for_status()
                    with partial.open("wb") as handle:
                        for chunk in response.iter_bytes(1 << 20):
                            handle.write(chunk)
        except httpx.HTTPError as error:
            print(f"  falhou: {type(error).__name__}", flush=True)
            continue
        if _is_xlsx(partial):
            partial.replace(TARGET)
            return url
        print("  a resposta não é um .xlsx (página de confirmação?)", flush=True)
    return None


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _cell(value: object) -> object:
    if value is None or isinstance(value, (int, float, bool)):
        return value
    return str(value)[:120]


def _inspect() -> list[dict[str, object]]:
    from openpyxl import load_workbook

    workbook = load_workbook(TARGET, read_only=True, data_only=True)
    sheets = []
    for sheet in workbook.worksheets:
        rows = sheet.iter_rows(values_only=True)
        header = next(rows, None)
        samples = []
        scanned = 0
        distinct: dict[int, set[str]] = {}
        for row in rows:
            scanned += 1
            if len(samples) < SAMPLE_ROWS:
                samples.append([_cell(v) for v in row])
            # valores distintos das colunas de texto, para achar UF e bioma
            for index, value in enumerate(row[:40]):
                if isinstance(value, str):
                    bucket = distinct.setdefault(index, set())
                    if len(bucket) <= 60:
                        bucket.add(value[:60])
            if scanned >= SCAN_ROWS:
                break
        sheets.append(
            {
                "name": sheet.title,
                "declared_dimensions": sheet.calculate_dimension()
                if hasattr(sheet, "calculate_dimension")
                else None,
                "header": [_cell(v) for v in (header or [])],
                "rows_scanned": scanned,
                "scan_was_capped": scanned >= SCAN_ROWS,
                "sample_rows": samples,
                "text_columns_distinct_values": {
                    str(index): sorted(values)[:60]
                    for index, values in distinct.items()
                    if len(values) <= 60
                },
            }
        )
    workbook.close()
    return sheets


def main() -> int:
    used_url = None
    if TARGET.is_file() and _is_xlsx(TARGET):
        print(f"arquivo já presente: {TARGET.relative_to(REPO)}")
    else:
        used_url = _download()
        if used_url is None:
            print(
                "\nDownload automático não funcionou. Baixe pelo navegador em\n"
                f"  {STATISTICS_PAGE}\n"
                "(linha 'Biomas, Estados e Municípios | Cobertura 30m - Coleção "
                "11') e salve como\n"
                f"  {TARGET}\n"
                "Depois rode este script de novo."
            )
            return 2
    print("lendo a planilha (pode levar alguns minutos) …", flush=True)
    report = {
        "inspected_at_utc": datetime.now(UTC).isoformat(),
        "statistics_page": STATISTICS_PAGE,
        "official_link": OFFICIAL_LINK,
        "downloaded_from": used_url,
        "file_name": TARGET.name,
        "content_bytes": TARGET.stat().st_size,
        "content_sha256": _sha256(TARGET),
        "sheets": _inspect(),
    }
    REPORT.write_text(
        json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    print(f"gravado {REPORT.relative_to(REPO)}")
    print(f"bytes={report['content_bytes']} sha256={report['content_sha256']}")
    for sheet in report["sheets"]:
        print(
            f"aba «{sheet['name']}»: {len(sheet['header'])} colunas, "
            f"{sheet['rows_scanned']} linhas lidas"
        )
        print("  cabeçalho:", sheet["header"][:14])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
