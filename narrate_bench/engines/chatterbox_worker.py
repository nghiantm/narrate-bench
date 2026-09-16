"""Standalone Chatterbox TTS worker, run under .venv-chatterbox's interpreter.

Isolated from the main venv because chatterbox-tts hard-pins
transformers==5.2.0 and numpy<2, incompatible with XTTS (needs
transformers<5) and the rest of this project (numpy 2.x) in one
interpreter -- see ARCHITECTURE.md's concurrency section and TASK_LOG.md's
M08 entry. Talks to ChatterboxEngine over stdin/stdout, one JSON object per
line, no dependency on the narrate_bench package (this venv doesn't have it
installed).

Usage: python chatterbox_worker.py <reference_clip_path>
"""

from __future__ import annotations

import json
import os
import sys

# This script's own directory (narrate_bench/engines/) ends up first on
# sys.path when run directly, and it contains our chatterbox.py -- which
# would shadow the real pip-installed `chatterbox` package. Drop it before
# importing anything from that package.
_this_dir = os.path.dirname(os.path.abspath(__file__))
sys.path = [p for p in sys.path if os.path.abspath(p or ".") != _this_dir]

# chatterbox/perth print plain status lines (e.g. "loaded PerthNet...")
# straight to stdout, which would corrupt our one-JSON-object-per-line
# protocol. Redirect the process's real stdout fd to stderr for everything,
# keeping a private handle on the original fd 1 for our own protocol
# messages only (via _send below).
_protocol_out = os.fdopen(os.dup(sys.stdout.fileno()), "w")
os.dup2(sys.stderr.fileno(), sys.stdout.fileno())


def _send(obj: dict) -> None:
    print(json.dumps(obj), file=_protocol_out, flush=True)


import time  # noqa: E402

import soundfile as sf  # noqa: E402
import torch  # noqa: E402
from chatterbox.tts import ChatterboxTTS  # noqa: E402


def main() -> None:
    reference_clip = sys.argv[1]
    device = "cuda" if torch.cuda.is_available() else "cpu"

    model = ChatterboxTTS.from_pretrained(device=device)
    model.prepare_conditionals(reference_clip)

    _send({"ready": True, "sample_rate": model.sr})

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        request = json.loads(line)
        if request.get("cmd") == "shutdown":
            break

        text = request["text"]
        out_path = request["out_path"]
        t0 = time.monotonic()
        if torch.cuda.is_available():
            torch.cuda.reset_peak_memory_stats()
        try:
            wav = model.generate(text)
            sf.write(out_path, wav.squeeze(0).cpu().numpy(), model.sr, subtype="PCM_16", format="WAV")
            peak_vram_mb = (
                int(torch.cuda.max_memory_allocated() / (1024 * 1024)) if torch.cuda.is_available() else None
            )
            response = {
                "wall_s": time.monotonic() - t0,
                "peak_vram_mb": peak_vram_mb,
                "raw_sample_rate": model.sr,
                "error": None,
            }
        except Exception as e:  # let the caller decide whether this aborts the run
            response = {
                "wall_s": time.monotonic() - t0,
                "peak_vram_mb": None,
                "raw_sample_rate": 0,
                "error": str(e),
            }
        _send(response)


if __name__ == "__main__":
    main()
