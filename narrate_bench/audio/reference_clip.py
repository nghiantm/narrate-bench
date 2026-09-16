"""Shared reference clip for the voice-cloning engines (XTTS, F5-TTS, Chatterbox).

Extracted from a single-narrator, public-domain LibriVox recording: Frank
Woodworth Pine's edited "Autobiography of Benjamin Franklin," narrated solo
by Gary Gilberd (LibriVox book id 1143, the same recording used for that
book's human baseline in Track C) -- chapter 1, a fixed 71.0s-81.0s window
verified clean: 64% of samples above -40 dBFS (mostly speech, not silence),
peak 0.78 (no clipping), well past any intro announcement.

Written at the source's native sample rate, NOT run through audio.conform()'s
16 kHz ASR/SpeechBrain contract -- this file feeds each engine's own speaker
reference encoder, not Whisper or SpeechBrain.
"""

from __future__ import annotations

import os
import shutil
import urllib.request
from pathlib import Path

import soundfile as sf

SOURCE_URL = "https://www.archive.org/download/franklin_autobio_gg_librivox/franklin_01_pine_64kb.mp3"
CLIP_START_S = 71.0
CLIP_DURATION_S = 10.0


def _download(url: str, dest: Path) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": "narrate-bench/0.1"})
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    with urllib.request.urlopen(req, timeout=120) as resp, open(tmp, "wb") as f:
        shutil.copyfileobj(resp, f)
    os.replace(tmp, dest)


def ensure_reference_clip(dest_path: Path) -> Path:
    if dest_path.exists():
        return dest_path
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    source_mp3 = dest_path.with_name(dest_path.stem + ".source.mp3")
    _download(SOURCE_URL, source_mp3)

    audio, sr = sf.read(str(source_mp3), dtype="float32")
    start = int(CLIP_START_S * sr)
    end = start + int(CLIP_DURATION_S * sr)
    clip = audio[start:end]

    tmp_wav = dest_path.with_suffix(dest_path.suffix + ".tmp")
    sf.write(str(tmp_wav), clip, sr, subtype="PCM_16", format="WAV")
    os.replace(tmp_wav, dest_path)
    source_mp3.unlink()
    return dest_path
