"""Fundação de jobs: allowlist, caminhos, atomicidade e NDVI sintético."""

from __future__ import annotations

import hashlib
import json
import threading
from pathlib import Path

import pytest
from geoai.processing.contract import JobContractError, idempotency_key
from geoai.processing.jobs import (
    PIPELINE_VERSION,
    _load_verified_publication,
    _sha256_file,
    execute_job,
)
from geoai.processing.ndvi import (
    SENTINEL_SEARCH_POLICY,
    ndvi_window,
    resample_nearest,
    valid_mask_from_scl,
)
from geoai.processing.safety import atomic_write_json

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
        source_sha256=hashlib.sha256(b"{").hexdigest(),
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
    mask = valid_mask_from_scl(
        resample_nearest(scl, 2, 2, allow_index_only=True)
    )
    grid = ndvi_window(b04, b08, valid=mask)
    assert grid[0][0] == pytest.approx(0.5)
    assert grid[0][1] is None
    assert grid[1][0] is None
    assert grid[1][1] is None
    assert SENTINEL_SEARCH_POLICY["download_in_this_release"] is False
    assert SENTINEL_SEARCH_POLICY["operational_sentinel"] is False


def test_scl_nearest_does_not_blend_classes() -> None:
    scl = [[4, 8], [9, 4]]
    out = resample_nearest(scl, 4, 4, allow_index_only=True)
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


def _tiny(tmp_path: Path) -> Path:
    src = tmp_path / "tiny.geojson"
    src.write_text(
        (REPO / "tests" / "fixtures" / "processing" / "tiny_bbox.geojson").read_text(
            encoding="utf-8"
        ),
        encoding="utf-8",
    )
    return src


def test_same_path_new_bytes_is_not_reused(tmp_path: Path) -> None:
    src = _tiny(tmp_path)
    params = {"input_path": str(src)}
    first = _run(
        tmp_path,
        job_type="vector_bbox_metrics",
        source_id="fixture.tiny",
        params=params,
    )
    src.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {},
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [[[0, 0], [2, 0], [2, 2], [0, 0]]],
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    second = _run(
        tmp_path,
        job_type="vector_bbox_metrics",
        source_id="fixture.tiny",
        params=params,
    )
    assert first.status == "succeeded"
    assert second.status == "succeeded"
    assert second.reused_previous is False
    assert second.idempotency_key != first.idempotency_key
    assert second.source_sha256 != first.source_sha256
    fresh = json.loads(Path(second.output_paths[0]).read_text(encoding="utf-8"))
    assert fresh["result"]["bbox"] == [0.0, 0.0, 2.0, 2.0]
    old = json.loads(Path(first.output_paths[0]).read_text(encoding="utf-8"))
    assert old["result"]["bbox"] == [0.0, 0.0, 1.0, 1.0]


def test_declared_sha_must_match_file(tmp_path: Path) -> None:
    src = _tiny(tmp_path)
    record = _run(
        tmp_path,
        job_type="vector_bbox_metrics",
        source_id="fixture.tiny",
        params={"input_path": str(src)},
        source_sha256="0" * 64,
    )
    assert record.status == "failed"
    assert record.error_code == "invalid_input"
    assert record.output_paths == []


def test_truncated_or_tampered_cache_is_recomputed(tmp_path: Path) -> None:
    src = _tiny(tmp_path)
    params = {"input_path": str(src)}
    kwargs = {
        "job_type": "vector_bbox_metrics",
        "source_id": "fixture.tiny",
        "params": params,
    }
    first = _run(tmp_path, **kwargs)
    out = Path(first.output_paths[0])
    manifest = out.with_name(out.name.replace(".json", ".job.json"))
    out.write_text("{", encoding="utf-8")
    rerun = _run(tmp_path, **kwargs)
    assert rerun.reused_previous is False
    assert rerun.status == "succeeded"
    body = json.loads(out.read_text(encoding="utf-8"))
    assert body["result"]["n_features"] == 1
    assert body["idempotency_key"] == first.idempotency_key
    recorded = json.loads(manifest.read_text(encoding="utf-8"))
    recorded["output_sha256"] = {str(out): "0" * 64}
    manifest.write_text(json.dumps(recorded), encoding="utf-8")
    again = _run(tmp_path, **kwargs)
    assert again.reused_previous is False
    assert _sha256_file(out) != "0" * 64
    checked = json.loads(manifest.read_text(encoding="utf-8"))
    assert checked["output_sha256"][str(out)] == _sha256_file(out)


