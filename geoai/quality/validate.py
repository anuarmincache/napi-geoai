"""Validadores de qualidade desacoplados de domínio.

``validate_tabular_record`` / ``validate_record`` avaliam **atributos
tabulares de um registro (dict)** contra ``DatasetSchema``.

Escopo explícito (MVP 06):
- Não valida geometria PostGIS, WKT/WKB nem arquivo espacial em disco.
- ``content_sha256``: formato (64 hex); verificação contra bytes só se
  ``content_bytes`` for fornecido.
"""

from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Mapping
from datetime import datetime
from typing import Any

from geoai.quality.contracts import (
    CANONICAL_ENERGY_UNITS,
    DatasetSchema,
    EnergyQuantityKind,
    FieldConstraint,
    QualityFinding,
    QualityReport,
    QualityStatus,
)

_SHA256_HEX_RE = re.compile(r"^[0-9a-fA-F]{64}$")


def is_sha256_hex(value: str) -> bool:
    """True se ``value`` tem exatamente 64 dígitos hexadecimais."""

    return bool(_SHA256_HEX_RE.fullmatch(value))


def verify_content_sha256(hex_digest: str, payload: bytes) -> bool:
    """Compara digest declarado com SHA-256 real dos bytes."""

    if not is_sha256_hex(hex_digest):
        return False
    return hashlib.sha256(payload).hexdigest() == hex_digest.lower()


def _parse_iso_datetime(value: str) -> bool:
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return False
    return True


def _parse_finite_number(
    value: Any,
    *,
    field: str,
) -> tuple[float | None, list[QualityFinding]]:
    """Converte para float finito; rejeita bool, NaN/Inf e não-números."""

    if isinstance(value, bool):
        return None, [
            QualityFinding(
                code="field.numeric_bool",
                message=f"campo {field}: booleano não é numérico válido",
                severity=QualityStatus.REJECTED,
                field=field,
            )
        ]
    if isinstance(value, (int, float)):
        numeric = float(value)
    elif isinstance(value, str):
        try:
            numeric = float(value.strip())
        except ValueError:
            return None, [
                QualityFinding(
                    code="field.numeric",
                    message=f"campo {field} exige valor numérico",
                    severity=QualityStatus.REJECTED,
                    field=field,
                )
            ]
    else:
        return None, [
            QualityFinding(
                code="field.numeric",
                message=f"campo {field} exige valor numérico",
                severity=QualityStatus.REJECTED,
                field=field,
            )
        ]

    if not math.isfinite(numeric):
        return None, [
            QualityFinding(
                code="field.non_finite",
                message=f"campo {field}: valor não finito (NaN/Inf) rejeitado",
                severity=QualityStatus.REJECTED,
                field=field,
            )
        ]
    return numeric, []


def validate_energy_field_unit(constraint: FieldConstraint) -> list[QualityFinding]:
    """Unidade coerente com a grandeza do **mesmo** campo (não entre colunas)."""

    findings: list[QualityFinding] = []
    kind = constraint.energy_quantity
    if kind in (EnergyQuantityKind.NOT_APPLICABLE, EnergyQuantityKind.OTHER):
        return findings
    if constraint.unit is None or not str(constraint.unit).strip():
        findings.append(
            QualityFinding(
                code="field.energy_unit_missing",
                message=(
                    f"campo energético {constraint.name} "
                    f"({kind.value}) exige unidade"
                ),
                severity=QualityStatus.REJECTED,
                field=constraint.name,
            )
        )
        return findings
    allowed = CANONICAL_ENERGY_UNITS.get(kind, frozenset())
    unit_norm = constraint.unit.strip()
    if allowed and unit_norm not in allowed:
        findings.append(
            QualityFinding(
                code="field.energy_unit_mismatch",
                message=(
                    f"campo {constraint.name}: unidade {unit_norm!r} incompatível "
                    f"com {kind.value}; esperadas: {sorted(allowed)}"
                ),
                severity=QualityStatus.REJECTED,
                field=constraint.name,
            )
        )
    return findings


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

    needs_numeric = (
        constraint.min_value is not None or constraint.max_value is not None
    )
    if needs_numeric:
        numeric, num_findings = _parse_finite_number(value, field=name)
        findings.extend(num_findings)
        if numeric is not None:
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

    findings.extend(validate_energy_field_unit(constraint))
    return findings


