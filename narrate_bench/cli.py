"""Typer app; one command per stage + status."""

from __future__ import annotations

import typer
from pydantic import ValidationError

from narrate_bench.config import load_config

app = typer.Typer(add_completion=False)

STAGE_COMMANDS = [
    "prepare",
    "synthesize",
    "align",
    "transcribe",
    "score",
    "embed",
    "analyze",
    "run",
]


def _stub(name: str) -> None:
    print(f"{name}: not implemented")
    raise typer.Exit(2)


@app.command()
def prepare() -> None:
    _stub("prepare")


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
