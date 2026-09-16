"""TTSEngine Protocol and SynthResult dataclass."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


class TTSEngine(Protocol):
    engine_id: str
    voice_id: str
    params: dict
    max_chars: int

    def synthesize(self, text: str, out_path: Path) -> SynthResult: ...


@dataclass
class SynthResult:
    wall_s: float
    peak_vram_mb: int | None
    raw_sample_rate: int
    error: str | None = None
