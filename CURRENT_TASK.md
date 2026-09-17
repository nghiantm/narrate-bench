# CURRENT_TASK.md — Narrate Bench

Read ARCHITECTURE.md first. Work only on the milestone below. When its acceptance criteria pass, append an entry to TASK_LOG.md, mark the milestone `[x]` in IMPLEMENTATION_PLAN.md, and stop. Do not begin the next milestone in the same session.

---

## Active milestone: M10 — Forced alignment and slicing

### Goal
Turn each ingested human chapter WAV (M09) into per-chunk human audio slices, so Track D can compute a WER floor from real narration for every chunk, not just chapter-level audio.

### Scope
1. Check WhisperX's actual package/install situation before assuming it just works — it has its own dependency chain (whisper, pyannote-audio for alignment, ctranslate2) that may collide with the main venv's pinned torch/transformers the same way XTTS and Chatterbox did in M07/M08. Verify early; if it needs its own isolated venv (same pattern as `.venv-chatterbox/`), set that up rather than fighting a conflict blind.
2. `narrate_bench/audio/align.py`: `align(wav_path, text) -> list[WordTiming]` (start_s, end_s, word, score) via WhisperX forced alignment, one call per ingested chapter WAV against that chapter's normalized text (from `data/text/{book}.norm.txt` + `chapters.json`'s char offsets — the same normalized text `nb prepare` already produced, not the raw human transcript, since alignment needs the text to score against).
3. `narrate_bench/audio/slice.py`: for each chunk belonging to an aligned chapter, find its first/last word's timestamps (matching the chunk's text span within the chapter), cut `[first_word_start - pad, last_word_end + pad]` from the chapter WAV, write the slice, run it through `audio.conform()` (M05) so it meets the same contract as synthetic audio. Compute `align_conf` = fraction of the chunk's words that aligned with score > 0.5. Set `human_audio = null` when `align_conf < 0.8` (per ARCHITECTURE.md's schema) rather than writing a low-confidence slice.
4. Update `data/chunks.parquet` in place with the new `human_audio` (path or null) and `align_conf` columns for every chunk in the aligned book(s).
5. Wire into a CLI command (`nb align --book <id>`, filling in the currently-stubbed `align` command in `cli.py`).
6. Cache the alignment step via `ContentCache` (keyed by book/chapter, not per-chunk — alignment runs once per chapter, slicing reads from that cached result) so a rerun doesn't redo WhisperX inference.

### Out of scope
Whisper transcription of synthetic or human audio for WER (M11). Running alignment on all 5 books unattended (see below — this is the "more than an hour" case).

### Acceptance criteria
- One book (use `franklin_autobiography`, already ingested in M09) fully sliced: every one of its chunks gets `human_audio`/`align_conf` written to `chunks.parquet`.
- Exclusion rate (fraction with `align_conf < 0.8`, `human_audio = null`) reported in TASK_LOG.
- 30 slices spot-checked — since I can't literally listen, use the same waveform-sanity-proxy approach from M07/M08 (peak, active-sample fraction, duration vs. expected) plus, ideally, a text/duration sanity cross-check (slice duration roughly matching the chunk's char count at a narration pace) — noted in TASK_LOG.
- Pad and the 0.5/0.8 confidence thresholds tuned if the first attempt produces an implausible exclusion rate (e.g. >30% excluded on a clean single-narrator book like Franklin's should be surprising — investigate before accepting).
- `pytest -q` passes, including all prior milestone tests.

### Verification commands
```
. .venv/bin/activate
pytest -q
nb align --book franklin_autobiography --chapter 0   # or equivalent one-chapter scoping if the CLI ends up needing it, to prove correctness cheaply first
```

### On completion — IMPORTANT, this milestone is flagged as likely exceeding an hour of machine time
Per standing instructions: set up the full pipeline, prove it correct on one chapter (or one short book), then **stop and report the exact command to launch the full 5-book (or however many are ingested) run** rather than running it unattended. Append the TASK_LOG entry with the one-chapter/one-book verification evidence, mark M10 `[x]` in IMPLEMENTATION_PLAN.md only once that scoped run's acceptance criteria pass, then replace this file's active milestone with M11 — Whisper transcription (copy its scope and acceptance criteria from IMPLEMENTATION_PLAN.md and expand into the same sections as above). M11 is also flagged as a likely-long-run milestone — same approach applies there.
