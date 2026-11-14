"""Executor local de jobs leves. PyQGIS permanece em scripts/, fora do Streamlit."""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from pathlib import Path
from typing import Any

from geoai.processing.contract import (
    JobContractError,
    JobRecord,
    idempotency_key,
    utc_now,
    validate_job_request,
)
from geoai.processing.ndvi import (
    ndvi_summary,
    ndvi_window,
    resample_nearest,
    valid_mask_from_scl,
)
from geoai.processing.safety import atomic_write_json, resolve_allowed_path

PIPELINE_VERSION = "geo-foundation-1"


def sample_rss_mb() -> tuple[float | None, str]:
    """Amostra WorkingSet no Windows. None se a API não responder."""

    try:
        import ctypes
        from ctypes import wintypes

        class Counters(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        kernel = ctypes.WinDLL("kernel32")
        psapi = ctypes.WinDLL("psapi")
        get_info = psapi.GetProcessMemoryInfo
        get_info.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(Counters),
            wintypes.DWORD,
        ]
        get_info.restype = wintypes.BOOL
        counters = Counters()
        counters.cb = ctypes.sizeof(Counters)
        ok = get_info(kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb)
        if not ok:
            return None, "não medido: GetProcessMemoryInfo recusou"
        return counters.PeakWorkingSetSize / (1024 * 1024), (
            "PeakWorkingSetSize do processo (vida do processo, não só o job)"
        )
    except Exception as exc:  # noqa: BLE001
        return None, f"não medido: {type(exc).__name__}"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _vector_bbox_metrics(path: Path) -> dict[str, Any]:
    """Lê GeoJSON preparado e devolve contagem + bbox. Não recalcula área oficial."""

    payload = json.loads(path.read_text(encoding="utf-8"))
    features = payload.get("features") or []
    minx = miny = float("inf")
    maxx = maxy = float("-inf")
    n = 0
    for feature in features:
        geom = (feature or {}).get("geometry") or {}
        coords = geom.get("coordinates")
        if coords is None:
            continue
        n += 1
        stack = [coords]
        while stack:
            item = stack.pop()
            if (
                isinstance(item, list)
                and len(item) >= 2
                and isinstance(item[0], (int, float))
            ):
                x, y = float(item[0]), float(item[1])
                minx, miny = min(minx, x), min(miny, y)
                maxx, maxy = max(maxx, x), max(maxy, y)
            elif isinstance(item, list):
                stack.extend(item)
    if n == 0:
        extent = None
    else:
        extent = [minx, miny, maxx, maxy]
    return {
        "n_features": n,
        "bbox": extent,
        "note": (
            "BBox do GeoJSON de apresentação. Não substitui AREA_KM2 oficial "
            "nem um join QGIS."
        ),
    }


def _ndvi_from_params(params: dict[str, Any]) -> dict[str, Any]:
    b04 = params.get("b04")
    b08 = params.get("b08")
    if not isinstance(b04, list) or not isinstance(b08, list):
        raise JobContractError("b04 e b08 devem ser grades numéricas")
    scl = params.get("scl")
    valid = None
    if scl is not None:
        if not isinstance(scl, list):
            raise JobContractError("scl deve ser grade categórica")
        target_rows = len(b04)
        target_cols = len(b04[0]) if b04 else 0
        scl_grid = resample_nearest(scl, target_rows, target_cols)
        valid = valid_mask_from_scl(scl_grid)
    grid = ndvi_window(b04, b08, valid=valid)
    summary = ndvi_summary(grid)
    summary["grid"] = grid
    summary["scl_resample"] = "nearest" if scl is not None else None
    return summary


