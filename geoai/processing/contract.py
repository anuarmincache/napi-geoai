"""Contrato de job geoespacial (serializável, sem QGIS no processo da UI)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

JOB_STATUSES = frozenset({"pending", "running", "succeeded", "failed"})

# Allowlist fechada. A UI não escolhe executável nem comando.
JOB_TYPES = frozenset(
    {
        "vector_bbox_metrics",
        "sentinel2_ndvi_window",
    }
)


class JobContractError(ValueError):
    """Entrada de job inválida (tipo, caminho ou parâmetro)."""


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )


def idempotency_key(
    *,
    job_type: str,
    source_id: str,
    source_sha256: str | None,
    params: dict[str, Any],
    algorithm_ids: list[str],
    pipeline_version: str,
) -> str:
    """Hash de fonte + versão + parâmetros + algoritmo. Sem timestamp."""

    body = canonical_json(
        {
            "job_type": job_type,
            "source_id": source_id,
            "source_sha256": source_sha256 or "",
            "params": params,
            "algorithm_ids": algorithm_ids,
            "pipeline_version": pipeline_version,
        }
    )
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


@dataclass
class JobRecord:
    job_id: str
    job_type: str
    created_at_utc: str
    status: str = "pending"
    started_at_utc: str | None = None
    finished_at_utc: str | None = None
    source_id: str = ""
    source_uri: str = ""
    source_date: str | None = None
    source_sha256: str | None = None
    input_paths: list[str] = field(default_factory=list)
    params: dict[str, Any] = field(default_factory=dict)
    crs: str | None = None
    spatial_extent: list[float] | None = None
    software_versions: dict[str, str] = field(default_factory=dict)
    algorithm_ids: list[str] = field(default_factory=list)
    output_paths: list[str] = field(default_factory=list)
    output_sha256: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    error_code: str | None = None
    error_message: str | None = None
    elapsed_seconds: float | None = None
    peak_rss_mb: float | None = None
    rss_note: str | None = None
    input_bytes: int | None = None
    output_bytes: int | None = None
    idempotency_key: str = ""
    pipeline_version: str = "geo-foundation-1"
    reused_previous: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def validate_job_request(
    *,
    job_type: str,
    params: dict[str, Any],
) -> None:
    if job_type not in JOB_TYPES:
        raise JobContractError(f"job_type não permitido: {job_type!r}")
    if not isinstance(params, dict):
        raise JobContractError("params deve ser objeto JSON")
    forbidden = {"shell", "command", "argv", "executable"}
    if forbidden & set(params):
        raise JobContractError("parâmetros de execução arbitrária não são aceitos")
