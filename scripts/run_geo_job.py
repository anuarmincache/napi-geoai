"""CLI de job geoespacial. Não é chamada pelo Streamlit.

Uso (uma linha):
py -3 scripts/run_geo_job.py --type vector_bbox_metrics --input CAMINHO
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from geoai.processing.jobs import execute_job  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Executa um job da allowlist NAPI")
    parser.add_argument("--type", required=True)
    parser.add_argument("--input", default="")
    parser.add_argument("--source-id", default="local.prepared_artifact")
    args = parser.parse_args(argv)
    roots = [REPO / "data" / "derived", REPO / "tests" / "fixtures"]
    params: dict[str, str] = {}
    if args.type == "vector_bbox_metrics":
        if not args.input:
            print("input obrigatório", file=sys.stderr)
            return 2
        params = {"input_path": str((REPO / args.input).resolve())}
    record = execute_job(
        job_type=args.type,
        source_id=args.source_id,
        params=params,
        allowed_roots=roots,
        jobs_dir=REPO / "data" / "jobs",
        source_uri=args.input,
    )
    print(json.dumps(record.to_dict(), ensure_ascii=False, indent=2))
    return 0 if record.status == "succeeded" else 1


if __name__ == "__main__":
    raise SystemExit(main())
