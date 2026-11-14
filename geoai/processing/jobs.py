"""Executor local de jobs leves. PyQGIS permanece em scripts/, fora do Streamlit."""

from __future__ import annotations

import hashlib
import json
import math
import time
import uuid
from pathlib import Path
from typing import Any

from geoai.processing.contract import (
    JobContractError,
    JobRecord,
    canonical_json,
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
from geoai.processing.safety import (
    atomic_write_json,
    exclusive_key_lock,
    resolve_allowed_path,
)

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


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _coordinate_pairs(coords: Any) -> list[tuple[float, float]]:
    if isinstance(coords, (str, bytes)) or not isinstance(coords, list):
        raise JobContractError("coordenada inválida")
    if (
        len(coords) >= 2
        and _is_number(coords[0])
        and _is_number(coords[1])
    ):
        x, y = float(coords[0]), float(coords[1])
        if not (math.isfinite(x) and math.isfinite(y)):
            raise JobContractError("coordenada não finita")
        return [(x, y)]
    if not coords:
        raise JobContractError("coordenada vazia")
    pairs: list[tuple[float, float]] = []
    for item in coords:
        pairs.extend(_coordinate_pairs(item))
    if not pairs:
        raise JobContractError("coordenada inválida")
    return pairs


def _read_input_bytes(path: Path) -> bytes:
    try:
        return path.read_bytes()
    except OSError as exc:
        raise JobContractError("arquivo de entrada ilegível") from exc


def _vector_bbox_metrics(data: bytes) -> dict[str, Any]:
    """Lê FeatureCollection e devolve contagem + bbox. Não calcula área oficial."""

    try:
        payload = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise JobContractError("GeoJSON inválido") from exc
    if not isinstance(payload, dict) or payload.get("type") != "FeatureCollection":
        raise JobContractError("GeoJSON deve ser FeatureCollection")
    features = payload.get("features")
    if not isinstance(features, list) or not features:
        raise JobContractError("FeatureCollection sem feições")
    points: list[tuple[float, float]] = []
    for feature in features:
        if not isinstance(feature, dict):
            raise JobContractError("feição inválida")
        geom = feature.get("geometry")
        if not isinstance(geom, dict):
            raise JobContractError("geometria ausente")
        points.extend(_coordinate_pairs(geom.get("coordinates")))
    xs = [item[0] for item in points]
    ys = [item[1] for item in points]
    return {
        "n_features": len(features),
        "bbox": [min(xs), min(ys), max(xs), max(ys)],
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
        scl_grid = resample_nearest(
            scl, target_rows, target_cols, allow_index_only=True
        )
        valid = valid_mask_from_scl(scl_grid)
    grid = ndvi_window(b04, b08, valid=valid)
    summary = ndvi_summary(grid)
    summary["grid"] = grid
    summary["scl_resample"] = (
        "index_nearest_synthetic" if scl is not None else None
    )
    summary["georeferenced_resample"] = False
    summary["sentinel_scene"] = False
    return summary


def _bind_source(
    *,
    job_type: str,
    params: dict[str, Any],
    allowed_roots: list[Path],
    source_sha256: str | None,
) -> tuple[str, Path | None]:
    """Calcula o SHA-256 da entrada antes da chave de idempotência."""

    if job_type == "vector_bbox_metrics":
        rel = params.get("input_path")
        if not isinstance(rel, str) or not rel:
            raise JobContractError("input_path obrigatório")
        path = resolve_allowed_path(Path(rel), roots=allowed_roots)
        digest = hashlib.sha256(_read_input_bytes(path)).hexdigest()
        if source_sha256 is not None and source_sha256 != digest:
            raise JobContractError("source_sha256 não confere com o arquivo")
        return digest, path
    if job_type == "sentinel2_ndvi_window":
        digest = hashlib.sha256(
            canonical_json(params).encode("utf-8")
        ).hexdigest()
        if source_sha256 is not None and source_sha256 != digest:
            raise JobContractError("source_sha256 não confere com os parâmetros")
        return digest, None
    raise JobContractError(f"job_type não implementado: {job_type}")


def _load_verified_publication(
    record_path: Path,
    out_path: Path,
    key: str,
) -> dict[str, Any] | None:
    """O manifest é o ponteiro de commit. Saída sem hash conferido não vale."""

    if not record_path.is_file() or not out_path.is_file():
        return None
    try:
        manifest = json.loads(record_path.read_text(encoding="utf-8"))
        payload = json.loads(out_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if not isinstance(manifest, dict) or not isinstance(payload, dict):
        return None
    if manifest.get("status") != "succeeded":
        return None
    if manifest.get("idempotency_key") != key or payload.get("idempotency_key") != key:
        return None
    if not isinstance(payload.get("result"), dict):
        return None
    recorded = (manifest.get("output_sha256") or {}).get(str(out_path))
    if not isinstance(recorded, str) or recorded != _sha256_file(out_path):
        return None
    return manifest


def _rejected_record(
    *,
    job_type: str,
    source_id: str,
    params: dict[str, Any],
    algorithms: list[str],
    message: str,
    source_uri: str,
    source_date: str | None,
) -> JobRecord:
    now = utc_now()
    return JobRecord(
        job_id=uuid.uuid4().hex,
        job_type=job_type,
        created_at_utc=now,
        status="failed",
        started_at_utc=now,
        finished_at_utc=now,
        source_id=source_id,
        source_uri=source_uri,
        source_date=source_date,
        params=params,
        algorithm_ids=algorithms,
        pipeline_version=PIPELINE_VERSION,
        error_code="invalid_input",
        error_message=message,
        elapsed_seconds=0.0,
    )


def _confirm_snapshot(resolved: Path | None, source_sha256: str) -> bytes | None:
    """Segunda leitura. O digest tem de ser o dos bytes que serão processados."""

    if resolved is None:
        return None
    confirmed = _read_input_bytes(resolved)
    if hashlib.sha256(confirmed).hexdigest() != source_sha256:
        raise JobContractError(
            "arquivo de entrada mudou entre o SHA-256 e a leitura"
        )
    return confirmed


def _new_record(
    *,
    job_type: str,
    source_id: str,
    source_uri: str,
    source_date: str | None,
    source_sha256: str,
    input_paths: list[str],
    params: dict[str, Any],
    algorithms: list[str],
    key: str,
) -> JobRecord:
    return JobRecord(
        job_id=uuid.uuid4().hex,
        job_type=job_type,
        created_at_utc=utc_now(),
        status="running",
        started_at_utc=utc_now(),
        source_id=source_id,
        source_uri=source_uri,
        source_date=source_date,
        source_sha256=source_sha256,
        input_paths=input_paths,
        params=params,
        algorithm_ids=algorithms,
        idempotency_key=key,
        pipeline_version=PIPELINE_VERSION,
    )


def _compute(
    *,
    job_type: str,
    params: dict[str, Any],
    confirmed: bytes | None,
    resolved: Path | None,
    record: JobRecord,
) -> dict[str, Any]:
    if job_type == "vector_bbox_metrics":
        if confirmed is None or resolved is None:
            raise JobContractError("entrada vetorial ausente")
        record.input_bytes = len(confirmed)
        record.input_paths = [str(resolved)]
        result = _vector_bbox_metrics(confirmed)
        record.spatial_extent = result.get("bbox")
        record.crs = params.get("declared_crs")
        return result
    if job_type == "sentinel2_ndvi_window":
        record.warnings.append(
            "Janela sintética em memória. Não é cena Sentinel baixada. "
            "SCL, se houver, usa nearest por índice, sem geotransform."
        )
        return _ndvi_from_params(params)
    raise JobContractError(f"job_type não implementado: {job_type}")


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
    """Executa um job da allowlist.

    O SHA-256 da entrada entra na chave antes de qualquer reuso. A mesma chave
    é publicada sob um lock local. A saída é gravada primeiro; o manifest
    `.job.json` é o ponteiro de commit e só vale se o hash conferir.
    """

    validate_job_request(job_type=job_type, params=params)
    algorithms = list(algorithm_ids or _default_algorithms(job_type))
    jobs_dir = Path(jobs_dir)
    jobs_dir.mkdir(parents=True, exist_ok=True)
    try:
        source_sha256, resolved = _bind_source(
            job_type=job_type,
            params=params,
            allowed_roots=allowed_roots,
            source_sha256=source_sha256,
        )
    except JobContractError as exc:
        rejected = _rejected_record(
            job_type=job_type,
            source_id=source_id,
            params=params,
            algorithms=algorithms,
            message=str(exc),
            source_uri=source_uri,
            source_date=source_date,
        )
        atomic_write_json(
            jobs_dir / f"rejected-{rejected.job_id}.job.json",
            rejected.to_dict(),
        )
        return rejected

    key = idempotency_key(
        job_type=job_type,
        source_id=source_id,
        source_sha256=source_sha256,
        params=params,
        algorithm_ids=algorithms,
        pipeline_version=PIPELINE_VERSION,
    )
    out_path = jobs_dir / f"{key}.json"
    record_path = jobs_dir / f"{key}.job.json"
    try:
        with exclusive_key_lock(jobs_dir, key):
            confirmed = _confirm_snapshot(resolved, source_sha256)
            verified = _load_verified_publication(record_path, out_path, key)
            if verified is not None:
                verified["reused_previous"] = True
                return JobRecord(**_filter_record(verified))
            record = _new_record(
                job_type=job_type,
                source_id=source_id,
                source_uri=source_uri,
                source_date=source_date,
                source_sha256=source_sha256,
                input_paths=list(input_paths or []),
                params=params,
                algorithms=algorithms,
                key=key,
            )
            started = time.perf_counter()
            try:
                result = _compute(
                    job_type=job_type,
                    params=params,
                    confirmed=confirmed,
                    resolved=resolved,
                    record=record,
                )
                payload = {
                    "idempotency_key": key,
                    "job_type": job_type,
                    "source_id": source_id,
                    "source_sha256": source_sha256,
                    "publication_role": "result",
                    "commit_pointer": record_path.name,
                    "result": result,
                }
                nbytes = atomic_write_json(out_path, payload)
                published_sha = _sha256_file(out_path)
                record.output_paths = [str(out_path)]
                record.output_sha256 = {str(out_path): published_sha}
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
            if record.status != "succeeded":
                kept = _load_verified_publication(record_path, out_path, key)
                if kept is not None:
                    kept["reused_previous"] = True
                    warnings = list(kept.get("warnings") or [])
                    warnings.append(
                        "nova tentativa falhou; resultado validado foi mantido"
                    )
                    kept["warnings"] = warnings
                    return JobRecord(**_filter_record(kept))
            atomic_write_json(record_path, record.to_dict())
            if (
                record.status == "succeeded"
                and _load_verified_publication(record_path, out_path, key) is None
            ):
                record.status = "failed"
                record.error_code = "publication_mismatch"
                record.error_message = (
                    "resultado e manifest não conferem após a publicação"
                )
                atomic_write_json(record_path, record.to_dict())
            return record
    except JobContractError as exc:
        rejected = _rejected_record(
            job_type=job_type,
            source_id=source_id,
            params=params,
            algorithms=algorithms,
            message=str(exc),
            source_uri=source_uri,
            source_date=source_date,
        )
        atomic_write_json(
            jobs_dir / f"rejected-{rejected.job_id}.job.json",
            rejected.to_dict(),
        )
        return rejected


def _default_algorithms(job_type: str) -> list[str]:
    if job_type == "vector_bbox_metrics":
        return ["napi.vector_bbox_metrics.v1"]
    return ["napi.sentinel2_ndvi_window.v1", "napi.scl_nearest.v1"]


def _filter_record(payload: dict[str, Any]) -> dict[str, Any]:
    allowed = set(JobRecord.__dataclass_fields__)
    return {key: value for key, value in payload.items() if key in allowed}
