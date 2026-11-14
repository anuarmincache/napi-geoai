"""Caminhos permitidos e publicação atômica de artefatos."""

from __future__ import annotations

import json
import os
import tempfile
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from geoai.processing.contract import JobContractError


def resolve_allowed_path(path: Path, *, roots: list[Path]) -> Path:
    """Resolve o caminho e exige que permaneça sob uma raiz permitida."""

    candidate = Path(path).expanduser()
    try:
        resolved = candidate.resolve(strict=False)
    except OSError as exc:
        raise JobContractError(f"caminho ilegível: {path}") from exc
    for root in roots:
        root_resolved = Path(root).resolve(strict=False)
        try:
            resolved.relative_to(root_resolved)
        except ValueError:
            continue
        return resolved
    raise JobContractError(
        f"caminho fora das raízes permitidas: {resolved}"
    )


def _replace_exclusive(source: Path, destination: Path) -> None:
    """os.replace com nova tentativa. No Windows o alvo pode estar em troca."""

    delay = 0.01
    for attempt in range(8):
        try:
            os.replace(source, destination)
            return
        except PermissionError:
            if attempt == 7:
                raise
            time.sleep(delay)
            delay *= 2


def _unlink_own(path: Path) -> None:
    delay = 0.01
    for _ in range(8):
        try:
            if path.exists():
                path.unlink()
            return
        except PermissionError:
            time.sleep(delay)
            delay *= 2
    if path.exists():
        path.unlink()


def atomic_write_json(destination: Path, payload: dict[str, Any]) -> int:
    """Grava JSON em temporário exclusivo e troca com os.replace.

    Cada chamada cria o seu arquivo no mesmo diretório do destino e apaga
    só esse temporário. Uma falha de validação não altera o destino.
    """

    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    fd, name = tempfile.mkstemp(
        prefix=f".{destination.name}.",
        suffix=".partial",
        dir=destination.parent,
    )
    partial = Path(name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        try:
            reloaded = json.loads(partial.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise JobContractError(
                "JSON de saída inválido; destino anterior preservado"
            ) from exc
        if not isinstance(reloaded, dict):
            raise JobContractError("saída JSON não é objeto")
        _replace_exclusive(partial, destination)
    finally:
        _unlink_own(partial)
    return destination.stat().st_size


_THREAD_LOCKS: dict[str, threading.Lock] = {}
_THREAD_LOCKS_GUARD = threading.Lock()


def _thread_lock(name: str) -> threading.Lock:
    with _THREAD_LOCKS_GUARD:
        lock = _THREAD_LOCKS.get(name)
        if lock is None:
            lock = threading.Lock()
            _THREAD_LOCKS[name] = lock
        return lock


def _lock_fd(fd: int) -> None:
    """Lock do sistema no arquivo aberto. Falha imediata se outro já o tem."""

    if os.name == "nt":
        import msvcrt

        os.lseek(fd, 0, os.SEEK_SET)
        try:
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        except OSError as exc:
            raise BlockingIOError(exc.errno or 0, "lock ocupado") from exc
        return
    import fcntl

    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)


def _unlock_fd(fd: int) -> None:
    if os.name == "nt":
        import msvcrt

        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
        return
    import fcntl

    fcntl.flock(fd, fcntl.LOCK_UN)


@contextmanager
def exclusive_key_lock(
    directory: Path,
    key: str,
    wait_timeout_s: float = 120.0,
) -> Iterator[None]:
    """Exclusão mútua local da chave. Sem fila distribuída.

    ``wait_timeout_s`` limita só a espera. A posse dura até o ``with`` terminar
    ou o processo morrer. A idade do arquivo não encerra um lock ativo, e este
    contexto não apaga o arquivo: isso evitava remover o lock de outro dono.
    """

    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{key}.lock"
    thread_lock = _thread_lock(str(path.resolve()))
    deadline = time.monotonic() + wait_timeout_s
    if not thread_lock.acquire(timeout=max(0.0, wait_timeout_s)):
        raise JobContractError(
            "outra execução local ainda publica esta chave"
        ) from None
    flags = os.O_CREAT | os.O_RDWR | getattr(os, "O_BINARY", 0)
    fd: int | None = None
    locked = False
    try:
        fd = os.open(path, flags)
        while True:
            try:
                _lock_fd(fd)
                locked = True
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise JobContractError(
                        "outra execução local ainda publica esta chave"
                    ) from None
                time.sleep(0.02)
        token = f"{os.getpid()}\n".encode("ascii")
        os.ftruncate(fd, 0)
        os.lseek(fd, 0, os.SEEK_SET)
        os.write(fd, token)
        yield
    finally:
        if fd is not None and locked:
            _unlock_fd(fd)
        if fd is not None:
            os.close(fd)
        thread_lock.release()
