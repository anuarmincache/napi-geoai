"""Regras da atualização quinzenal. Não há agendamento ativo."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

UPDATE_INTERVAL_DAYS = 15
MINIMUM_VALID_FRACTION = 0.70


@dataclass(frozen=True, slots=True)
class CoverageRequest:
    """Pedido de um município sobre uma tile de uma aquisição."""

    ibge: str
    acquisition_id: str
    tile_id: str


@dataclass(frozen=True, slots=True)
class TileJob:
    """Uma cena/tile é baixada uma vez e serve aos municípios que a usam."""

    acquisition_id: str
    tile_id: str
    municipalities: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AcquisitionSnapshot:
    """Registro que o histórico precisa conservar."""

    acquisition_id: str
    image_date: str
    quality_status: str
    algorithm_version: str


@dataclass(frozen=True, slots=True)
class UpdateDecision:
    action: str
    reason: str
    retained_acquisition_id: str
    user_message_pt: str
    preserved: AcquisitionSnapshot | None = None
    scheduler_active: bool = False
    guarantees_new_valid_scene: bool = False


def attempt_is_due(
    last_attempt: date | None,
    today: date,
    *,
    interval_days: int = UPDATE_INTERVAL_DAYS,
) -> bool:
    """Informa se a janela de 15 dias já decorreu. Não dispara tarefa."""

    if interval_days != UPDATE_INTERVAL_DAYS:
        raise ValueError("intervalo_recusado")
    if last_attempt is None:
        return True
    return (today - last_attempt).days >= interval_days


def scene_tile_plan(requests: tuple[CoverageRequest, ...]) -> tuple[TileJob, ...]:
    """Agrupa pedidos para não repetir a mesma tile na mesma aquisição."""

    grouped: dict[tuple[str, str], set[str]] = {}
    for request in requests:
        grouped.setdefault((request.acquisition_id, request.tile_id), set()).add(
            request.ibge
        )
    return tuple(
        TileJob(acquisition_id, tile_id, tuple(sorted(ibges)))
        for (acquisition_id, tile_id), ibges in sorted(grouped.items())
    )


def decide_update(
    *,
    current_acquisition_id: str,
    candidate_acquisition_id: str,
    candidate_valid_fraction: float,
    candidate_validated: bool,
    current: AcquisitionSnapshot | None = None,
) -> UpdateDecision:
    """Mantém o último mapa aprovado quando a passagem nova não serve.

    A janela de 15 dias autoriza uma tentativa. Ela não garante uma cena
    válida nova. O registro ``current`` entra no histórico com data,
    qualidade e versão do algoritmo.
    """

    if current is not None and current.acquisition_id != current_acquisition_id:
        raise ValueError("historico_divergente")
    if candidate_acquisition_id == current_acquisition_id:
        return UpdateDecision(
            action="manter",
            reason="cena_ja_catalogada",
            retained_acquisition_id=current_acquisition_id,
            user_message_pt=(
                "A passagem consultada já é a imagem válida deste município."
            ),
            preserved=current,
        )
    if not candidate_validated or candidate_valid_fraction < MINIMUM_VALID_FRACTION:
        return UpdateDecision(
            action="manter",
            reason="nova_passagem_sem_qualidade",
            retained_acquisition_id=current_acquisition_id,
            user_message_pt=(
                "Existe uma imagem mais recente, mas ela não atingiu o "
                "critério de pixels válidos. O mapa continua sendo a última "
                "imagem válida. A tentativa de 15 dias não garante uma cena "
                "válida nova."
            ),
            preserved=current,
        )
    return UpdateDecision(
        action="substituir",
        reason="nova_cena_validada",
        retained_acquisition_id=candidate_acquisition_id,
        user_message_pt=(
            "Uma nova imagem válida passa a ser o mapa atual. "
            "A imagem anterior permanece no histórico, com a data da "
            "aquisição, a qualidade e a versão do algoritmo."
        ),
        preserved=current,
    )
