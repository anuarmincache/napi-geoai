"""Mede uma operação espacial pequena e grava o JSON de evidência.

Não define SLA. Se a memória não puder ser lida, o campo fica nulo e a nota
explica o motivo.
"""

from __future__ import annotations

import json
import platform
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from geoai.processing.jobs import execute_job  # noqa: E402


def main() -> int:
    fixture = REPO / "tests" / "fixtures" / "processing" / "tiny_bbox.geojson"
    jobs = REPO / "data" / "jobs"
    record = execute_job(
        job_type="vector_bbox_metrics",
        source_id="tests.fixtures.processing.tiny_bbox.v2",
        source_uri=str(fixture.relative_to(REPO)).replace("\\", "/"),
        params={"input_path": str(fixture), "declared_crs": None},
        allowed_roots=[REPO / "tests" / "fixtures"],
        jobs_dir=jobs,
    )
    payload = {
        "operation": "vector_bbox_metrics",
        "fixture": "tests/fixtures/processing/tiny_bbox.geojson",
        "status": record.status,
        "elapsed_seconds": record.elapsed_seconds,
        "peak_rss_mb": record.peak_rss_mb,
        "rss_note": record.rss_note,
        "input_bytes": record.input_bytes,
        "output_bytes": record.output_bytes,
        "n_features": None,
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "pipeline_version": record.pipeline_version,
        "qgis_executed": False,
    }
    if record.status == "succeeded":
        body = json.loads(Path(record.output_paths[0]).read_text(encoding="utf-8"))
        payload["n_features"] = body["result"]["n_features"]
    out = REPO / "docs" / "evidence" / "processing" / "benchmark_small.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(out)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if record.status == "succeeded" else 1


if __name__ == "__main__":
    raise SystemExit(main())
