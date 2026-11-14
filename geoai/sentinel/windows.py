"""Janelas STAC reproduzíveis a partir de um instante UTC."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta


def parse_as_of(value: str | None) -> datetime:
    """Aceita RFC3339 com fuso. Vazio significa o instante atual em UTC."""

    if value is None or value == "":
        return datetime.now(UTC).replace(microsecond=0)
    text = value.strip().replace("Z", "+00:00")
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        raise ValueError("--as-of exige fuso, por exemplo 2026-11-14T18:00:00Z")
    return parsed.astimezone(UTC).replace(microsecond=0)


def _stamp(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def search_windows(as_of: datetime) -> dict[str, str]:
    """Intervalos [as_of-7d, as_of] e [as_of-30d, as_of], fechados no instante."""

    if as_of.tzinfo is None:
        raise ValueError("as_of sem fuso")
    end = as_of.astimezone(UTC)
    return {
        "7d": f"{_stamp(end - timedelta(days=7))}/{_stamp(end)}",
        "30d": f"{_stamp(end - timedelta(days=30))}/{_stamp(end)}",
    }


def choose_search_window(full_coverage_in_7d: int) -> str:
    """30 dias quando a semana não tem footprint adequado, mesmo com itens."""

    if full_coverage_in_7d > 0:
        return "7d"
    return "30d"
