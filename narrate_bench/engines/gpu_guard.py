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

import torch

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


def reset_peak_vram() -> None:
    """Call right before a synthesize() call whose peak VRAM you want isolated."""
    if torch.cuda.is_available():
        torch.cuda.reset_peak_memory_stats()


def peak_vram_mb() -> int | None:
    """Peak allocation since the last reset_peak_vram() call, or None off-GPU."""
    if not torch.cuda.is_available():
        return None
    return int(torch.cuda.max_memory_allocated() / (1024 * 1024))
