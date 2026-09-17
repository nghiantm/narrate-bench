import json
from unittest.mock import patch

import numpy as np
import pytest
import soundfile as sf
import typer

from narrate_bench.cli import ingest
from narrate_bench.config import Book, Config, EngineCfg, Paths

FAKE_SECTIONS = [
    {"section_number": "1", "listen_url": "https://example.com/1.mp3", "title": "Chapter 1"},
    {"section_number": "2", "listen_url": "https://example.com/2.mp3", "title": "Chapter 2"},
]


def _make_cfg(tmp_path, chapter_map=None, n_chapters=2):
    book = Book(
        book_id="b",
        gutenberg_id=1,
        librivox_id=999,
        librivox_url="https://example.com",
        chapter_regex="x",
        chapter_map=chapter_map,
    )
    engine_cfg = EngineCfg(voice_id="v", max_chars=100, device="cpu", model_revision="1")
    cfg = Config(
        books=[book],
        engines={"piper": engine_cfg},
        paths=Paths(data=tmp_path / "data", cache=tmp_path / "cache", results=tmp_path / "results"),
    )
    text_dir = cfg.paths.data / "text"
    text_dir.mkdir(parents=True)
    chapters = [{"heading": f"CH {i}", "start_char": i * 10, "end_char": (i + 1) * 10} for i in range(n_chapters)]
    (text_dir / "b.chapters.json").write_text(json.dumps(chapters))
    return cfg


def _fake_download(url, dest):
    tone = (np.sin(2 * np.pi * 440 * np.arange(16000) / 16000) * 8000).astype(np.int16)
    sf.write(str(dest), tone, 16000, subtype="PCM_16", format="WAV")


def test_ingest_writes_conforming_audio_per_chapter(tmp_path):
    cfg = _make_cfg(tmp_path, chapter_map={"1": "0", "2": "1"}, n_chapters=2)

    with (
        patch("narrate_bench.cli.load_config", return_value=cfg),
        patch("narrate_bench.audio.librivox.fetch_sections", return_value=FAKE_SECTIONS) as mock_fetch,
        patch("narrate_bench.cli.urllib.request.urlopen"),
        patch("narrate_bench.cli.shutil.copyfileobj"),
        patch(
            "narrate_bench.cli.audio_conform.conform",
            side_effect=lambda src, dst: _fake_download(None, dst),
        ),
    ):
        ingest(book="b")
        assert mock_fetch.call_count == 1

    out_dir = cfg.paths.data / "audio" / "human" / "b"
    assert (out_dir / "0.wav").exists()
    assert (out_dir / "1.wav").exists()


def test_ingest_mismatch_without_chapter_map_exits_with_clear_error(tmp_path):
    cfg = _make_cfg(tmp_path, chapter_map=None, n_chapters=5)  # 5 chapters, but only 2 fake sections

    with (
        patch("narrate_bench.cli.load_config", return_value=cfg),
        patch("narrate_bench.audio.librivox.fetch_sections", return_value=FAKE_SECTIONS),
        pytest.raises(typer.Exit),
    ):
        ingest(book="b")
