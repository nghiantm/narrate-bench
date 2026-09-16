"""Typer app; one command per stage + status."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pandas as pd
import soundfile as sf
import typer
from pydantic import ValidationError

from narrate_bench.audio import conform as audio_conform
from narrate_bench.cache import ContentCache
from narrate_bench.config import Config, load_config
from narrate_bench.engines import registry
from narrate_bench.text import chunk as text_chunk
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


def _prepare_book(cfg: Config, cache: ContentCache, book) -> tuple[str, list[dict]]:
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
    return normalized, chapters


@app.command()
def prepare() -> None:
    cfg = load_config()
    cache = ContentCache(cfg.paths.cache)
    max_chars = min(e.max_chars for e in cfg.engines.values())

    all_chunks = []
    for book in cfg.books:
        normalized, chapters = _prepare_book(cfg, cache, book)
        rows = text_chunk.build_chunks(book.book_id, normalized, chapters, max_chars)
        buckets = pd.Series([r["bucket"] for r in rows]).value_counts().to_dict()
        print(f"  {len(rows)} chunks, buckets={buckets}")
        all_chunks.extend(rows)

    chunks_df = pd.DataFrame(all_chunks)
    cfg.paths.data.mkdir(parents=True, exist_ok=True)
    chunks_df.to_parquet(cfg.paths.data / "chunks.parquet", index=False)


CHARS_PER_SECOND = 15.0  # ~150 words/min typical audiobook narration pace


def _load_manifest(manifest_path: Path) -> pd.DataFrame:
    if manifest_path.exists():
        return pd.read_parquet(manifest_path)
    return pd.DataFrame(
        columns=["chunk_id", "engine_id", "synth_path", "wall_s", "peak_vram_mb", "audio_dur_s", "status"]
    )


def _classify(path: Path, text: str) -> tuple[str, float]:
    info = sf.info(str(path))
    audio_dur_s = info.frames / info.samplerate
    expected_s = len(text) / CHARS_PER_SECOND
    if audio_conform.is_silent(path):
        return "silent", audio_dur_s
    if audio_dur_s < 0.4 * expected_s:
        return "truncated", audio_dur_s
    return "ok", audio_dur_s


def _synthesize_chunk(eng, cache: ContentCache, model_revision: str, chunk_id: str, text: str) -> dict:
    key = cache.key(
        stage="synthesize",
        engine_id=eng.engine_id,
        voice_id=eng.voice_id,
        params=eng.params,
        model_version=model_revision,
        chunk_id=chunk_id,
    )
    timing: dict = {}

    def producer(tmp_path: Path) -> None:
        raw_tmp = tmp_path.with_suffix(".raw.wav")
        result = eng.synthesize(text, raw_tmp)
        if result.error is not None:
            raw_tmp.unlink(missing_ok=True)
            raise RuntimeError(result.error)
        audio_conform.conform(raw_tmp, tmp_path)
        raw_tmp.unlink(missing_ok=True)
        timing["wall_s"] = result.wall_s
        timing["peak_vram_mb"] = result.peak_vram_mb

    try:
        final_path = cache.write_atomic(key, producer)
    except Exception as e:  # per-chunk failures must not abort the run
        return {
            "chunk_id": chunk_id,
            "engine_id": eng.engine_id,
            "synth_path": None,
            "wall_s": None,
            "peak_vram_mb": None,
            "audio_dur_s": None,
            "status": f"engine_error: {e}",
        }

    status, audio_dur_s = _classify(final_path, text)
    return {
        "chunk_id": chunk_id,
        "engine_id": eng.engine_id,
        "synth_path": str(final_path),
        "wall_s": timing["wall_s"],
        "peak_vram_mb": timing["peak_vram_mb"],
        "audio_dur_s": audio_dur_s,
        "status": status,
    }


@app.command()
def synthesize(
    engine: str = typer.Option(..., "--engine"),
    book: str = typer.Option(..., "--book"),
    chapter: int = typer.Option(None, "--chapter"),
) -> None:
    cfg = load_config()
    eng = registry.get(engine, cfg)
    cache = ContentCache(cfg.paths.cache)

    chunks_path = cfg.paths.data / "chunks.parquet"
    if not chunks_path.exists():
        print("chunks.parquet not found; run `nb prepare` first")
        raise typer.Exit(1)

    df = pd.read_parquet(chunks_path)
    df = df[df["book_id"] == book]
    if chapter is not None:
        df = df[df["chapter_idx"] == chapter]
    if df.empty:
        print(f"no chunks found for book={book!r} chapter={chapter!r}")
        raise typer.Exit(1)

    manifest_path = cfg.paths.data / "synth_manifest.parquet"
    manifest = _load_manifest(manifest_path)
    existing_keys = set(zip(manifest["chunk_id"], manifest["engine_id"]))
    model_revision = cfg.engines[engine].model_revision

    new_rows = []
    n_cached = n_synth = 0
    for row in df.itertuples():
        key = cache.key(
            stage="synthesize",
            engine_id=eng.engine_id,
            voice_id=eng.voice_id,
            params=eng.params,
            model_version=model_revision,
            chunk_id=row.chunk_id,
        )
        if cache.has(key):
            n_cached += 1
            if (row.chunk_id, eng.engine_id) not in existing_keys:
                status, audio_dur_s = _classify(cache.path(key), row.text)
                new_rows.append(
                    {
                        "chunk_id": row.chunk_id,
                        "engine_id": eng.engine_id,
                        "synth_path": str(cache.path(key)),
                        "wall_s": None,
                        "peak_vram_mb": None,  # not recoverable from a cache hit alone
                        "audio_dur_s": audio_dur_s,
                        "status": status,
                    }
                )
            continue
        n_synth += 1
        new_rows.append(_synthesize_chunk(eng, cache, model_revision, row.chunk_id, row.text))

    if new_rows:
        manifest = pd.concat([manifest, pd.DataFrame(new_rows)], ignore_index=True)
        manifest = manifest.drop_duplicates(subset=["chunk_id", "engine_id"], keep="last")
        manifest.to_parquet(manifest_path, index=False)

    print(f"{book}: {n_synth} synthesized, {n_cached} already cached, {len(df)} total chunks")


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

    chunks_path = cfg.paths.data / "chunks.parquet"
    if chunks_path.exists():
        chunks = pd.read_parquet(chunks_path)
        manifest_path = cfg.paths.data / "synth_manifest.parquet"
        manifest = _load_manifest(manifest_path)
        total = len(chunks)
        print(f"synthesis coverage ({total} chunks total):")
        for name in cfg.engines:
            done = manifest.loc[
                (manifest["engine_id"] == name) & (manifest["status"] == "ok"), "chunk_id"
            ].nunique()
            print(f"  {name}: {done}/{total}")


if __name__ == "__main__":
    app()
