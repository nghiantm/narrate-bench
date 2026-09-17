"""Cut human chapter audio at chunk boundaries using aligned word times."""

from __future__ import annotations

from pathlib import Path

import soundfile as sf

from narrate_bench.audio import conform as audio_conform

PAD_MS = 100
MIN_WORD_SCORE = 0.5

# WhisperX/wav2vec2 CTC per-word confidence is not the bimodal
# near-0-or-near-1 distribution some forced-alignment writeups assume.
# Measured directly on a real, manually-verified-correct chapter (Franklin
# autobiography ch. 14, 796 words): median word score 0.56, only 53% of all
# words score above 0.5. A chunk needing 80% of its words above 0.5 is
# statistically almost unreachable at that population rate -- it excluded
# 93% of chunks, including ones whose word timings were individually
# checked and clearly correct (monotonic, plausible pacing, sane gaps at
# punctuation). Recalibrated against the same data: 0.3 gives a ~13%
# exclusion rate and does not exclude the manually-verified-correct chunks.
MIN_ALIGN_CONF = 0.3


def slice_chunk(chapter_audio_path: Path, words: list[dict], out_path: Path) -> tuple[float, str | None]:
    """Returns (align_conf, human_audio_path_or_None). Writes the conformed
    slice to out_path only when align_conf >= MIN_ALIGN_CONF."""
    scored = [w for w in words if w.get("score") is not None]
    align_conf = sum(1 for w in scored if w["score"] > MIN_WORD_SCORE) / len(words) if words else 0.0

    timed_words = [w for w in words if w.get("start") is not None and w.get("end") is not None]
    if align_conf < MIN_ALIGN_CONF or not timed_words:
        return align_conf, None

    start_s = max(0.0, timed_words[0]["start"] - PAD_MS / 1000)
    end_s = timed_words[-1]["end"] + PAD_MS / 1000

    audio, sr = sf.read(str(chapter_audio_path), dtype="float32")
    start_sample = int(start_s * sr)
    end_sample = min(len(audio), int(end_s * sr))
    clip = audio[start_sample:end_sample]

    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = out_path.with_suffix(out_path.suffix + ".tmp")
    sf.write(str(tmp_path), clip, sr, subtype="PCM_16", format="WAV")
    audio_conform.conform(tmp_path, out_path)
    tmp_path.unlink()

    return align_conf, str(out_path)