def _aggregate_status(findings: list[QualityFinding]) -> QualityStatus:
    if any(f.severity == QualityStatus.REJECTED for f in findings):
        return QualityStatus.REJECTED
    if any(f.severity == QualityStatus.WARNING for f in findings):
        return QualityStatus.WARNING
    return QualityStatus.VALID


def validate_tabular_record(
    schema: DatasetSchema,
    record: Mapping[str, Any],
    *,
    version_label: str,
    collected_at: str,
    content_sha256: str | None = None,
    content_bytes: bytes | None = None,
    limitations: tuple[str, ...] = (),
) -> QualityReport:
    """Avalia atributos tabulares de um registro (dict) contra o schema.

    Não inspeciona geometria PostGIS nem o conteúdo espacial do arquivo.
    Colunas com grandezas energéticas distintas **podem** coexistir, desde
    que cada campo tenha unidade canônica coerente (kW / MWh / kWh/m²).
    """

    findings: list[QualityFinding] = []
    extra: dict[str, Any] = {
        "scope": "tabular_record_only",
        "validates_postgis_geometry": False,
        "validates_file_bytes": content_bytes is not None,
    }

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
    elif content_sha256 is not None:
        if not is_sha256_hex(content_sha256):
            findings.append(
                QualityFinding(
                    code="meta.content_sha256_format",
                    message=(
                        "content_sha256 deve ter exatamente 64 caracteres "
                        "hexadecimais"
                    ),
                    severity=QualityStatus.REJECTED,
                )
            )
            extra["content_sha256_format_ok"] = False
        else:
            extra["content_sha256_format_ok"] = True
            if content_bytes is not None:
                matched = verify_content_sha256(content_sha256, content_bytes)
                extra["content_sha256_verified"] = matched
                if not matched:
                    findings.append(
                        QualityFinding(
                            code="meta.content_sha256_mismatch",
                            message=(
                                "content_sha256 não corresponde aos bytes "
                                "fornecidos"
                            ),
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

    # Unidades canônicas por campo (não proíbe colunas multi-grandeza).
    for constraint in schema.fields:
        findings.extend(validate_energy_field_unit(constraint))

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
            # validate_field_value já chama validate_energy_field_unit;
            # evitar duplicar: só atributos do valor aqui.
            value_findings = [
                f
                for f in validate_field_value(
                    constraint, record.get(constraint.name)
                )
                if f.code
                not in (
                    "field.energy_unit_missing",
                    "field.energy_unit_mismatch",
                )
            ]
            findings.extend(value_findings)

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
        extra=extra,
    )


def validate_record(
    schema: DatasetSchema,
    record: Mapping[str, Any],
    *,
    version_label: str,
    collected_at: str,
    content_sha256: str | None = None,
    content_bytes: bytes | None = None,
    limitations: tuple[str, ...] = (),
) -> QualityReport:
    """Alias de ``validate_tabular_record`` (compatibilidade)."""

    return validate_tabular_record(
        schema,
        record,
        version_label=version_label,
        collected_at=collected_at,
        content_sha256=content_sha256,
        content_bytes=content_bytes,
        limitations=limitations,
    )


def assert_energy_field_unit_coherent(constraint: FieldConstraint) -> None:
    """Falha se a unidade do campo não casa com sua grandeza energética."""

    findings = validate_energy_field_unit(constraint)
    if findings:
        raise ValueError(findings[0].message)


def assert_energy_quantities_separated(
    fields: tuple[FieldConstraint, ...],
) -> None:
    """Compatibilidade: valida coerência unidade↔grandeza **por campo**.

    Não rejeita coexistência de potência e geração em colunas distintas.
    """

    for constraint in fields:
        assert_energy_field_unit_coherent(constraint)
