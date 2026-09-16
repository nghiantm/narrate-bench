from unittest.mock import patch

from narrate_bench.cache import ContentCache
from narrate_bench.cli import _prepare_book
from narrate_bench.config import Book, Config, EngineCfg, Paths

FIXTURE_RAW = """Produced by Example Team.

*** START OF THE PROJECT GUTENBERG EBOOK EXAMPLE ***

Contents

   I.   A Beginning
   II.  An End

CHAPTER I.

It was a dark and stormy night.

CHAPTER II.

The plot thickened considerably.

*** END OF THE PROJECT GUTENBERG EBOOK EXAMPLE ***
"""


def _make_cfg(tmp_path):
    book = Book(
        book_id="example",
        gutenberg_id=99999,
        librivox_url="https://example.com",
        chapter_regex=r"^CHAPTER [IVXLC]+\.?$",
    )
    engine = EngineCfg(voice_id="v", max_chars=100, device="cpu", model_revision="1")
    return Config(
        books=[book],
        engines={"piper": engine},
        paths=Paths(data=tmp_path / "data", cache=tmp_path / "cache", results=tmp_path / "results"),
    )


def test_prepare_writes_norm_and_chapters_and_skips_toc(tmp_path):
    cfg = _make_cfg(tmp_path)
    cache = ContentCache(cfg.paths.cache)
    book = cfg.books[0]

    with patch("narrate_bench.cli.gutenberg.fetch", return_value=FIXTURE_RAW):
        _prepare_book(cfg, cache, book)

    norm_path = cfg.paths.data / "text" / "example.norm.txt"
    chapters_path = cfg.paths.data / "text" / "example.chapters.json"
    assert norm_path.exists()
    assert chapters_path.exists()

    norm_text = norm_path.read_text()
    assert "dark and stormy night" in norm_text
    assert "A Beginning" not in norm_text  # indented ToC entry must not be treated as a chapter body

    import json

    chapters = json.loads(chapters_path.read_text())
    assert len(chapters) == 2
    assert chapters[0]["heading"] == "CHAPTER I."
    assert chapters[1]["heading"] == "CHAPTER II."


def test_prepare_second_run_hits_cache_and_is_byte_identical(tmp_path):
    cfg = _make_cfg(tmp_path)
    cache = ContentCache(cfg.paths.cache)
    book = cfg.books[0]
    norm_path = cfg.paths.data / "text" / "example.norm.txt"

    with patch("narrate_bench.cli.gutenberg.fetch", return_value=FIXTURE_RAW) as mock_fetch:
        _prepare_book(cfg, cache, book)
        assert mock_fetch.call_count == 1

    first_norm = norm_path.read_text()

    with patch("narrate_bench.cli.gutenberg.fetch", return_value=FIXTURE_RAW) as mock_fetch:
        _prepare_book(cfg, cache, book)
        assert mock_fetch.call_count == 0

    assert norm_path.read_text() == first_norm
