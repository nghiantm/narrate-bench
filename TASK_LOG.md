# TASK_LOG.md — Narrate Bench

## M01 — Project skeleton and config `2026-09-16`

Created package layout per ARCHITECTURE.md (`narrate_bench/` with `text/`, `engines/`, `audio/`, `asr/`, `speaker/`, `analysis/` subpackages, all non-M01 modules stubbed with a one-line docstring), `pyproject.toml`, `requirements.lock`, `config.yaml` (5 books, 5 engines, unconfirmed model identifiers marked `# verify`), `Makefile`, `.gitignore`, and `tests/test_config.py`.

`config.py`: pydantic v2 models (`Book`, `EngineCfg`, `WhisperCfg`, `SamplePlan`, `Paths`, `Config`) with `extra="forbid"`, `load_config()` reading `config.yaml`. `cli.py`: typer app, `prepare/synthesize/align/transcribe/score/embed/analyze/run` each print `"<cmd>: not implemented"` and exit 2; `status` loads config and prints books/engines/whisper summary.

### Verification output

```
$ python3 -m venv .venv && . .venv/bin/activate
$ pip install -e . && pip install -r requirements.lock
INSTALL_OK

$ nb --help
Usage: nb [OPTIONS] COMMAND [ARGS]...

╭─ Options ────────────────────────────────────────────────────────────────────╮
│ --help          Show this message and exit.                                  │
╰──────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ───────────────────────────────────────────────────────────────────╮
│ prepare                                                                      │
│ synthesize                                                                   │
│ align                                                                        │
│ transcribe                                                                   │
│ score                                                                        │
│ embed                                                                        │
│ analyze                                                                      │
│ run                                                                          │
│ status                                                                       │
╰──────────────────────────────────────────────────────────────────────────────╯

$ nb status
books (5):
  pride_and_prejudice (gutenberg 1342)
  treasure_island (gutenberg 120)
  sherlock_holmes (gutenberg 1661)
  franklin_autobiography (gutenberg 20203)
  anne_of_green_gables (gutenberg 45)
engines (5):
  piper: voice=en_US-lessac-medium device=cpu revision=1.2.0
  kokoro: voice=af_heart device=cpu revision=v1.0
  xtts: voice=reference device=cuda revision=v2.0.3
  f5tts: voice=reference device=cuda revision=base
  chatterbox: voice=reference device=cuda revision=main
whisper:
  model=large-v3 backend=faster-whisper beam=5

$ nb prepare; echo "exit=$?"
prepare: not implemented
exit=2

$ pytest -q
..                                                                       [100%]
2 passed in 0.75s
```

All acceptance criteria met. Dependency versions pinned to current stable releases at time of writing (typer 0.27.2, pydantic 2.13.5, pandas 3.0.5, pyarrow 25.0.1, pyyaml 6.0.3, pytest 9.1.1) — `pyyaml` added beyond the four named packages since `config.yaml` parsing requires it and stdlib has no YAML support.

Book/engine identifiers in `config.yaml` marked `# verify` are placeholders from the original plan doc and ARCHITECTURE.md; not yet checked against current upstream releases (deferred to the milestones that actually use them, per ARCHITECTURE.md's own note to "verify exact identifiers... before pinning").

## M02 — Content cache `2026-09-16`

Implemented `ContentCache` in `narrate_bench/cache.py` per ARCHITECTURE.md: `key()` hashes `stage + engine_id + voice_id + sorted_json(params) + model_version + chunk_id` with sha256; `path()` returns `cache/{stage_root}/{key[:2]}/{key}` under the configured cache root; `has()` checks existence; `write_atomic()` has the producer write to `{path}.tmp`, then `os.replace`s into place, and removes the tmp file if the producer raises (so a failed write leaves nothing behind, including the case where the producer partially wrote to the tmp path before raising).

`tests/test_cache.py`: identical-inputs-same-key, params-key-order-independence, six parametrized single-field-change-different-key cases, raising-producer-leaves-no-file, and has() false-before/true-after.

### Verification output

```
$ . .venv/bin/activate
$ pytest -q
............                                                             [100%]
12 passed in 0.80s
```

All acceptance criteria met.
