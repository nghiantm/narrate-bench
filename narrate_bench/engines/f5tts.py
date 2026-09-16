"""F5-TTS GPU voice-cloning engine."""

from __future__ import annotations

import os
import time
from pathlib import Path

import numpy as np
import soundfile as sf

os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")

from narrate_bench.engines.base import SynthResult
from narrate_bench.engines.gpu_guard import acquire, peak_vram_mb, release, reset_peak_vram

MODEL_NAME = "F5TTS_v1_Base"


class F5TTSEngine:
    engine_id = "f5tts"

    def __init__(self, voice_id: str, params: dict, max_chars: int, reference_clip: Path):
        self.voice_id = voice_id
        self.params = params
        self.max_chars = max_chars

        acquire(self.engine_id)
        from f5_tts.api import F5TTS
        from f5_tts.infer.utils_infer import preprocess_ref_audio_text

        self._tts = F5TTS(model=MODEL_NAME)
        # Transcribed once via F5-TTS's bundled ASR fallback (empty ref_text);
        # every later call reuses this text and skips re-transcription.
        self._ref_file, self._ref_text = preprocess_ref_audio_text(str(reference_clip), "")

    def synthesize(self, text: str, out_path: Path) -> SynthResult:
        t0 = time.monotonic()
        reset_peak_vram()
        try:
            wav, sr, _ = self._tts.infer(
                ref_file=self._ref_file,
                ref_text=self._ref_text,
                gen_text=text,
                show_info=lambda *a, **k: None,
                **self.params,
            )
            audio = np.asarray(wav, dtype=np.float32)
        except Exception as e:  # per-chunk engine failures must not abort the run
            return SynthResult(wall_s=time.monotonic() - t0, peak_vram_mb=peak_vram_mb(), raw_sample_rate=0, error=str(e))
        sf.write(str(out_path), audio, sr, subtype="PCM_16", format="WAV")
        return SynthResult(wall_s=time.monotonic() - t0, peak_vram_mb=peak_vram_mb(), raw_sample_rate=sr)

    def unload(self) -> None:
        import torch

        del self._tts
        torch.cuda.empty_cache()
        release(self.engine_id)
