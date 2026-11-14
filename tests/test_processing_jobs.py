"""Fundação de jobs: allowlist, caminhos, atomicidade e NDVI sintético."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from geoai.processing.contract import JobContractError, idempotency_key
from geoai.processing.jobs import PIPELINE_VERSION, execute_job
from geoai.processing.ndvi import (
    SENTINEL_SEARCH_POLICY,
    ndvi_window,
    resample_nearest,
    valid_mask_from_scl,
)

REPO = Path(__file__).resolve().parents[1]


def _run(tmp_path: Path, **kwargs):
    roots = kwargs.pop("allowed_roots", [tmp_path])
    return execute_job(
        allowed_roots=roots,
        jobs_dir=tmp_path / "jobs",
        **kwargs,
    )


def test_rejects_unknown_job_type(tmp_path: Path) -> None:
    with pytest.raises(JobContractError):
        _run(tmp_path, job_type="shell", source_id="x", params={})


def test_rejects_arbitrary_command_params(tmp_path: Path) -> None:
    with pytest.raises(JobContractError):
        _run(
            tmp_path,
            job_type="vector_bbox_metrics",
            source_id="x",
            params={"command": "calc.exe", "input_path": "a.geojson"},
        )


def test_rejects_path_outside_root(tmp_path: Path) -> None:
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    outside = tmp_path / "secret.geojson"
    outside.write_text("{}", encoding="utf-8")
    record = _run(
        tmp_path,
        job_type="vector_bbox_metrics",
        source_id="x",
        params={"input_path": str(outside)},
        allowed_roots=[allowed],
    )
    assert record.status == "failed"
    assert record.error_code == "invalid_input"
    written = list((tmp_path / "jobs").glob("*.json"))
    assert written
    outputs = [p for p in written if not p.name.endswith(".job.json")]
    assert outputs == []


def test_idempotency_reuses_published_output(tmp_path: Path) -> None:
    src = tmp_path / "tiny.geojson"
    src.write_text(
        (REPO / "tests" / "fixtures" / "processing" / "tiny_bbox.geojson").read_text(
            encoding="utf-8"
        ),
        encoding="utf-8",
    )
    params = {"input_path": str(src)}
    first = _run(
        tmp_path,
        job_type="vector_bbox_metrics",
        source_id="fixture.tiny",
        params=params,
    )
    second = _run(
        tmp_path,
        job_type="vector_bbox_metrics",
        source_id="fixture.tiny",
        params=params,
    )
    assert first.status == "succeeded"
    assert second.reused_previous is True
    assert first.idempotency_key == second.idempotency_key
    assert first.job_id == second.job_id
    body = json.loads(Path(first.output_paths[0]).read_text(encoding="utf-8"))
    assert body["result"]["n_features"] == 1
    assert body["result"]["bbox"] == [0.0, 0.0, 1.0, 1.0]


def test_failure_does_not_replace_validated_output(tmp_path: Path) -> None:
    src = tmp_path / "broken.geojson"
    src.write_text("{", encoding="utf-8")
    params = {"input_path": str(src)}
    key = idempotency_key(
        job_type="vector_bbox_metrics",
        source_id="broken",
        source_sha256=None,
        params=params,
        algorithm_ids=["napi.vector_bbox_metrics.v1"],
        pipeline_version=PIPELINE_VERSION,
    )
    jobs = tmp_path / "jobs"
    jobs.mkdir()
    sentinel = jobs / f"{key}.json"
    sentinel.write_text('{"ok": true}\n', encoding="utf-8")
    record = _run(
        tmp_path,
        job_type="vector_bbox_metrics",
        source_id="broken",
        params=params,
    )
    assert record.status == "failed"
    assert sentinel.read_text(encoding="utf-8") == '{"ok": true}\n'


def test_success_then_same_key_keeps_bytes(tmp_path: Path) -> None:
    src = tmp_path / "tiny.geojson"
    src.write_text(
        (REPO / "tests" / "fixtures" / "processing" / "tiny_bbox.geojson").read_text(
            encoding="utf-8"
        ),
        encoding="utf-8",
    )
    first = _run(
        tmp_path,
        job_type="vector_bbox_metrics",
        source_id="fixture.tiny",
        params={"input_path": str(src)},
    )
    digest = Path(first.output_paths[0]).read_bytes()
    second = _run(
        tmp_path,
        job_type="vector_bbox_metrics",
        source_id="fixture.tiny",
        params={"input_path": str(src)},
    )
    assert second.reused_previous is True
    assert Path(first.output_paths[0]).read_bytes() == digest


def test_ndvi_window_masks_invalid_and_does_not_invent_zero() -> None:
    b04 = [[0.1, 0.2], [0.0, None]]
    b08 = [[0.3, 0.2], [0.0, 0.4]]
    scl = [[4, 8], [0, 4]]
    mask = valid_mask_from_scl(resample_nearest(scl, 2, 2))
    grid = ndvi_window(b04, b08, valid=mask)
    assert grid[0][0] == pytest.approx(0.5)
    assert grid[0][1] is None
    assert grid[1][0] is None
    assert grid[1][1] is None
    assert SENTINEL_SEARCH_POLICY["download_in_this_release"] is False


def test_scl_nearest_does_not_blend_classes() -> None:
    scl = [[4, 8], [9, 4]]
    out = resample_nearest(scl, 4, 4)
    assert out[0][0] == 4
    assert out[0][3] == 8
    assert out[3][0] == 9
    assert out[3][3] == 4
    assert all(cell in {4, 8, 9} for row in out for cell in row)


def test_streamlit_does_not_import_qgis_or_run_jobs() -> None:
    banned = (
        "import qgis",
        "from qgis",
        "QgsApplication",
        "processing.run",
        "execute_job",
        "sentinel2_ndvi_window",
    )
    roots = [REPO / "app", REPO / "geoai" / "portal"]
    for root in roots:
        for path in root.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            for token in banned:
                assert token not in text, f"{path} contém {token}"
