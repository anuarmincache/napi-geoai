"""Validadores de qualidade desacoplados de domínio."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any

from geoai.quality.contracts import (
    DatasetSchema,
    EnergyQuantityKind,
    FieldConstraint,
    QualityFinding,
    QualityReport,
    QualityStatus,
)


def _parse_iso_datetime(value: str) -> bool:
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return False
    return True


def validate_field_value(
    constraint: FieldConstraint,
    value: Any,
) -> list[QualityFinding]:
    """Valida um valor contra ``FieldConstraint`` (sem inventar preenchimento)."""

    findings: list[QualityFinding] = []
    name = constraint.name

    if value is None or value == "":
        if constraint.required and not constraint.nullable:
            findings.append(
                QualityFinding(
                    code="field.required",
                    message=f"campo obrigatório ausente: {name}",
                    severity=QualityStatus.REJECTED,
                    field=name,
                )
            )
        return findings

    if constraint.allowed_values is not None:
        as_text = str(value)
        if as_text not in constraint.allowed_values:
            findings.append(
                QualityFinding(
                    code="field.allowed_values",
                    message=(
                        f"valor {as_text!r} fora do conjunto permitido "
                        f"para {name}"
                    ),
                    severity=QualityStatus.REJECTED,
                    field=name,
                )
            )

    if constraint.min_value is not None or constraint.max_value is not None:
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            findings.append(
                QualityFinding(
                    code="field.numeric",
                    message=f"campo {name} exige valor numérico",
                    severity=QualityStatus.REJECTED,
                    field=name,
                )
            )
            return findings
        if constraint.min_value is not None and numeric < constraint.min_value:
            findings.append(
                QualityFinding(
                    code="field.range_min",
                    message=(
                        f"campo {name}={numeric} abaixo do mínimo "
                        f"{constraint.min_value}"
                    ),
                    severity=QualityStatus.REJECTED,
                    field=name,
                )
            )
        if constraint.max_value is not None and numeric > constraint.max_value:
            findings.append(
                QualityFinding(
                    code="field.range_max",
                    message=(
                        f"campo {name}={numeric} acima do máximo "
                        f"{constraint.max_value}"
                    ),
                    severity=QualityStatus.REJECTED,
                    field=name,
                )
            )

    if (
        constraint.energy_quantity != EnergyQuantityKind.NOT_APPLICABLE
        and constraint.unit is None
    ):
        findings.append(
            QualityFinding(
                code="field.energy_unit_missing",
                message=(
                    f"campo energético {name} "
                    f"({constraint.energy_quantity.value}) exige unidade"
                ),
                severity=QualityStatus.REJECTED,
                field=name,
            )
        )

    return findings


def _aggregate_status(findings: list[QualityFinding]) -> QualityStatus:
    if any(f.severity == QualityStatus.REJECTED for f in findings):
        return QualityStatus.REJECTED
    if any(f.severity == QualityStatus.WARNING for f in findings):
        return QualityStatus.WARNING
    return QualityStatus.VALID


def validate_record(
    schema: DatasetSchema,
    record: Mapping[str, Any],
    *,
    version_label: str,
    collected_at: str,
    content_sha256: str | None = None,
    limitations: tuple[str, ...] = (),
) -> QualityReport:
    """Avalia um registro (dict) contra o schema do dataset."""

    findings: list[QualityFinding] = []

    if not _parse_iso_datetime(collected_at):
        findings.append(
            QualityFinding(
                code="meta.collected_at",
                message="collected_at deve ser ISO-8601",
                severity=QualityStatus.REJECTED,
            )
        )

    if schema.content_sha256_required and not content_sha256:
        findings.append(
            QualityFinding(
                code="meta.content_sha256",
                message="content_sha256 obrigatório para este dataset",
                severity=QualityStatus.REJECTED,
            )
        )

    if not schema.crs.strip():
        findings.append(
            QualityFinding(
                code="meta.crs",
                message="CRS do schema está vazio",
                severity=QualityStatus.REJECTED,
            )
        )

    if not schema.license_note.strip():
        findings.append(
            QualityFinding(
                code="meta.license",
                message="licença do schema está vazia",
                severity=QualityStatus.REJECTED,
            )
        )

    # Detectar mistura de grandezas energéticas no mesmo schema.
    energy_kinds = {
        f.energy_quantity
        for f in schema.fields
        if f.energy_quantity
        not in (EnergyQuantityKind.NOT_APPLICABLE, EnergyQuantityKind.OTHER)
    }
    if len(energy_kinds) > 1:
        findings.append(
            QualityFinding(
                code="schema.energy_quantity_mix",
                message=(
                    "schema mistura grandezas energéticas distintas no mesmo "
                    "dataset: "
                    + ", ".join(sorted(k.value for k in energy_kinds))
                ),
                severity=QualityStatus.REJECTED,
            )
        )

    known = set(record.keys())
    for constraint in schema.fields:
        if constraint.name not in known and constraint.required:
            findings.append(
                QualityFinding(
                    code="field.missing",
                    message=f"campo ausente no registro: {constraint.name}",
                    severity=QualityStatus.REJECTED,
                    field=constraint.name,
                )
            )
            continue
        if constraint.name in known:
            findings.extend(
                validate_field_value(constraint, record.get(constraint.name))
            )

    status = _aggregate_status(findings)
    return QualityReport(
        dataset_id=schema.dataset_id,
        source_id=schema.source_id,
        status=status,
        version_label=version_label,
        collected_at=collected_at,
        limitations=limitations,
        findings=tuple(findings),
        content_sha256=content_sha256,
    )


def assert_energy_quantities_separated(
    fields: tuple[FieldConstraint, ...],
) -> None:
    """Falha se potência, geração e irradiação coexistirem no mesmo schema."""

    kinds = {
        f.energy_quantity
        for f in fields
        if f.energy_quantity
        not in (EnergyQuantityKind.NOT_APPLICABLE, EnergyQuantityKind.OTHER)
    }
    if len(kinds) > 1:
        raise ValueError(
            "não misturar grandezas energéticas no mesmo schema: "
            + ", ".join(sorted(k.value for k in kinds))
        )
