from unittest.mock import patch

import numpy as np
import pandas as pd
import soundfile as sf

from narrate_bench.audio import conform
from narrate_bench.cli import synthesize
from narrate_bench.config import Book, Config, EngineCfg, Paths
from narrate_bench.engines.base import SynthResult


class CountingEngine:
    engine_id = "mock"
    voice_id = "v1"
    params: dict = {}
    max_chars = 1000

    def __init__(self):
        self.calls = 0

    def synthesize(self, text, out_path):
        self.calls += 1
        tone = (np.sin(2 * np.pi * 440 * np.arange(8000) / 16000) * 8000).astype(np.int16)
        sf.write(str(out_path), tone, 16000, subtype="PCM_16", format="WAV")
        return SynthResult(wall_s=0.01, peak_vram_mb=None, raw_sample_rate=16000)


def _make_cfg(tmp_path):
    book = Book(book_id="b", gutenberg_id=1, librivox_url="https://example.com", chapter_regex="x")
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
                "char_len": 10,
                "word_count": 2,
                "text": f"hello {i}",
                "human_audio": None,
                "align_conf": None,
            }
            for i in range(5)
        ]
    )
    chunks.to_parquet(cfg.paths.data / "chunks.parquet", index=False)
    return cfg


def test_synthesize_second_run_makes_zero_engine_calls(tmp_path):
    cfg = _make_cfg(tmp_path)
    engine = CountingEngine()

    with (
        patch("narrate_bench.cli.load_config", return_value=cfg),
        patch("narrate_bench.engines.registry.get", return_value=engine),
    ):
        synthesize(engine="mock", book="b", chapter=None)
        assert engine.calls == 5

        synthesize(engine="mock", book="b", chapter=None)
        assert engine.calls == 5  # every chunk was a cache hit the second time

    manifest = pd.read_parquet(cfg.paths.data / "synth_manifest.parquet")
    assert len(manifest) == 5
    assert (manifest["status"] == "ok").all()

    for p in manifest["synth_path"]:
        conform.check(p)  # raises if the audio contract was violated


def test_synthesize_writes_conforming_audio(tmp_path):
    cfg = _make_cfg(tmp_path)
    engine = CountingEngine()

    with (
        patch("narrate_bench.cli.load_config", return_value=cfg),
        patch("narrate_bench.engines.registry.get", return_value=engine),
    ):
        synthesize(engine="mock", book="b", chapter=None)

    manifest = pd.read_parquet(cfg.paths.data / "synth_manifest.parquet")
    row = manifest.iloc[0]
    info = sf.info(row["synth_path"])
    assert info.samplerate == conform.TARGET_SR
    assert info.channels == 1
    assert row["audio_dur_s"] > 0
