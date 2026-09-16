# CURRENT_TASK.md — Narrate Bench

Read ARCHITECTURE.md first. Work only on the milestone below. When its acceptance criteria pass, append an entry to TASK_LOG.md, mark the milestone `[x]` in IMPLEMENTATION_PLAN.md, and stop. Do not begin the next milestone in the same session.

---

## Active milestone: M09 — LibriVox ingest

### Goal
Download the human-narrated LibriVox audio for each book, conform it to the audio contract, and verify chapter counts match the text chapter index built in M03 — the human baseline Track D's scoring will compare synthetic engines against.

### Scope
1. Verify each of the 5 books' `librivox_url` in `config.yaml` actually points to a real, single-narrator LibriVox recording, the same way M03 had to fix wrong `gutenberg_id`/`chapter_regex` values and M07 had to verify a LibriVox book's narrator count before using it as the reference-clip source. Use the LibriVox API (`https://librivox.org/api/feed/audiobooks/?...`) to confirm section list, per-section narrator(s), and per-section MP3 URLs for each configured book — do not trust the M01 placeholder URLs. Note: `treasure_island`'s configured URL includes "version-4" — check whether that specific version exists and is single-narrator, or find the one that is (same due diligence as the Franklin autobiography check in M07, which found id 1143 was the clean single-narrator one).
2. Download each book's chapter-level MP3s (or section MP3s, if LibriVox's section boundaries don't align 1:1 with the text chapter index — handle the mismatch via a configured merge/split map per the milestone's own acceptance criterion, not by silently guessing).
3. Conform each to the audio contract via `audio.conform()` (16 kHz mono PCM16, etc. — same function M05 built, reused here rather than duplicated).
4. Verify chapter count matches `data/text/{book_id}.chapters.json`'s chapter count; on mismatch, raise a clear error naming which chapters don't line up (not a silent skip).
5. Write `data/audio/human/{book_id}/{chapter_idx}.wav` (or similar naming — match whatever `chapters.json` uses for chapter identity, likely 0-based `chapter_idx`).
6. Use `ContentCache` for the raw MP3 download step (same pattern as `nb prepare`'s Gutenberg fetch caching), since these are large files and re-downloading on every rerun would be wasteful and slow.

### Out of scope
Forced alignment / chunk-level slicing (M10). Whisper transcription of human audio (M11). Full 5-book ingest is not required by this milestone's acceptance criterion — one book is enough to prove the pipeline, though there's no reason not to do all 5 if it's cheap once the mechanism works.

### Acceptance criteria
- `data/audio/human/{book}/{chapter}.wav` exists for at least one full book, every file passing `conform.check()`.
- A deliberately mismatched chapter count (or a real one, if one of the 5 books turns out to have a mismatch) produces a clear error naming the specific chapters involved, not a silent partial result.
- `pytest -q` passes, including all prior milestone tests.

### Verification commands
```
. .venv/bin/activate
pytest -q
nb align --book <chosen_book_id>   # or whatever command name this milestone ends up wiring — adjust to match cli.py's actual stage command, may need a new command distinct from the existing `align` stub if that name is reserved for M10's forced-alignment stage
```

### On completion
Append the TASK_LOG entry with exact `pytest -q` output and the chapter-count verification evidence, mark M09 `[x]` in IMPLEMENTATION_PLAN.md, then replace this file's active milestone with M10 — Forced alignment and slicing (copy its scope and acceptance criteria from IMPLEMENTATION_PLAN.md and expand into the same sections as above). M10 is one of the three milestones (M10, M11, M14) the user's own instructions flag as likely exceeding an hour of machine time for a full run — set it up and run it on one chapter, then report the command to launch the full run rather than running it unattended.
