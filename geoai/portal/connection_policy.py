"""Política de conexão a dados — local canônico vs remoto futuro.

Não cria projeto Supabase, não lê segredos e não abre porta à Internet.
Apenas documenta modos suportados para adaptadores futuros (MVP 07+).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any


class DataBackendMode(StrEnum):
    """Onde a interface pode obter camadas/metadados."""

    LOCAL_ARTIFACTS = "local_artifacts"
    LOCAL_POSTGIS = "local_postgis"
    REMOTE_SUPABASE_FUTURE = "remote_supabase_future"


@dataclass(frozen=True, slots=True)
class ConnectionPolicy:
    """Descreve o backend ativo e restrições operacionais."""

    mode: DataBackendMode
    description_pt: str
    requires_secret: bool
    network_exposure: str
    notes_pt: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["mode"] = self.mode.value
        data["notes_pt"] = list(self.notes_pt)
        return data


DEFAULT_DEMO_POLICY = ConnectionPolicy(
    mode=DataBackendMode.LOCAL_ARTIFACTS,
    description_pt=(
        "Demonstração Streamlit usa GeoJSON/proveniência versionados em "
        "data/derived — sem Postgres remoto e sem Supabase."
    ),
    requires_secret=False,
    network_exposure="nenhuma (arquivos locais do repositório)",
    notes_pt=(
        "PostgreSQL/PostGIS :5433 permanece canônico para pesquisa/ops; "
        "a UI deste MVP não o altera.",
        "Supabase Pro da organização NÃO é provisionado neste MVP.",
        "Publicação no Streamlit Community Cloud deve usar só artefatos "
        "versionados; segredos só no painel — nunca .env no Git.",
        "MVP 08 prepara o deploy (docs/MVP08_DEPLOY.md) sem publicar "
        "automaticamente nem provisionar Supabase.",
    ),
)


def demo_connection_policy() -> ConnectionPolicy:
    return DEFAULT_DEMO_POLICY


def future_supabase_policy_stub() -> ConnectionPolicy:
    """Placeholder explícito — não ativa conexão."""

    return ConnectionPolicy(
        mode=DataBackendMode.REMOTE_SUPABASE_FUTURE,
        description_pt=(
            "Modo futuro: leitura de camadas aprovadas via projeto Supabase "
            "independente, após autorização de custos e escopo."
        ),
        requires_secret=True,
        network_exposure="HTTPS ao projeto remoto (ainda não configurado)",
        notes_pt=(
            "Não criar projeto nem copiar dados sem aprovação explícita.",
            "Núcleo geoai permanece sem dependência proprietária obrigatória.",
        ),
    )
