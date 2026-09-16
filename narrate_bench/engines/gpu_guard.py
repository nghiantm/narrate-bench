"""GPU model residency guard: only one GPU-resident TTS model (or Whisper,
once M11 wires it in) at a time, per ARCHITECTURE.md's concurrency section.

Each `nb synthesize` invocation currently loads at most one GPU engine per
process anyway, so this has nothing to contend with yet. It exists now,
real and tested, so M14's full-run orchestrator -- which will load and
unload GPU engines in sequence within one process -- has this hook ready
rather than needing to invent it under a bigger milestone.
"""

from __future__ import annotations

import threading

_lock = threading.Lock()
_holder: str | None = None


def acquire(engine_id: str) -> None:
    global _holder
    if not _lock.acquire(blocking=False):
        raise RuntimeError(f"GPU already held by {_holder!r}; release it before loading {engine_id!r}")
    _holder = engine_id


def release(engine_id: str) -> None:
    global _holder
    if _holder != engine_id:
        raise RuntimeError(f"{engine_id!r} does not hold the GPU guard (held by {_holder!r})")
    _holder = None
    _lock.release()