def execute_job(
    *,
    job_type: str,
    source_id: str,
    params: dict[str, Any],
    allowed_roots: list[Path],
    jobs_dir: Path,
    source_uri: str = "",
    source_sha256: str | None = None,
    source_date: str | None = None,
    input_paths: list[str] | None = None,
    algorithm_ids: list[str] | None = None,
) -> JobRecord:
    """Executa um job da allowlist e publica o JSON só após sucesso."""

    validate_job_request(job_type=job_type, params=params)
    algorithms = list(algorithm_ids or _default_algorithms(job_type))
    key = idempotency_key(
        job_type=job_type,
        source_id=source_id,
        source_sha256=source_sha256,
        params=params,
        algorithm_ids=algorithms,
        pipeline_version=PIPELINE_VERSION,
    )
    jobs_dir = Path(jobs_dir)
    jobs_dir.mkdir(parents=True, exist_ok=True)
    out_path = jobs_dir / f"{key}.json"
    record_path = jobs_dir / f"{key}.job.json"

    if out_path.is_file() and record_path.is_file():
        previous = json.loads(record_path.read_text(encoding="utf-8"))
        same_key = previous.get("idempotency_key") == key
        if previous.get("status") == "succeeded" and same_key:
            previous["reused_previous"] = True
            return JobRecord(**_filter_record(previous))

    record = JobRecord(
        job_id=uuid.uuid4().hex,
        job_type=job_type,
        created_at_utc=utc_now(),
        status="running",
        started_at_utc=utc_now(),
        source_id=source_id,
        source_uri=source_uri,
        source_date=source_date,
        source_sha256=source_sha256,
        input_paths=list(input_paths or []),
        params=params,
        algorithm_ids=algorithms,
        idempotency_key=key,
        pipeline_version=PIPELINE_VERSION,
    )
    started = time.perf_counter()
    try:
        if job_type == "vector_bbox_metrics":
            rel = params.get("input_path")
            if not isinstance(rel, str) or not rel:
                raise JobContractError("input_path obrigatório")
            path = resolve_allowed_path(Path(rel), roots=allowed_roots)
            record.input_bytes = path.stat().st_size
            record.input_paths = [str(path)]
            result = _vector_bbox_metrics(path)
            record.spatial_extent = result.get("bbox")
            record.crs = params.get("declared_crs")
        elif job_type == "sentinel2_ndvi_window":
            result = _ndvi_from_params(params)
            record.warnings.append(
                "Janela sintética ou fornecida em memória. Não é cena Sentinel baixada."
            )
        else:
            raise JobContractError(f"job_type não implementado: {job_type}")
        payload = {
            "idempotency_key": key,
            "job_type": job_type,
            "source_id": source_id,
            "result": result,
        }
        nbytes = atomic_write_json(out_path, payload)
        record.output_paths = [str(out_path)]
        record.output_sha256 = {str(out_path): _sha256_file(out_path)}
        record.output_bytes = nbytes
        record.status = "succeeded"
    except JobContractError as exc:
        record.status = "failed"
        record.error_code = "invalid_input"
        record.error_message = str(exc)
    except Exception as exc:  # noqa: BLE001
        record.status = "failed"
        record.error_code = "job_failed"
        record.error_message = f"{type(exc).__name__}: {exc}"
    record.finished_at_utc = utc_now()
    record.elapsed_seconds = round(time.perf_counter() - started, 6)
    rss, note = sample_rss_mb()
    record.peak_rss_mb = None if rss is None else round(rss, 3)
    record.rss_note = note
    if record.status != "succeeded" and _published_success(record_path, key):
        record.warnings.append(
            "falha não substituiu o resultado validado da mesma chave"
        )
        return record
    atomic_write_json(record_path, record.to_dict())
    return record


def _published_success(record_path: Path, key: str) -> bool:
    if not record_path.is_file():
        return False
    try:
        previous = json.loads(record_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    return (
        previous.get("status") == "succeeded"
        and previous.get("idempotency_key") == key
    )


def _default_algorithms(job_type: str) -> list[str]:
    if job_type == "vector_bbox_metrics":
        return ["napi.vector_bbox_metrics.v1"]
    return ["napi.sentinel2_ndvi_window.v1", "napi.scl_nearest.v1"]


def _filter_record(payload: dict[str, Any]) -> dict[str, Any]:
    allowed = set(JobRecord.__dataclass_fields__)
    return {key: value for key, value in payload.items() if key in allowed}
