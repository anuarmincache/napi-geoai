"""Configuração local do visualizador. Nenhum caminho fica no código."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

CONFIG_ENV = "NAPI_NDVI_VIEWER_CONFIG"
SCIENCE_ENV = "NAPI_NDVI_SCIENCE_DIR"
PREVIEW_ENV = "NAPI_NDVI_PREVIEW_DIR"
DOWNLOAD_ENV = "NAPI_NDVI_LOCAL_TEST_DOWNLOADS"


@dataclass(frozen=True)
class ViewerConfig:
    science_dir: Path
    preview_dir: Path
    local_test_downloads: bool


def _flag(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "sim", "yes"}


def _from_mapping(payload: Mapping[str, object]) -> ViewerConfig:
    science = payload.get("science_dir")
    preview = payload.get("preview_dir")
    if not isinstance(science, str) or not isinstance(preview, str):
        raise ValueError("configuracao_invalida")
    if not science.strip() or not preview.strip():
        raise ValueError("configuracao_incompleta")
    flag = payload.get("local_test_downloads", False)
    if not isinstance(flag, bool):
        raise ValueError("configuracao_invalida")
    return ViewerConfig(Path(science), Path(preview), flag)


def load_config(
    environ: Mapping[str, str] | None = None,
) -> ViewerConfig | None:
    """Lê um JSON apontado pelo ambiente, ou três variáveis separadas."""

    env = os.environ if environ is None else environ
    configured = env.get(CONFIG_ENV, "").strip()
    if configured:
        payload = json.loads(Path(configured).read_text(encoding="utf-8"))
        return _from_mapping(payload)
    science = env.get(SCIENCE_ENV, "").strip()
    preview = env.get(PREVIEW_ENV, "").strip()
    if not science and not preview:
        return None
    if not science or not preview:
        raise ValueError("configuracao_incompleta")
    return ViewerConfig(
        Path(science),
        Path(preview),
        _flag(env.get(DOWNLOAD_ENV, "0")),
    )
