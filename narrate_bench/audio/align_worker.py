"""Standalone WhisperX forced-alignment worker, run under .venv-whisperx's
interpreter. Isolated from the main venv because whisperx pins
torch~=2.8.0/torchaudio~=2.8.0, incompatible with the main venv's
torch==2.14.0 (needed by XTTS/F5-TTS's torchcodec audio backend) --
see ARCHITECTURE.md's Environment section and TASK_LOG.md's M10 entry.
Talks to align.py's Aligner over stdin/stdout, one JSON object per line, no
dependency on the narrate_bench package (this venv doesn't have it
installed).

Per-chunk rough timing is estimated by character-position proportion of the
chapter's total duration (chapters can be many minutes long; forced-aligning
one giant segment spanning the whole chapter breaks down -- verified
directly: WhisperX's CTC alignment silently stopped after ~45s / 50 of ~800
words on a 5-minute test chapter). Chunk-sized segments give the aligner a
tight enough search window per call, all done in a single batched
whisperx.align() call per chapter.

Usage: python align_worker.py <device: cpu|cuda>
"""

from __future__ import annotations

import json
import os
import sys

# This script's own directory (narrate_bench/audio/) ends up first on
# sys.path when run directly; make sure that never shadows a same-named
# real package (mirrors the same guard in chatterbox_worker.py).
_this_dir = os.path.dirname(os.path.abspath(__file__))
sys.path = [p for p in sys.path if os.path.abspath(p or ".") != _this_dir]

ALIGN_MODEL_NAME = "WAV2VEC2_ASR_LARGE_LV60K_960H"


def _proportional_segments(chunks: list[dict], duration: float) -> list[dict]:
    total_chars = sum(c["char_len"] for c in chunks) + len(chunks)  # +1 per join space
    segments = []
    cum = 0
    for c in chunks:
        start = cum / total_chars * duration
        cum += c["char_len"] + 1
        end = cum / total_chars * duration
        segments.append({"text": c["text"].replace("\n", " "), "start": start, "end": end})
    return segments


def main() -> None:
    device = sys.argv[1] if len(sys.argv) > 1 else "cpu"

    import whisperx

    model_a, metadata = whisperx.load_align_model(language_code="en", device=device, model_name=ALIGN_MODEL_NAME)

    print(json.dumps({"ready": True}), flush=True)

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        request = json.loads(line)
        if request.get("cmd") == "shutdown":
            break

        try:
            chunks = request["chunks"]
            audio = whisperx.load_audio(request["audio_path"])
            duration = len(audio) / 16000
            segments = _proportional_segments(chunks, duration)
            result = whisperx.align(segments, model_a, metadata, audio, device, return_char_alignments=False)

            def _num(v):  # numpy floats (or None) -> plain float, JSON-serializable
                return None if v is None else float(v)

            # whisperx's own per-segment word grouping is not reliable at exact
            # chunk boundaries: a trailing word can land in the *next* input
            # segment's output when that segment's proportional-timing estimate
            # is even slightly early -- verified directly, and it cascades,
            # since every later chunk in the chapter ends up shifted by however
            # many words leaked. The words are still correctly time-ordered
            # overall, so flatten them across all segments and re-split by each
            # chunk's own known word count instead of trusting the returned
            # segment structure.
            flat_words = [
                {"word": w["word"], "start": _num(w.get("start")), "end": _num(w.get("end")), "score": _num(w.get("score"))}
                for seg in result["segments"]
                for w in seg.get("words", [])
            ]

            out_segments = []
            pos = 0
            for c in chunks:
                n = len(c["text"].split())
                out_segments.append({"words": flat_words[pos : pos + n]})
                pos += n

            response = {"segments": out_segments, "error": None}
        except Exception as e:  # let the caller decide whether this aborts the run
            response = {"segments": None, "error": str(e)}
        print(json.dumps(response), flush=True)


if __name__ == "__main__":
    main()
