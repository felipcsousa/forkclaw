from __future__ import annotations

import os
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar

_runtime_env_overlay: ContextVar[dict[str, str]] = ContextVar("runtime_env_overlay", default={})


def runtime_env(name: str, default: str | None = None) -> str | None:
    overlay = _runtime_env_overlay.get()
    if name in overlay:
        return overlay[name]
    return os.getenv(name, default)


@contextmanager
def runtime_env_overlay(values: Mapping[str, str]) -> Iterator[None]:
    overlay = {key: value for key, value in values.items() if value}
    current = dict(_runtime_env_overlay.get())
    token = _runtime_env_overlay.set({**current, **overlay})
    try:
        yield
    finally:
        _runtime_env_overlay.reset(token)
