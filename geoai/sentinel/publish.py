"""Decisão de publicação. O raster anterior só sai do lugar depois do catálogo."""

from __future__ import annotations

import os
import shutil
from collections.abc import Callable
from pathlib import Path

from geoai.sentinel.mosaic_rule import MIN_VALID_PIXEL_FRACTION


def publication_allowed(
    *,
    official_pixels: bool,
    valid_fraction: float | None,
    acquisition_ids: tuple[str, ...] | list[str],
) -> bool:
    """Publica só uma passagem oficial com fração válida de pelo menos 0,70."""

    if not official_pixels or valid_fraction is None:
        return False
    identities = {item for item in acquisition_ids if item}
    if len(identities) != 1:
        return False
    return float(valid_fraction) >= MIN_VALID_PIXEL_FRACTION


def _stamp(path: Path) -> tuple[int, int] | None:
    if not path.is_file():
        return None
    stat = path.stat()
    return (stat.st_size, stat.st_mtime_ns)


def publish_new_raster(
    previous: Path,
    staging: Path,
    produce: Callable[[Path], None],
    commit_catalog: Callable[[], None],
    restore_catalog: Callable[[], None],
) -> None:
    """Grava um arquivo novo. Falha devolve o raster antigo."""

    backup = previous.with_name(previous.name + ".rollback")
    had_previous = previous.is_file()
    if had_previous:
        shutil.copy2(previous, backup)
    before = _stamp(previous)
    try:
        produce(staging)
        if _stamp(previous) != before:
            raise RuntimeError("raster_anterior_alterado")
        commit_catalog()
        os.replace(staging, previous)
    except Exception:
        staging.unlink(missing_ok=True)
        if had_previous and backup.is_file():
            os.replace(backup, previous)
        else:
            backup.unlink(missing_ok=True)
        try:
            restore_catalog()
        finally:
            raise
    else:
        backup.unlink(missing_ok=True)
