from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest
import soundfile as sf

from narrate_bench.audio import conform
from narrate_bench.cli import synthesize
from narrate_bench.config import Book, Config, EngineCfg, Paths
from narrate_bench.engines.base import SynthResult


def _tone(n_samples=32000, sr=16000, freq=440, amp=8000):
    # 2s default: comfortably above the ~1.4s expected duration for a
    # ~21-char test chunk at CHARS_PER_SECOND, so "normal" output isn't
    # accidentally flagged truncated.
    t = np.arange(n_samples)
    return (np.sin(2 * np.pi * freq * t / sr) * amp).astype(np.int16), sr


class CrashAfterNEngine:
    """A mock engine that completes `crash_after` chunks normally, then
    raises KeyboardInterrupt on the next call, simulating a process kill
    mid-run rather than a normal per-chunk synthesis failure (which
    _synthesize_chunk already catches and continues past)."""

    engine_id = "mock"
    voice_id = "v1"
    params: dict = {}
    max_chars = 1000

    def __init__(self, crash_after=None):
        self.calls = 0  # counts only completed (non-crashing) calls
        self.crash_after = crash_after

    def synthesize(self, text, out_path):
        if self.crash_after is not None and self.calls >= self.crash_after:
            raise KeyboardInterrupt("simulated process kill")
        audio, sr = _tone()
        sf.write(str(out_path), audio, sr, subtype="PCM_16", format="WAV")
        self.calls += 1
        return SynthResult(wall_s=0.01, peak_vram_mb=None, raw_sample_rate=sr)


def _make_cfg(tmp_path, n_chunks=10):
    book = Book(book_id="b", gutenberg_id=1, librivox_id=1, librivox_url="https://example.com", chapter_regex="x")
    engine_cfg = EngineCfg(voice_id="v1", max_chars=1000, device="cpu", model_revision="rev1")
    cfg = Config(
        books=[book],
        engines={"mock": engine_cfg},
        paths=Paths(data=tmp_path / "data", cache=tmp_path / "cache", results=tmp_path / "results"),
    )
    cfg.paths.data.mkdir(parents=True)
    chunks = pd.DataFrame(
        [
            {
                "chunk_id": f"c{i}",
                "book_id": "b",
                "chapter_idx": 0,
                "position_index": i,
                "bucket": "XS",
                "char_len": 20,
                "word_count": 4,
                "text": f"hello there number {i}",
                "human_audio": None,
                "align_conf": None,
            }
            for i in range(n_chunks)
        ]
    )
    chunks.to_parquet(cfg.paths.data / "chunks.parquet", index=False)
    return cfg


def test_crash_and_restart_synthesizes_every_chunk_exactly_once(tmp_path):
    n_chunks = 10
    cfg = _make_cfg(tmp_path, n_chunks=n_chunks)

    engine1 = CrashAfterNEngine(crash_after=4)
    with (
        patch("narrate_bench.cli.load_config", return_value=cfg),
        patch("narrate_bench.engines.registry.get", return_value=engine1),
        pytest.raises(KeyboardInterrupt),
    ):
        synthesize(engine="mock", book="b", chapter=None)

    assert engine1.calls == 4  # crashed on the 5th attempt, nothing written for it

    # "restart": a fresh engine instance, same cache/data dirs, run again
    engine2 = CrashAfterNEngine(crash_after=None)
    with (
        patch("narrate_bench.cli.load_config", return_value=cfg),
        patch("narrate_bench.engines.registry.get", return_value=engine2),
    ):
        synthesize(engine="mock", book="b", chapter=None)

    assert engine1.calls + engine2.calls == n_chunks  # every chunk synthesized exactly once total
    assert engine2.calls == n_chunks - 4  # only the un-synthesized remainder was redone

    manifest = pd.read_parquet(cfg.paths.data / "synth_manifest.parquet")
    assert len(manifest) == n_chunks
    assert manifest["chunk_id"].nunique() == n_chunks  # no duplicate manifest rows
    assert (manifest["status"] == "ok").all()


def test_silent_output_is_flagged(tmp_path):
    cfg = _make_cfg(tmp_path, n_chunks=1)

    class SilentEngine:
        engine_id = "mock"
        voice_id = "v1"
        params: dict = {}
        max_chars = 1000

        def synthesize(self, text, out_path):
            silence = np.zeros(8000, dtype=np.int16)
            sf.write(str(out_path), silence, 16000, subtype="PCM_16", format="WAV")
            return SynthResult(wall_s=0.01, peak_vram_mb=None, raw_sample_rate=16000)

    with (
        patch("narrate_bench.cli.load_config", return_value=cfg),
        patch("narrate_bench.engines.registry.get", return_value=SilentEngine()),
    ):
        synthesize(engine="mock", book="b", chapter=None)

    manifest = pd.read_parquet(cfg.paths.data / "synth_manifest.parquet")
    assert manifest.iloc[0]["status"] == "silent"


def test_truncated_output_is_flagged(tmp_path):
    cfg = _make_cfg(tmp_path, n_chunks=1)

    class TruncatingEngine:
        engine_id = "mock"
        voice_id = "v1"
        params: dict = {}
        max_chars = 1000

        def synthesize(self, text, out_path):
            # "hello there number 0" at ~15 chars/s expects ~1.5s; give 0.05s.
            audio, sr = _tone(n_samples=800)
            sf.write(str(out_path), audio, sr, subtype="PCM_16", format="WAV")
            return SynthResult(wall_s=0.01, peak_vram_mb=None, raw_sample_rate=sr)

    with (
        patch("narrate_bench.cli.load_config", return_value=cfg),
        patch("narrate_bench.engines.registry.get", return_value=TruncatingEngine()),
    ):
        synthesize(engine="mock", book="b", chapter=None)

    manifest = pd.read_parquet(cfg.paths.data / "synth_manifest.parquet")
    assert manifest.iloc[0]["status"] == "truncated"


def test_normal_output_stays_ok(tmp_path):
    cfg = _make_cfg(tmp_path, n_chunks=1)
    engine = CrashAfterNEngine(crash_after=None)

    with (
        patch("narrate_bench.cli.load_config", return_value=cfg),
        patch("narrate_bench.engines.registry.get", return_value=engine),
    ):
        synthesize(engine="mock", book="b", chapter=None)

    manifest = pd.read_parquet(cfg.paths.data / "synth_manifest.parquet")
    assert manifest.iloc[0]["status"] == "ok"
    conform.check(manifest.iloc[0]["synth_path"])
