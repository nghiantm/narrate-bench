"""Piper CPU engine."""

from __future__ import annotations

import os
import shutil
import time
import urllib.request
import wave
from pathlib import Path

from piper import PiperVoice

from narrate_bench.engines.base import SynthResult

VOICE_BASE_URL = "https://huggingface.co/rhasspy/piper-voices/resolve/main"


def _voice_url(voice_id: str, ext: str) -> str:
    # Standard Piper naming: "{region}-{name}-{quality}", e.g. en_US-lessac-medium
    region, name, quality = voice_id.split("-")
    lang = region.split("_")[0]
    return f"{VOICE_BASE_URL}/{lang}/{region}/{name}/{quality}/{voice_id}.{ext}"


def _download(url: str, dest: Path) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": "narrate-bench/0.1"})
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    with urllib.request.urlopen(req, timeout=120) as resp, open(tmp, "wb") as f:
        shutil.copyfileobj(resp, f)
    os.replace(tmp, dest)


def ensure_voice_files(voice_id: str, model_dir: Path) -> tuple[Path, Path]:
    model_dir.mkdir(parents=True, exist_ok=True)
    onnx_path = model_dir / f"{voice_id}.onnx"
    json_path = model_dir / f"{voice_id}.onnx.json"
    if not onnx_path.exists():
        _download(_voice_url(voice_id, "onnx"), onnx_path)
    if not json_path.exists():
        _download(_voice_url(voice_id, "onnx.json"), json_path)
    return onnx_path, json_path


class PiperEngine:
    engine_id = "piper"

    def __init__(self, voice_id: str, params: dict, max_chars: int, model_dir: Path):
        self.voice_id = voice_id
        self.params = params
        self.max_chars = max_chars
        onnx_path, json_path = ensure_voice_files(voice_id, model_dir)
        self._voice = PiperVoice.load(str(onnx_path), config_path=str(json_path))

    def synthesize(self, text: str, out_path: Path) -> SynthResult:
        t0 = time.monotonic()
        try:
            with wave.open(str(out_path), "wb") as wav_file:
                self._voice.synthesize_wav(text, wav_file)
        except Exception as e:  # per-chunk engine failures must not abort the run
            return SynthResult(wall_s=time.monotonic() - t0, peak_vram_mb=None, raw_sample_rate=0, error=str(e))
        return SynthResult(
            wall_s=time.monotonic() - t0,
            peak_vram_mb=None,
            raw_sample_rate=self._voice.config.sample_rate,
        )