def test_invalid_geojson_does_not_publish_bbox(tmp_path: Path) -> None:
    src = tmp_path / "bad.geojson"
    src.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "geometry": {"type": "Point", "coordinates": ["x", "y"]},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    record = _run(
        tmp_path,
        job_type="vector_bbox_metrics",
        source_id="bad",
        params={"input_path": str(src)},
    )
    assert record.status == "failed"
    assert record.error_code == "invalid_input"
    assert record.output_paths == []
    empty = tmp_path / "empty.geojson"
    empty.write_text(
        json.dumps({"type": "FeatureCollection", "features": []}),
        encoding="utf-8",
    )
    empty_record = _run(
        tmp_path,
        job_type="vector_bbox_metrics",
        source_id="empty",
        params={"input_path": str(empty)},
    )
    assert empty_record.status == "failed"
    assert empty_record.output_paths == []


def test_ndvi_rejects_empty_grid_and_mask_shape() -> None:
    with pytest.raises(ValueError, match="incompatível|vazia"):
        ndvi_window([], [])
    with pytest.raises(ValueError, match="vazia"):
        ndvi_window([[]], [[]])
    with pytest.raises(ValueError, match="máscara"):
        ndvi_window([[0.1, 0.2]], [[0.2, 0.3]], valid=[[True]])


def test_resample_nearest_refuses_real_scene_inputs() -> None:
    grid = [[4, 8], [9, 4]]
    with pytest.raises(ValueError, match="allow_index_only"):
        resample_nearest(grid, 2, 2)
    with pytest.raises(ValueError, match="geotransform"):
        resample_nearest(
            grid,
            2,
            2,
            allow_index_only=True,
            geotransform=(0, 10, 0, 0, 0, -10),
            crs="EPSG:4326",
        )


def test_concurrent_atomic_write_keeps_one_valid_json(tmp_path: Path) -> None:
    dest = tmp_path / "out.json"
    errors: list[BaseException] = []

    def _write(index: int) -> None:
        try:
            atomic_write_json(dest, {"i": index, "pad": "x" * 200})
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=_write, args=(i,)) for i in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert errors == []
    body = json.loads(dest.read_text(encoding="utf-8"))
    assert body["i"] in range(8)
    assert list(tmp_path.glob("*.partial")) == []


def test_invalid_payload_preserves_destination(tmp_path: Path) -> None:
    dest = tmp_path / "out.json"
    dest.write_text('{"ok": true}\n', encoding="utf-8")
    with pytest.raises(JobContractError):
        atomic_write_json(dest, ["nao-objeto"])  # type: ignore[arg-type]
    assert dest.read_text(encoding="utf-8") == '{"ok": true}\n'
    assert list(tmp_path.glob("*.partial")) == []


def test_two_jobs_same_key_publish_consistent_pair(tmp_path: Path) -> None:
    src = _tiny(tmp_path)
    params = {"input_path": str(src)}
    barrier = threading.Barrier(2)
    records: list = []
    errors: list[BaseException] = []

    def _run_one() -> None:
        try:
            barrier.wait(timeout=5)
            records.append(
                _run(
                    tmp_path,
                    job_type="vector_bbox_metrics",
                    source_id="fixture.tiny",
                    params=params,
                )
            )
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=_run_one) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert errors == []
    assert len(records) == 2
    assert all(item.status == "succeeded" for item in records)
    assert records[0].idempotency_key == records[1].idempotency_key
    assert sum(bool(item.reused_previous) for item in records) == 1
    out = Path(records[0].output_paths[0])
    manifest = tmp_path / "jobs" / f"{records[0].idempotency_key}.job.json"
    verified = _load_verified_publication(
        manifest, out, records[0].idempotency_key
    )
    assert verified is not None
    assert verified["output_sha256"][str(out)] == _sha256_file(out)
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["idempotency_key"] == records[0].idempotency_key
    assert payload["source_sha256"] == records[0].source_sha256
    assert payload["result"]["n_features"] == 1
    assert list((tmp_path / "jobs").glob("*.lock")) == []


def test_input_change_between_hash_and_read_does_not_publish(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    src = _tiny(tmp_path)
    original = src.read_bytes()
    other = json.dumps(
        {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [9, 9]},
                }
            ],
        }
    ).encode("utf-8")
    calls = {"n": 0}

    def _flip(path: Path) -> bytes:
        calls["n"] += 1
        if calls["n"] == 1:
            return original
        return other

    monkeypatch.setattr("geoai.processing.jobs._read_input_bytes", _flip)
    record = _run(
        tmp_path,
        job_type="vector_bbox_metrics",
        source_id="fixture.tiny",
        params={"input_path": str(src)},
    )
    assert record.status == "failed"
    assert record.error_code == "invalid_input"
    assert "mudou" in (record.error_message or "")
    published = [
        path
        for path in (tmp_path / "jobs").glob("*.json")
        if not path.name.endswith(".job.json")
    ]
    assert published == []
    assert list((tmp_path / "jobs").glob("*.lock")) == []
