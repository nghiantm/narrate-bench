"""Typer app; one command per stage + status."""

from __future__ import annotations

import json

import typer
from pydantic import ValidationError

from narrate_bench.cache import ContentCache
from narrate_bench.config import Config, load_config
from narrate_bench.text import gutenberg
from narrate_bench.text import normalize as text_normalize

app = typer.Typer(add_completion=False)


def _stub(name: str) -> None:
    print(f"{name}: not implemented")
    raise typer.Exit(2)


def _fetch_cached(cache: ContentCache, gutenberg_id: int) -> str:
    key = cache.key(
        stage="fetch_gutenberg",
        engine_id="",
        voice_id="",
        params={},
        model_version="1",
        chunk_id=str(gutenberg_id),
    )
    if not cache.has(key):
        raw = gutenberg.fetch(gutenberg_id)
        cache.write_atomic(key, lambda path: path.write_text(raw, encoding="utf-8"))
    return cache.path(key).read_text(encoding="utf-8")


def _prepare_book(cfg: Config, cache: ContentCache, book) -> None:
    raw = _fetch_cached(cache, book.gutenberg_id)
    stripped = gutenberg.strip_boilerplate(raw)

    # Split on the raw (pre-normalize) text: normalizing first would strip
    # the leading indentation that distinguishes a real chapter heading from
    # an indented table-of-contents entry with the same text shape.
    raw_chapters = gutenberg.split_chapters(stripped, book.chapter_regex)

    parts = []
    chapters = []
    pos = 0
    for c in raw_chapters:
        body = text_normalize.normalize(stripped[c["start_char"] : c["end_char"]]).rstrip("\n")
        start = pos
        end = pos + len(body)
        chapters.append({"heading": c["heading"], "start_char": start, "end_char": end})
        parts.append(body)
        pos = end + 1  # account for the "\n" join separator below

    normalized = "\n".join(parts) + "\n"

    text_dir = cfg.paths.data / "text"
    text_dir.mkdir(parents=True, exist_ok=True)
    (text_dir / f"{book.book_id}.norm.txt").write_text(normalized, encoding="utf-8")
    (text_dir / f"{book.book_id}.chapters.json").write_text(
        json.dumps(chapters, indent=2), encoding="utf-8"
    )
    print(f"{book.book_id}: {len(chapters)} chapters, {len(normalized)} chars")


@app.command()
def prepare() -> None:
    cfg = load_config()
    cache = ContentCache(cfg.paths.cache)
    for book in cfg.books:
        _prepare_book(cfg, cache, book)


@app.command()
def synthesize() -> None:
    _stub("synthesize")


@app.command()
def align() -> None:
    _stub("align")


@app.command()
def transcribe() -> None:
    _stub("transcribe")


@app.command()
def score() -> None:
    _stub("score")


@app.command()
def embed() -> None:
    _stub("embed")


@app.command()
def analyze() -> None:
    _stub("analyze")


@app.command()
def run() -> None:
    _stub("run")


@app.command()
def status() -> None:
    try:
        cfg = load_config()
    except (FileNotFoundError, ValidationError) as e:
        print(f"config error: {e}")
        raise typer.Exit(1)

    print(f"books ({len(cfg.books)}):")
    for b in cfg.books:
        print(f"  {b.book_id} (gutenberg {b.gutenberg_id})")

    print(f"engines ({len(cfg.engines)}):")
    for name, e in cfg.engines.items():
        print(f"  {name}: voice={e.voice_id} device={e.device} revision={e.model_revision}")

    print("whisper:")
    print(f"  model={cfg.whisper.model} backend={cfg.whisper.backend} beam={cfg.whisper.beam_size}")


if __name__ == "__main__":
    app()
