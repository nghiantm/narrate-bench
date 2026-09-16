# CURRENT_TASK.md — Narrate Bench

Read ARCHITECTURE.md first. Work only on the milestone below. When its acceptance criteria pass, append an entry to TASK_LOG.md, mark the milestone `[x]` in IMPLEMENTATION_PLAN.md, and stop. Do not begin the next milestone in the same session.

---

## Active milestone: M08 — F5-TTS and Chatterbox

### Goal
Complete the GPU voice-cloning trio (XTTS done in M07) with F5-TTS and Chatterbox, both using the same shared reference clip, and add per-chunk peak VRAM tracking now that more than one GPU engine exists.

### Scope
1. Find and check the actual pip package / install path for each engine before assuming API shape — do not guess:
   - F5-TTS: likely `f5-tts` on PyPI (check `pip index versions f5-tts`), or may need installing from source/GitHub if not packaged. Check its actual max reference-audio length and max generation-text-length constraints directly (the way M07 discovered XTTS's real 250-char limit the hard way) before trusting `config.yaml`'s current `max_chars: 400` placeholder.
   - Chatterbox: likely `chatterbox-tts` on PyPI. Same check for its real text-length ceiling and reference-clip requirements (duration, sample rate expectations).
2. `narrate_bench/engines/f5tts.py`, `narrate_bench/engines/chatterbox.py`: load once at construction (compute/cache any reference-clip conditioning the same way XTTS's latents are cached, if the library supports it — don't recompute from the wav file every chunk if avoidable), `synthesize(text, out_path) -> SynthResult` per protocol, using `narrate_bench.engines.gpu_guard.acquire/release` the same way `XTTSEngine` does.
3. `peak_vram_mb`: record via `torch.cuda.max_memory_allocated()` per chunk. Check the actual reset semantics before trusting a number — `max_memory_allocated` is cumulative since the last `torch.cuda.reset_peak_memory_stats()` call, not since the last chunk, so get the reset point right (probably: reset right before each `synthesize()` call) or the numbers will be meaningless.
4. Register both in `narrate_bench/engines/registry.py`.
5. Update `config.yaml`: correct `max_chars` for f5tts/chatterbox once their real limits are known (the shared chunker cap is `min()` across all configured engines — if either is lower than XTTS's 250, the cap drops further and `chunks.parquet` needs regenerating again, same as M07's fix). Pin exact model revisions once loaded, matching ARCHITECTURE.md's pinned-models section; update that section's `# verify` framing if reality differs from what's written there.
6. `nb synthesize`: thread `peak_vram_mb` from `SynthResult` into the manifest row (currently hardcoded absent for CPU/XTTS-without-tracking engines — check `_synthesize_chunk` in `cli.py`).

### Out of scope
Any Track C (human baseline, M09/M10) or Track D (scoring, M11+) work. Whisper.

### Acceptance criteria
- Synthesize one chapter each with F5-TTS and Chatterbox on the RTX 3070 without OOM.
- Every output passes `conform.check()`.
- `engine_error` status recorded (not raised, not aborting the run) on a deliberately malformed input for each engine — extend `tests/test_synthesize.py`-style mock-based tests or add real ones.
- `peak_vram_mb` is populated and non-null for GPU engine manifest rows, with a sane order of magnitude (not zero, not absent) — spot check a few values by hand against what `nvidia-smi`-class tooling would suggest, noting M07's WSL2 `nvidia-smi` reporting limitation if it recurs.
- 5-chunk spot-check per engine noted in TASK_LOG.md (same waveform-sanity-proxy approach as M07, given I can't literally listen).
- `pytest -q` passes, including all prior milestone tests.

### Verification commands
```
. .venv/bin/activate
pytest -q
nb synthesize --engine f5tts --book <smallest_book_id> --chapter 0
nb synthesize --engine chatterbox --book <smallest_book_id> --chapter 0
nb status
```

### On completion
Append the TASK_LOG entry with exact `pytest -q` output and per-engine spot-check notes, mark M08 `[x]` in IMPLEMENTATION_PLAN.md, then replace this file's active milestone with M09 — LibriVox ingest (copy its scope and acceptance criteria from IMPLEMENTATION_PLAN.md and expand into the same sections as above). Track B (all 5 synthesis engines) will be fully done after M08 — worth pausing to confirm with the user before starting Track C (human baseline) whether they want a quick full-book synthesis run across all 5 engines first, or to proceed straight into the human-narration pipeline. M09 also needs the LibriVox `librivox_url` fields in `config.yaml` verified against real chapter-track lists (like M03 had to fix `chapter_regex` and gutenberg_id for real content) — check chapter/track alignment for each of the 5 books before assuming the configured URLs map cleanly to the existing `chapters.json` files.
