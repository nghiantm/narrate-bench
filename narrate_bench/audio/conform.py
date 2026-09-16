"""Resample/trim/normalize to the fixed audio contract, with check() that raises on violation."""

from __future__ import annotations

from math import gcd
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

TARGET_SR = 16000
PEAK_DBFS = -1.0
SILENCE_DBFS = -40.0
PAD_MS = 100


def _to_mono(audio: np.ndarray) -> np.ndarray:
    return audio if audio.ndim == 1 else audio.mean(axis=1)


def _resample(audio: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
    if orig_sr == target_sr:
        return audio
    g = gcd(orig_sr, target_sr)
    return resample_poly(audio, target_sr // g, orig_sr // g)


def _trim_silence(audio: np.ndarray, sr: int) -> np.ndarray:
    if len(audio) == 0:
        return audio
    threshold = 10 ** (SILENCE_DBFS / 20)
    above = np.abs(audio) > threshold
    if not above.any():
        return audio  # entirely silent; leave for status=silent detection (M06) rather than emptying it
    first = int(np.argmax(above))
    last = len(audio) - int(np.argmax(above[::-1])) - 1
    pad = int(sr * PAD_MS / 1000)
    start = max(0, first - pad)
    end = min(len(audio), last + pad + 1)
    return audio[start:end]


def _normalize_peak(audio: np.ndarray) -> np.ndarray:
    peak = float(np.max(np.abs(audio))) if len(audio) else 0.0
    if peak == 0:
        return audio
    target_linear = 10 ** (PEAK_DBFS / 20)
    return audio * (target_linear / peak)


def conform(in_path: Path, out_path: Path) -> None:
    audio, sr = sf.read(str(in_path), dtype="float32", always_2d=False)
    audio = _to_mono(audio)
    audio = _resample(audio, sr, TARGET_SR)
    audio = _trim_silence(audio, TARGET_SR)
    audio = _normalize_peak(audio)
    audio_i16 = np.clip(audio * 32767, -32768, 32767).astype(np.int16)
    # cache paths are extension-less content hashes; soundfile can't infer a
    # format from that on write (read/info autodetect fine without it).
    sf.write(str(out_path), audio_i16, TARGET_SR, subtype="PCM_16", format="WAV")


def is_silent(path: Path, threshold_dbfs: float = SILENCE_DBFS) -> bool:
    """RMS below the same -40 dBFS floor conform() uses to define 'silence'
    when trimming, applied to the whole clip rather than a leading/trailing
    span."""
    audio, _ = sf.read(str(path), dtype="float32")
    rms = float(np.sqrt(np.mean(audio.astype(np.float64) ** 2))) if len(audio) else 0.0
    if rms == 0:
        return True
    return 20 * np.log10(rms) < threshold_dbfs


def check(path: Path) -> None:
    """Raise AssertionError naming the violated part of the audio contract."""
    info = sf.info(str(path))
    assert info.samplerate == TARGET_SR, f"{path}: sample rate {info.samplerate} != {TARGET_SR}"
    assert info.channels == 1, f"{path}: channels {info.channels} != 1 (mono)"
    assert info.subtype == "PCM_16", f"{path}: subtype {info.subtype} != PCM_16"

    audio, _ = sf.read(str(path), dtype="float32")
    peak = float(np.max(np.abs(audio))) if len(audio) else 0.0
    if peak > 0:
        peak_dbfs = 20 * np.log10(peak)
        assert peak_dbfs <= PEAK_DBFS + 0.5, f"{path}: peak {peak_dbfs:.2f} dBFS exceeds contract ({PEAK_DBFS} dBFS)"
