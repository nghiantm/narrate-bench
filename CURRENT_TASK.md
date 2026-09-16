# CURRENT_TASK.md — Narrate Bench

Read ARCHITECTURE.md first. Work only on the milestone below. When its acceptance criteria pass, append an entry to TASK_LOG.md, mark the milestone `[x]` in IMPLEMENTATION_PLAN.md, and stop. Do not begin the next milestone in the same session.

---

## Active milestone: M06 — Resumability proof

### Goal
Prove synthesis is safely resumable after a crash (no duplicate work, no lost chunks), and add the two failure-status detections ARCHITECTURE.md's `results.parquet` schema expects: `silent` and `truncated`.

### Scope
1. `tests/test_resumability.py`: a mock engine that raises after N calls (simulating a crash mid-run). Drive `nb synthesize`'s underlying per-chunk loop (call the same building blocks `nb synthesize` itself uses — `_synthesize_chunk` plus the cache-skip logic in `cli.synthesize`, refactor if that logic needs to be more directly testable/restartable) against a chunk set, let it crash partway, then "restart" it (call again with a fresh mock engine instance, same cache dir) and assert: total `engine.synthesize()` calls across both runs == total chunk count (no chunk synthesized twice, none skipped).
2. `status=silent` detection: after `conform()`, compute RMS of the conformed audio; if below a threshold (pick and justify a concrete dBFS value relative to the contract's −40 dBFS silence-trim floor), mark the manifest row `status="silent"` instead of `"ok"`.
3. `status=truncated` detection: compare `audio_dur_s` against an expected duration from a chars-per-second prior (pick and justify a words/characters-per-second reading-speed constant appropriate for audiobook narration, e.g. derived from typical narration rates); if `audio_dur_s < 0.4 * expected`, mark `status="truncated"`.
4. A test with a deliberately truncated/silent mock engine output proves both get flagged correctly (and that a normal-length, normal-volume output stays `"ok"`).

### Out of scope
Kokoro, XTTS, F5-TTS, Chatterbox (M07/M08). Any change to the audio contract itself (conform.py's resample/trim/normalize behavior is settled from M05).

### Acceptance criteria
- Resumability test passes: total engine calls across a crashed-then-restarted run == total chunk count, no duplicates.
- Deliberately truncated mock output is flagged `status="truncated"`.
- Deliberately silent (near-zero RMS) mock output is flagged `status="silent"`.
- A normal mock output stays `status="ok"`.
- `pytest -q` passes, including all prior milestone tests.

### Verification commands
```
. .venv/bin/activate
pytest -q
```

### On completion
Append the TASK_LOG entry with the exact `pytest -q` output, mark M06 `[x]` in IMPLEMENTATION_PLAN.md, then replace this file's active milestone with M07 — Kokoro and XTTS (copy its scope and acceptance criteria from IMPLEMENTATION_PLAN.md and expand into the same sections as above). Note before starting M07: XTTS is a GPU engine needing a fixed reference clip that ARCHITECTURE.md says all three cloning engines share — check whether I need to supply that clip (or approve a synthetic/public-domain stand-in) and whether GPU access is actually available in this environment before assuming the milestone can run unattended; if there's no GPU here, that's exactly the kind of thing to stop and ask about rather than skip or fake.
