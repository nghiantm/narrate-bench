# CURRENT_TASK.md — Narrate Bench

Read ARCHITECTURE.md first. Work only on the milestone below. When its acceptance criteria pass, append an entry to TASK_LOG.md, mark the milestone `[x]` in IMPLEMENTATION_PLAN.md, and stop. Do not begin the next milestone in the same session.

---

## Active milestone: M05 — Engine base + Piper + audio conform

### Goal
Stand up the `TTSEngine` protocol, the engine registry, the first real engine (Piper, CPU), and the audio contract enforcement every engine's output must pass through — the foundation Track B's remaining engines (M07, M08) plug into.

### Scope
1. `narrate_bench/engines/base.py`: `TTSEngine` Protocol (`engine_id`, `voice_id`, `params`, `max_chars`, `synthesize(text, out_path) -> SynthResult`) and `SynthResult` dataclass, exactly per ARCHITECTURE.md's Interfaces section.
2. `narrate_bench/engines/registry.py`: `name -> factory` mapping, built from `config.yaml`'s `engines` section; a `get(name: str) -> TTSEngine` lookup that raises a clear error on an unknown engine.
3. `narrate_bench/engines/piper.py`: wraps the `piper-tts` package (CPU, ONNX-based — check it installs cleanly via pip with no extra system packages beyond what's already on this machine; if `piper-phonemize` or espeak-ng system libraries are needed, that's the kind of "needs something I must provide" case to flag rather than push through silently).
4. `narrate_bench/audio/conform.py`: enforce the fixed audio contract (WAV PCM16, 16 kHz, mono, peak −1 dBFS, silence trimmed at −40 dBFS with 100 ms pad) using `soundfile`/`numpy` (add to deps; avoid pulling in a heavier audio framework for this). `conform()` transforms; `check()` raises `AssertionError` (or similar) naming which part of the contract was violated.
5. `nb synthesize --engine piper --book <id>`: iterates `chunks.parquet` rows for that book, skips chunks already in the cache (`ContentCache`, stage `synthesize`), calls Piper, runs `conform()` on the output, writes to cache, and appends a synth manifest row (`synth_path, wall_s, dur_s, status`) — write this manifest as its own parquet (e.g. `data/synth_manifest.parquet` or fold into a per-engine section of `results.parquet`'s eventual shape; keep it simple, a flat parquet keyed by `chunk_id, engine_id` is enough for now).
6. `nb status` gains per-engine coverage: chunks total vs. chunks synthesized.

### Out of scope
Kokoro, XTTS, F5-TTS, Chatterbox (M07/M08). Resumability proof and truncated/silent detection (M06 — comes right after this one but is a separate milestone). GPU model loading/guarding (no GPU engine exists yet).

### Acceptance criteria
- Synthesize one full chapter (all its chunks) of one book with Piper.
- Every output file passes `conform.check()`.
- Running `nb synthesize --engine piper --book <id>` a second time makes zero calls into Piper's actual synth function for that chapter's chunks (assert via mock in a test — same resumability pattern as `nb prepare`'s fetch cache).
- `nb status` shows Piper coverage for the book.
- `pytest -q` passes, including all prior milestone tests.

### Verification commands
```
. .venv/bin/activate
pytest -q
nb synthesize --engine piper --book <smallest_book_id> --chapter 0   # or however chapter scoping ends up designed; adjust command to match actual CLI if a --chapter flag is added
nb status
```

### On completion
Append the TASK_LOG entry with the exact `pytest -q` and `nb status` output, mark M05 `[x]` in IMPLEMENTATION_PLAN.md, then replace this file's active milestone with M06 — Resumability proof (copy its scope and acceptance criteria from IMPLEMENTATION_PLAN.md and expand into the same sections as above).

### Before starting
This milestone adds the first ML dependency and downloads a real model file (Piper voice `en_US-lessac-medium`, ~60 MB). If Piper needs anything beyond a clean `pip install` — a system package, a license click-through, a voice file that isn't fetchable by plain HTTP — stop and ask rather than working around it.
