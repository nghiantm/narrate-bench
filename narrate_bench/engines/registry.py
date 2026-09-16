"""Engine name -> factory registry.

Each builder imports its engine module lazily, so commands that never touch
an engine (`nb prepare`, `nb status`) don't pay for importing torch/coqui-tts
just because `cli.py` imports this module.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from narrate_bench.config import Config, EngineCfg
    from narrate_bench.engines.base import TTSEngine


def _build_piper(cfg: "Config", engine_cfg: "EngineCfg"):
    from narrate_bench.engines.piper import PiperEngine

    return PiperEngine(
        voice_id=engine_cfg.voice_id,
        params=engine_cfg.params,
        max_chars=engine_cfg.max_chars,
        model_dir=cfg.paths.data / "models" / "piper",
    )


def _build_kokoro(cfg: "Config", engine_cfg: "EngineCfg"):
    from narrate_bench.engines.kokoro import KokoroEngine

    return KokoroEngine(
        voice_id=engine_cfg.voice_id,
        params=engine_cfg.params,
        max_chars=engine_cfg.max_chars,
        lang_code=engine_cfg.voice_id[0],  # kokoro convention: 'a' = American English, 'b' = British, ...
    )


def _build_xtts(cfg: "Config", engine_cfg: "EngineCfg"):
    from narrate_bench.audio.reference_clip import ensure_reference_clip
    from narrate_bench.engines.xtts import XTTSEngine

    ref_clip = ensure_reference_clip(Path(engine_cfg.reference_clip))
    return XTTSEngine(
        voice_id=engine_cfg.voice_id,
        params=engine_cfg.params,
        max_chars=engine_cfg.max_chars,
        reference_clip=ref_clip,
    )


_BUILDERS = {
    "piper": _build_piper,
    "kokoro": _build_kokoro,
    "xtts": _build_xtts,
}


def get(name: str, cfg: "Config") -> "TTSEngine":
    if name not in cfg.engines:
        raise ValueError(f"engine {name!r} not configured in config.yaml")
    if name not in _BUILDERS:
        raise ValueError(f"engine {name!r} has no implementation yet (available: {sorted(_BUILDERS)})")
    return _BUILDERS[name](cfg, cfg.engines[name])
