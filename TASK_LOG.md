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

## M03 — Text: fetch and normalize `2026-09-16`

`narrate_bench/text/gutenberg.py`: `fetch()` (stdlib `urllib.request`, no new dependency) downloads the plain-text edition from `gutenberg.org/cache/epub/{id}/pg{id}.txt`; `strip_boilerplate()` cuts everything outside the `*** START/END OF THE PROJECT GUTENBERG EBOOK ... ***` markers; `split_chapters(text, chapter_regex)` returns `[{heading, start_char, end_char}, ...]` spanning each heading match to the next (or EOF).

`narrate_bench/text/normalize.py`: `NORMALIZER_VERSION = "1"`, `normalize()` in fixed order NFKC -> straight quotes -> dash unification (em/en dash, `--` all -> ` - `) -> abbreviation expansion (small lookup table: Mr./Mrs./Dr./St./Mt./vs./etc./Jr./Sr.) -> numeral spelling (integers 0-999 via a hand-written cardinal-number converter; years 1000-2099 read the conventional way, e.g. 1984 -> "nineteen eighty-four", 1800 -> "eighteen hundred"; ordinals like "1st" are untouched since there's no `\b` between digit and following letter) -> whitespace collapse (single trailing newline, no double spaces/blank-line runs).

**Bug found and fixed during implementation:** normalizing the whole book before splitting into chapters strips leading indentation everywhere (whitespace-collapse step), which erased the one signal distinguishing an indented table-of-contents entry from a real chapter heading — on Sherlock Holmes this doubled the chapter count (24 instead of 12) by matching the ToC too. Fixed by splitting on the raw (pre-normalize) stripped text, where ToC entries are still indented and don't match the `^`-anchored chapter regex, then normalizing each chapter body independently and joining. Covered by `test_prepare_writes_norm_and_chapters_and_skips_toc`.

Also fixed while wiring `nb prepare` against the real config: `config.yaml`'s `chapter_regex` values from M01 were unverified placeholders and wrong for 4 of 5 books (checked against the actual Gutenberg text): Pride and Prejudice's default edition (id 1342) marks chapter breaks only through illustrations, not text — switched to the 3-volume plain-text edition (id 42671, `^CHAPTER [IVXLC]+\.?$`, 61 chapters). Treasure Island and the Franklin autobiography mark chapters with a bare roman numeral alone on its own line (`^[IVXLC]+$`, 34 and 19 chapters). Sherlock Holmes needed the ToC-excluding pattern above (`^[IVXLC]+\. .+$`, 12 chapters). Anne of Green Gables' original regex was already correct, widened only to capture the full heading line (`^CHAPTER [IVXLC]+\..*$`, 38 chapters).

`nb prepare` (wired into `cli.py`): for each configured book, fetches through `ContentCache` (keyed by `gutenberg_id`, stage `fetch_gutenberg`) so a rerun makes zero network calls, strips boilerplate, splits chapters on raw text, normalizes each chapter body, writes `data/text/{book_id}.norm.txt` and `data/text/{book_id}.chapters.json`.

`tests/test_normalize.py`: 60 table-driven golden cases across NFKC, quotes, dashes, abbreviations, numerals (ordinals excluded), whitespace. `tests/test_gutenberg.py`: boilerplate stripping and chapter splitting against a fixture (no network). `tests/test_prepare.py`: `_prepare_book` writes correct output and excludes indented ToC entries; second call with a mocked `gutenberg.fetch` makes zero fetch calls and produces a byte-identical `norm.txt`.

### Verification output

```
$ . .venv/bin/activate
$ rm -rf data cache && pip install -q -e .
$ pytest -q
........................................................................ [ 92%]
......                                                                   [100%]
78 passed in 1.14s

$ nb prepare
pride_and_prejudice: 61 chapters, 690500 chars
treasure_island: 34 chapters, 360675 chars
sherlock_holmes: 12 chapters, 563678 chars
franklin_autobiography: 19 chapters, 419715 chars
anne_of_green_gables: 38 chapters, 560297 chars

$ md5sum data/text/pride_and_prejudice.norm.txt
36ff7fa6ae5b6376d5028a0a27fd8f35  data/text/pride_and_prejudice.norm.txt

$ nb prepare   # second run
pride_and_prejudice: 61 chapters, 690500 chars
... (identical counts/sizes for all 5 books)

$ md5sum data/text/pride_and_prejudice.norm.txt
36ff7fa6ae5b6376d5028a0a27fd8f35  data/text/pride_and_prejudice.norm.txt   # unchanged
```

All acceptance criteria met, run against the real 5-book config (not just one book). `data/` and `cache/` are gitignored; not committed.
