"""WhisperX forced alignment -> word timestamps, one chapter at a time.

Runs out-of-process in `.venv-whisperx/` (set up per ARCHITECTURE.md) via
`align_worker.py`, the same pattern as `engines/chatterbox.py` -- see that
module's docstring and TASK_LOG.md's M10 entry for why.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKER_VENV_PYTHON = REPO_ROOT / ".venv-whisperx" / "bin" / "python"
WORKER_SCRIPT = Path(__file__).with_name("align_worker.py")

ALIGN_MODEL_NAME = "WAV2VEC2_ASR_LARGE_LV60K_960H"  # keep in sync with align_worker.py; used for cache keys


class Aligner:
    def __init__(self, device: str = "cpu"):
        if not WORKER_VENV_PYTHON.exists():
            raise RuntimeError(
                f"whisperx worker venv not found at {WORKER_VENV_PYTHON}; "
                "set it up per ARCHITECTURE.md's Environment section before using this module"
            )
        self._proc = subprocess.Popen(
            [str(WORKER_VENV_PYTHON), str(WORKER_SCRIPT), device],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        ready_line = self._proc.stdout.readline()
        if not ready_line:
            raise RuntimeError("align worker exited before signaling ready")
        ready = json.loads(ready_line)
        if not ready.get("ready"):
            raise RuntimeError(f"align worker failed to start: {ready}")

    def align_chapter(self, audio_path: Path, chunks: list[dict]) -> list[dict]:
        """chunks: ordered list of {"text": str, "char_len": int} for one chapter.
        Returns one {"words": [{"word","start","end","score"}, ...]} dict per chunk,
        in the same order."""
        request = {"audio_path": str(audio_path), "chunks": chunks}
        self._proc.stdin.write(json.dumps(request) + "\n")
        self._proc.stdin.flush()
        response_line = self._proc.stdout.readline()
        if not response_line:
            raise RuntimeError("align worker died mid-run")
        response = json.loads(response_line)
        if response["error"] is not None:
            raise RuntimeError(response["error"])
        return response["segments"]

    def close(self) -> None:
        try:
            self._proc.stdin.write(json.dumps({"cmd": "shutdown"}) + "\n")
            self._proc.stdin.flush()
        except (BrokenPipeError, OSError):
            pass
        self._proc.wait(timeout=10)

    def __enter__(self) -> "Aligner":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
