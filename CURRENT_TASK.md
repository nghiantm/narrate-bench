# CURRENT_TASK.md — Narrate Bench

Read ARCHITECTURE.md first. Work only on the milestone below. When its acceptance criteria pass, append an entry to TASK_LOG.md, mark the milestone `[x]` in IMPLEMENTATION_PLAN.md, and stop. Do not begin the next milestone in the same session.

---

## Active milestone: M02 — Content cache

### Goal
Implement the single content-addressed cache every later stage writes through and reads from, exactly per the interface and key derivation in ARCHITECTURE.md, so no stage ever redoes work or leaves a corrupt partial file behind.

### Scope
1. `narrate_bench/cache.py`: implement `ContentCache` per the ARCHITECTURE.md interface:
   - `key(self, stage, engine_id, voice_id, params, model_version, chunk_id) -> str` — `sha256(stage + engine_id + voice_id + sorted_json(params) + model_version + chunk_id)`. `params` must be serialized with sorted keys so key order never affects the hash.
   - `has(self, key) -> bool`
   - `path(self, key) -> Path` — `cache/{stage}/{key[:2]}/{key}`
   - `write_atomic(self, key, producer: Callable[[Path], None]) -> Path` — producer writes to a `{path}.tmp` path (create parent dirs as needed), then `os.replace` into the final path. If `producer` raises, the `.tmp` file (and the final path) must not exist.
2. Cache root comes from `Config.paths.cache` (already in `config.py` from M01); `ContentCache.__init__` takes a root `Path`.
3. `tests/test_cache.py` covering the four proof points in the acceptance criteria below.

### Out of scope
Any real stage logic (text, synth, ASR, etc.), any engine or model code, wiring the cache into the CLI stage commands (they stay stubbed until the milestone that implements each stage).

### Acceptance criteria
- Test: identical inputs to `key()` → identical key, called twice.
- Test: changing any single input (`stage`, `engine_id`, `voice_id`, one entry in `params`, `model_version`, or `chunk_id`) → a different key than the baseline.
- Test: a `producer` callable that raises inside `write_atomic` leaves no file at the temp path or the final path.
- Test: `has(key)` is `False` before `write_atomic`, `True` after.
- `pytest -q` passes, including the existing M01 config tests.

### Verification commands
```
. .venv/bin/activate
pytest -q
```

### On completion
Append the TASK_LOG entry with the exact `pytest -q` output, mark M02 `[x]` in IMPLEMENTATION_PLAN.md, then replace this file's active milestone with M03 — Text: fetch and normalize (copy its scope and acceptance criteria from IMPLEMENTATION_PLAN.md and expand into the same sections as above).
