"""Coqui XTTS v2 GPU voice-cloning engine."""

from __future__ import annotations

import os
import time
from pathlib import Path

import numpy as np
import soundfile as sf
import torch

os.environ.setdefault("COQUI_TOS_AGREED", "1")  # CPML non-commercial use, confirmed with the user

from TTS.api import TTS  # noqa: E402

from narrate_bench.engines.base import SynthResult
from narrate_bench.engines.gpu_guard import acquire, release

MODEL_NAME = "tts_models/multilingual/multi-dataset/xtts_v2"
SAMPLE_RATE = 24000


class XTTSEngine:
    engine_id = "xtts"

    def __init__(self, voice_id: str, params: dict, max_chars: int, reference_clip: Path, language: str = "en"):
        self.voice_id = voice_id
        self.params = params
        self.max_chars = max_chars
        self.language = language

        acquire(self.engine_id)
        self._tts = TTS(MODEL_NAME, gpu=torch.cuda.is_available())
        self._model = self._tts.synthesizer.tts_model
        # Computed once from the shared reference clip, reused for every chunk.
        self._gpt_cond_latent, self._speaker_embedding = self._model.get_conditioning_latents(
            audio_path=str(reference_clip)
        )

    def synthesize(self, text: str, out_path: Path) -> SynthResult:
        t0 = time.monotonic()
        try:
            out = self._model.inference(
                text,
                self.language,
                self._gpt_cond_latent,
                self._speaker_embedding,
                **self.params,
            )
            audio = np.asarray(out["wav"], dtype=np.float32)
        except Exception as e:  # per-chunk engine failures must not abort the run
            return SynthResult(wall_s=time.monotonic() - t0, peak_vram_mb=None, raw_sample_rate=0, error=str(e))
        sf.write(str(out_path), audio, SAMPLE_RATE, subtype="PCM_16", format="WAV")
        return SynthResult(wall_s=time.monotonic() - t0, peak_vram_mb=None, raw_sample_rate=SAMPLE_RATE)

    def unload(self) -> None:
        del self._model
        del self._tts
        torch.cuda.empty_cache()
        release(self.engine_id)
