"""Engine name -> factory registry."""

from __future__ import annotations

from typing import TYPE_CHECKING

from narrate_bench.engines.piper import PiperEngine

if TYPE_CHECKING:
    from narrate_bench.config import Config
    from narrate_bench.engines.base import TTSEngine

_BUILDERS = {
    "piper": lambda cfg, engine_cfg: PiperEngine(
        voice_id=engine_cfg.voice_id,
        params=engine_cfg.params,
        max_chars=engine_cfg.max_chars,
        model_dir=cfg.paths.data / "models" / "piper",
    ),
}


def get(name: str, cfg: "Config") -> "TTSEngine":
    if name not in cfg.engines:
        raise ValueError(f"engine {name!r} not configured in config.yaml")
    if name not in _BUILDERS:
        raise ValueError(f"engine {name!r} has no implementation yet (available: {sorted(_BUILDERS)})")
    return _BUILDERS[name](cfg, cfg.engines[name])
