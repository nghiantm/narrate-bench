# CURRENT_TASK.md — Narrate Bench

Read ARCHITECTURE.md first. Work only on the milestone below. When its acceptance criteria pass, append an entry to TASK_LOG.md, mark the milestone `[x]` in IMPLEMENTATION_PLAN.md, and stop. Do not begin the next milestone in the same session.

---

## Active milestone: M11 — Whisper transcription

### Goal
Transcribe both synthetic (TTS) and human audio through the same frozen Whisper settings, so Track D can score intelligibility against a common yardstick.

### Scope
1. `narrate_bench/asr/whisper.py`: `transcribe(path) -> str` using faster-whisper with ARCHITECTURE.md's frozen settings exactly (`large-v3`, float16, beam 5, temperature 0, `condition_on_previous_text=False`, `vad_filter=True`, language `en`). This almost certainly belongs in `.venv-whisperx/` too (`whisperx` already bundles `faster-whisper`, confirmed in M10's install) — reuse that venv and the same subprocess-worker pattern (`asr/whisper_worker.py`?) rather than setting up a fourth environment. Confirm `faster-whisper`'s API directly before assuming the call shape; don't guess from memory.
2. Cache transcription per chunk via `ContentCache` (stage `transcribe`, keyed by chunk_id + `model_version` = whisper settings fingerprint) so reruns make zero model calls — mirrors the resumability pattern already proven for synthesis (M06) and alignment (M10).
3. `nb transcribe --source {engine|human|all} [--engine <name>] [--book <id>]`: for `engine`, transcribes each cached synth output in `synth_manifest.parquet`; for `human`, transcribes each `human_audio` slice from M10's `chunks.parquet` column; for `all`, both. Store the hypothesis text — decide where (a new `whisper_hyp` column joined back into the relevant manifest/parquet, matching ARCHITECTURE.md's `results.parquet` schema which has a `whisper_hyp` column, so the natural home is wherever M12 will build `results.parquet` from — check whether that means writing to an intermediate file now or waiting for M12's join step; don't invent a schema M12 will just have to reshape).
4. GPU vs CPU: Whisper `large-v3` is heavy; check whether CPU transcription is fast enough for this project's scale before assuming GPU is required, and if GPU, apply the same "don't run concurrently with an active TTS GPU job" discipline established in M07/M08/M10.

### Out of scope
WER scoring itself, `excess_wer` computation, `results.parquet`/`human_results.parquet` construction (M12). Running on all 5 books (this is flagged as a likely long-run milestone — see below).

### Acceptance criteria
- Transcribes one book's human slices (from M10, `franklin_autobiography`) and one engine's synth output (Piper, already fully synthesized for `treasure_island` from the earlier full-book checkpoint — or resynthesize a small set if a cleaner one-book overlap between M09/M10's book and a synthesized book is needed) through frozen Whisper settings.
- Rerun makes zero model calls (cache hit path, same proof pattern as M05/M06).
- Hypothesis text is stored somewhere sensible and inspectable (print a few examples in TASK_LOG showing hypothesis vs. source/reference text look plausible).
- `pytest -q` passes, including all prior milestone tests.

### Verification commands
```
. .venv/bin/activate
pytest -q
nb transcribe --source human --book franklin_autobiography --chapter 13   # or whatever chapter/book scoping the CLI ends up needing, matching M10's proof scope
```

### On completion — this milestone is flagged as likely exceeding an hour for a full run
Set up the full pipeline, prove correct on a small scope (one chapter/book's worth), then stop and report the exact command for the full run rather than executing it unattended. Append the TASK_LOG entry with that scoped verification evidence, mark M11 `[x]` in IMPLEMENTATION_PLAN.md, then replace this file's active milestone with M12 — WER scoring and excess_wer (copy its scope and acceptance criteria from IMPLEMENTATION_PLAN.md and expand into the same sections as above).
