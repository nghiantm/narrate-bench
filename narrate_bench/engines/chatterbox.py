"""Chatterbox GPU voice-cloning engine, run out-of-process in its own venv.

chatterbox-tts hard-pins transformers==5.2.0 and numpy<2.0, incompatible
with XTTS (needs transformers<5) and the rest of this project (numpy 2.x)
in one interpreter. Isolated to .venv-chatterbox/ (set up per
ARCHITECTURE.md); this class talks to a persistent worker subprocess
(chatterbox_worker.py), loaded once, over a one-JSON-object-per-line
stdin/stdout protocol -- same TTSEngine surface as every in-process engine,
so the rest of the codebase (registry, cli.py, gpu_guard) doesn't need to
know the difference.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from narrate_bench.engines.base import SynthResult
from narrate_bench.engines.gpu_guard import acquire, release

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKER_VENV_PYTHON = REPO_ROOT / ".venv-chatterbox" / "bin" / "python"
WORKER_SCRIPT = Path(__file__).with_name("chatterbox_worker.py")


class ChatterboxEngine:
    engine_id = "chatterbox"

    def __init__(self, voice_id: str, params: dict, max_chars: int, reference_clip: Path):
        self.voice_id = voice_id
        self.params = params
        self.max_chars = max_chars

        if not WORKER_VENV_PYTHON.exists():
            raise RuntimeError(
                f"chatterbox worker venv not found at {WORKER_VENV_PYTHON}; "
                "set it up per ARCHITECTURE.md's Environment section before using this engine"
            )

        acquire(self.engine_id)
        try:
            self._proc = subprocess.Popen(
                [str(WORKER_VENV_PYTHON), str(WORKER_SCRIPT), str(reference_clip)],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                text=True,
                bufsize=1,
            )
            ready_line = self._proc.stdout.readline()
            if not ready_line:
                raise RuntimeError("chatterbox worker exited before signaling ready")
            ready = json.loads(ready_line)
            if not ready.get("ready"):
                raise RuntimeError(f"chatterbox worker failed to start: {ready}")
            self.sample_rate = ready["sample_rate"]
        except Exception:
            release(self.engine_id)
            raise

    def synthesize(self, text: str, out_path: Path) -> SynthResult:
        request = {"text": text, "out_path": str(out_path)}
        self._proc.stdin.write(json.dumps(request) + "\n")
        self._proc.stdin.flush()
        response_line = self._proc.stdout.readline()
        if not response_line:
            return SynthResult(wall_s=0.0, peak_vram_mb=None, raw_sample_rate=0, error="chatterbox worker died")
        response = json.loads(response_line)
        return SynthResult(
            wall_s=response["wall_s"],
            peak_vram_mb=response["peak_vram_mb"],
            raw_sample_rate=response["raw_sample_rate"],
            error=response["error"],
        )

    def unload(self) -> None:
        try:
            self._proc.stdin.write(json.dumps({"cmd": "shutdown"}) + "\n")
            self._proc.stdin.flush()
        except (BrokenPipeError, OSError):
            pass
        self._proc.wait(timeout=10)
        release(self.engine_id)
