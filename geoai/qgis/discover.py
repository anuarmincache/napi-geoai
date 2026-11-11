"""Descoberta local do QGIS (Windows LTR). Sem instalação na Cloud."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class QgisInstall:
    root: Path
    python_bat: Path | None
    process_bat: Path | None
    qgis_bin: Path | None


def _candidate_roots() -> tuple[Path, ...]:
    env = os.environ.get("QGIS_ROOT") or os.environ.get("OSGEO4W_ROOT")
    roots: list[Path] = []
    if env:
        roots.append(Path(env))
    roots.extend(
        [
            Path(r"C:\Program Files\QGIS 3.44.15"),
            Path(r"C:\Program Files\QGIS 3.40.0"),
            Path(r"C:\OSGeo4W64"),
        ]
    )
    # Dedup preserving order
    seen: set[str] = set()
    out: list[Path] = []
    for root in roots:
        key = str(root.resolve()) if root.exists() else str(root)
        if key not in seen:
            seen.add(key)
            out.append(root)
    return tuple(out)


def discover_qgis() -> QgisInstall | None:
    for root in _candidate_roots():
        if not root.is_dir():
            continue
        bin_dir = root / "bin"
        python_bat = bin_dir / "python-qgis-ltr.bat"
        if not python_bat.is_file():
            python_bat = bin_dir / "python-qgis.bat"
        process_bat = bin_dir / "qgis_process-qgis-ltr.bat"
        if not process_bat.is_file():
            process_bat = bin_dir / "qgis_process.bat"
        qgis_bin = bin_dir / "qgis-ltr-bin.exe"
        if not qgis_bin.is_file():
            qgis_bin = bin_dir / "qgis-bin.exe"
        if python_bat.is_file() or process_bat.is_file() or qgis_bin.is_file():
            return QgisInstall(
                root=root,
                python_bat=python_bat if python_bat.is_file() else None,
                process_bat=process_bat if process_bat.is_file() else None,
                qgis_bin=qgis_bin if qgis_bin.is_file() else None,
            )
    return None


def qgis_available() -> bool:
    return discover_qgis() is not None
