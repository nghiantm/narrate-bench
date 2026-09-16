"""Kokoro CPU engine."""

from __future__ import annotations

import time
from pathlib import Path

import numpy as np
import soundfile as sf
from kokoro import KPipeline

from narrate_bench.engines.base import SynthResult

SAMPLE_RATE = 24000


class KokoroEngine:
    engine_id = "kokoro"

    def __init__(self, voice_id: str, params: dict, max_chars: int, lang_code: str = "a"):
        self.voice_id = voice_id
        self.params = params
        self.max_chars = max_chars
        self._pipeline = KPipeline(lang_code=lang_code, device="cpu")

    def synthesize(self, text: str, out_path: Path) -> SynthResult:
        t0 = time.monotonic()
        try:
            segments = [r.audio.detach().cpu().numpy() for r in self._pipeline(text, voice=self.voice_id)]
            audio = np.concatenate(segments) if len(segments) > 1 else segments[0]
        except Exception as e:  # per-chunk engine failures must not abort the run
            return SynthResult(wall_s=time.monotonic() - t0, peak_vram_mb=None, raw_sample_rate=0, error=str(e))
        sf.write(str(out_path), audio, SAMPLE_RATE, subtype="PCM_16", format="WAV")
        return SynthResult(wall_s=time.monotonic() - t0, peak_vram_mb=None, raw_sample_rate=SAMPLE_RATE)
