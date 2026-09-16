"""Pydantic model for config.yaml."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict


class Book(BaseModel):
    model_config = ConfigDict(extra="forbid")

    book_id: str
    gutenberg_id: int
    librivox_url: str
    chapter_regex: str
    chapter_map: dict[str, str] | None = None


class EngineCfg(BaseModel):
    model_config = ConfigDict(extra="forbid")

    voice_id: str
    params: dict = {}
    max_chars: int
    device: Literal["cpu", "cuda"]
    model_revision: str
    reference_clip: str | None = None


class WhisperCfg(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model: str = "large-v3"
    backend: str = "faster-whisper"
    compute_type: str = "float16"
    beam_size: int = 5
    temperature: float = 0.0
    condition_on_previous_text: bool = False
    vad_filter: bool = True
    language: str = "en"


class SamplePlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["full", "every_nth_chapter"] = "full"
    n: int | None = None


class Paths(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: Path = Path("data")
    cache: Path = Path("cache")
    results: Path = Path("results")


class Config(BaseModel):
    model_config = ConfigDict(extra="forbid")

    books: list[Book]
    engines: dict[str, EngineCfg]
    whisper: WhisperCfg = WhisperCfg()
    sample_plan: SamplePlan = SamplePlan()
    paths: Paths = Paths()


def load_config(path: Path | str = "config.yaml") -> Config:
    with open(path) as f:
        raw = yaml.safe_load(f)
    return Config.model_validate(raw)
