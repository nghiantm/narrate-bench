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

## M04 — Text: chunker `2026-09-16`

`narrate_bench/text/chunk.py`: sentence splitting via `pysbd` (rule-based, no model download needed, unlike NLTK punkt — keeps `nb prepare` fully offline after the first Gutenberg fetch). `build_chunks(book_id, norm_text, chapters, max_chars)` rotates XS(1)->S(3)->M(8)->L(20) sentences per group, restarting the rotation at each chapter boundary. A group that would exceed `max_chars` is shrunk sentence-by-sentence from the end (never mid-sentence); the loop advances by however many sentences were actually kept, so a shrunk group's leftover sentences start the next chunk rather than being silently dropped — every sentence in a chapter ends up in exactly one chunk, none are lost to capping. `chunk_id = sha256(book_id + text)[:16]` per ARCHITECTURE.md.

Wired into `nb prepare`: after writing each book's `norm.txt`/`chapters.json`, chunks it with `max_chars = min(engine.max_chars for engine in config)` (400, from the three cloning engines), collects rows from all 5 books, and writes one `data/chunks.parquet` (pyarrow via pandas) with the exact ARCHITECTURE.md schema (`human_audio`/`align_conf` null — those are M09/M10).

`tests/test_chunk.py`: sentence segmentation sanity; no chunk exceeds `max_chars` except the unavoidable single-oversized-sentence case; a generous cap never overflows; every original sentence is recovered exactly once by concatenating chunk texts (proves no silent drops); bucket rotation restarts at each chapter; `position_index` is global and sequential; bucket counts per position decile stay within ±20% of uniform on a 2000-sentence synthetic chapter.

### Verification output

```
$ . .venv/bin/activate
$ pytest -q
........................................................................ [ 84%]
.............                                                            [100%]
85 passed in 7.44s

$ rm -rf data cache && nb prepare
pride_and_prejudice: 61 chapters, 690500 chars
  3124 chunks, buckets={'XS': 793, 'S': 792, 'M': 780, 'L': 759}
treasure_island: 34 chapters, 360675 chars
  1637 chunks, buckets={'XS': 416, 'S': 416, 'M': 408, 'L': 397}
sherlock_holmes: 12 chapters, 563678 chars
  2619 chunks, buckets={'XS': 656, 'S': 656, 'M': 656, 'L': 651}
franklin_autobiography: 19 chapters, 419715 chars
  1830 chunks, buckets={'XS': 461, 'S': 461, 'M': 458, 'L': 450}
anne_of_green_gables: 38 chapters, 560297 chars
  2657 chunks, buckets={'XS': 673, 'S': 672, 'M': 664, 'L': 648}

$ python3 -c "import pandas as pd; df = pd.read_parquet('data/chunks.parquet'); print(df.shape); print('max char_len:', df['char_len'].max()); print('rows over cap:', (df['char_len'] > 400).sum())"
(11867, 10)
max char_len: 400
rows over cap: 0
```

All acceptance criteria met: no chunk exceeds the configured cap (400, from the cloning engines), bucket distribution is near-uniform per decile (verified via test and visually balanced in the real per-book bucket counts above), `nb prepare` runs end to end for the real 5-book config and writes `data/chunks.parquet`.

Observation carried forward, not a defect: each chapter's own heading line (e.g. "CHAPTER I.") becomes its own tiny leading chunk, since it's included in the chapter body per M03's design and pysbd treats it as a one-line "sentence". Harmless for chunking correctness; worth reconsidering if it turns out to be an odd thing for a TTS engine to read aloud, no later than M05 when engines actually synthesize these chunks.

## M05 — Engine base + Piper + audio conform `2026-09-16`

`narrate_bench/engines/base.py`: `TTSEngine` Protocol and `SynthResult` dataclass exactly per ARCHITECTURE.md. `narrate_bench/engines/registry.py`: `get(name, cfg)` builds a configured engine from `config.yaml`, raising on an unconfigured or unimplemented name. `narrate_bench/engines/piper.py`: `PiperEngine` wraps `piper-tts` (pip-only install, no system packages — checked before committing to this design); `ensure_voice_files()` downloads the ONNX model + config JSON from the `rhasspy/piper-voices` HuggingFace repo into `data/models/piper/` on first use (freely licensed, no login/click-through) and reuses them after.

`narrate_bench/audio/conform.py`: `conform()` enforces the fixed contract — mono, resampled to 16 kHz via `scipy.signal.resample_poly`, silence-trimmed at −40 dBFS with a 100 ms pad, peak-normalized to −1 dBFS, written as PCM16 WAV (`soundfile` + `numpy`, no heavier audio framework needed). `check()` raises `AssertionError` naming which part of the contract was violated.

`nb synthesize --engine <name> --book <id> [--chapter <n>]`: reads `chunks.parquet`, skips chunks already in `ContentCache` (stage `synthesize`, keyed by engine/voice/params/model_revision/chunk_id — reusing M02's cache exactly as designed), synthesizes+conforms the rest, and records a manifest row (`chunk_id, engine_id, synth_path, wall_s, audio_dur_s, status`) in `data/synth_manifest.parquet`. Per-chunk engine failures are caught and recorded as `status="engine_error: ..."` rather than aborting the run (ARCHITECTURE non-negotiable 6). `nb status` gained a synthesis coverage section (chunks done per engine vs. total).

**Two bugs found and fixed while running this against real Piper output, not just mocks:**
1. `soundfile.write()` on the cache's extension-less content-hash paths failed with `LibsndfileError: No format specified` — every single chunk in the first real run came back `engine_error`. `sf.read`/`sf.info` autodetect the format from file content fine without an extension; only `write()` needs it. Fixed by passing `format="WAV"` explicitly in `conform()`.
2. One chunk's recorded `wall_s` came back negative (−0.98s) from a run of 51 real chunks — `time.time()` is wall-clock and not protected against a system clock adjustment mid-call (observed under WSL2). Switched `piper.py`'s timing to `time.monotonic()`, which is immune to clock adjustments; reran and confirmed non-negative timings across all chunks.

`tests/test_synthesize.py`: a `CountingEngine` test double (writes a real conforming tone, counts calls) proves a second `synthesize()` call makes zero engine calls once every chunk is cached, and that manifest rows point at audio passing `conform.check()`.

### Verification output

```
$ . .venv/bin/activate && pip install -q -e . && pytest -q
........................................................................ [ 82%]
...............                                                          [100%]
87 passed in 11.39s

$ rm -rf data cache && nb prepare > /dev/null
$ nb status
...
synthesis coverage (11867 chunks total):
  piper: 0/11867
  kokoro: 0/11867
  xtts: 0/11867
  f5tts: 0/11867
  chatterbox: 0/11867

$ time nb synthesize --engine piper --book treasure_island --chapter 0
treasure_island: 51 synthesized, 0 already cached, 51 total chunks
real	0m29.097s

$ nb status   # after synth
synthesis coverage (11867 chunks total):
  piper: 51/11867
  ...

$ time nb synthesize --engine piper --book treasure_island --chapter 0   # second run
treasure_island: 0 synthesized, 51 already cached, 51 total chunks
real	0m8.124s   # model load only, zero engine.synthesize() calls
```

Spot-checked with a Python one-liner: all 51 manifest rows `status == "ok"`, all pass `conform.check()` (16 kHz mono PCM16, peak within contract), `wall_s` non-negative for all chunks after the monotonic-clock fix. Real per-chunk synth time ranged ~0.07-0.95s on CPU for chunks up to 400 chars.

All acceptance criteria met. `data/models/piper/*.onnx` (~63 MB) is gitignored (under `data/`), downloaded fresh on first `nb synthesize` run in any environment.

## M06 — Resumability proof `2026-09-16`

Resumability was already mostly correct by construction from M02/M05 (cache is the single source of truth for "was this chunk actually synthesized"; the manifest is derived bookkeeping that gets backfilled from cache state on every run), so this milestone is primarily the proof plus the two status detections.

`tests/test_resumability.py`: `CrashAfterNEngine` completes `crash_after` chunks normally, then raises `KeyboardInterrupt` on the next call — deliberately a `BaseException`, not `Exception`, so it is NOT swallowed by `_synthesize_chunk`'s per-chunk `except Exception` (that layer exists to keep a normal engine failure from aborting the run; a real process kill is a different thing and should propagate). The crashing chunk gets no cache entry (per M02's write_atomic guarantee). "Restarting" with a fresh engine instance against the same cache dir picks up exactly the un-synthesized remainder — `engine1.calls + engine2.calls == n_chunks`, no chunk synthesized twice, and `synth_manifest.parquet` ends up with exactly `n_chunks` unique rows even though the crash happened before that run's in-memory manifest rows were ever flushed to disk (proving the cache-hit backfill path in `synthesize()` correctly reclassifies and re-adds rows for chunks that exist in the cache but are missing from the manifest).

`status=silent`: `audio.conform.is_silent()` computes RMS over the whole conformed clip and flags it below the same -40 dBFS floor `conform()` already uses to define "not speech" when trimming — reusing an existing, already-justified constant rather than inventing a new one. `status=truncated`: `CHARS_PER_SECOND = 15.0` (~150 words/min, typical audiobook narration pace) gives an expected duration from chunk text length; `audio_dur_s < 0.4 * expected` is flagged truncated. Both checks are in a shared `_classify()` used by both the real-synthesis path (`_synthesize_chunk`) and the cache-hit manifest-backfill path in `synthesize()` — the backfill branch previously hardcoded `status="ok"` unconditionally, which would have silently missed silent/truncated chunks reclassified on a manifest-less rerun; fixed as part of this milestone since both paths write the same manifest schema and must apply the same classification.

### Verification output

```
$ . .venv/bin/activate && pip install -q -e . && pytest -q
........................................................................ [ 79%]
...................                                                      [100%]
91 passed in 11.50s
```

Also reran the real Piper output from M05 (51 chunks, `treasure_island` chapter 0) through the new classifier by deleting `synth_manifest.parquet` and rerunning `nb synthesize` (pure cache-hit backfill path, real audio, not mocks): all 51 came back `status="ok"`, none false-flagged silent or truncated.

All acceptance criteria met.

## M07 — Kokoro and XTTS `2026-09-16`

**Reference clip** (user chose: pull from an existing LibriVox recording rather than supply a file): `narrate_bench/audio/reference_clip.py`, `ensure_reference_clip()` downloads Frank Woodworth Pine's "Autobiography of Benjamin Franklin," solo-narrated by Gary Gilberd (LibriVox id 1143 -- single narrator, matches ARCHITECTURE's requirement, and is the same book already in `config.yaml`), chapter 1, extracts a fixed 71.0s-81.0s window (verified beforehand: 64% of samples above -40 dBFS, peak 0.78, no clipping). Written once to `data/reference_clip.wav` at native sample rate, not run through the 16 kHz ASR contract since it feeds TTS reference encoders, not Whisper/SpeechBrain.

**Kokoro** (`narrate_bench/engines/kokoro.py`): wraps the `kokoro` pip package (`KPipeline`, CPU), concatenating all yielded segments (kokoro can split internally on some inputs) into one array before writing. `lang_code` derived from the voice_id's first character (`af_heart` -> `'a'`, kokoro's own American/British English convention) rather than hardcoded, so a future voice change in config doesn't silently mismatch.

**XTTS** (`narrate_bench/engines/xtts.py`): wraps `coqui-tts` (the maintained fork -- the original `TTS` PyPI package is gone). Computes GPT conditioning latents + speaker embedding from the shared reference clip **once** at construction (`model.get_conditioning_latents`), then calls the low-level `model.inference(text, language, gpt_cond_latent, speaker_embedding)` per chunk instead of the high-level `tts_to_file(..., speaker_wav=...)`, which was measured recomputing the reference-clip latents on every single call (9.2s vs 1.9s per short sentence with latents cached -- a ~5x per-chunk cost that would have compounded across thousands of chunks in later milestones).

**GPU guard** (`narrate_bench/engines/gpu_guard.py`): minimal `acquire(engine_id)`/`release(engine_id)` around a single lock, enforcing one GPU-resident model at a time. `XTTSEngine.__init__` acquires before loading; `XTTSEngine.unload()` (not yet called by anything -- `nb synthesize` only ever builds one engine per process today) releases and frees CUDA memory. Real teeth arrive with M14's orchestrator, which will call `unload()` before switching GPU engines within one process; the guard is implemented and tested now rather than invented later. `tests/test_gpu_guard.py` proves the mutual exclusion directly (second acquire before release raises; release by a non-holder raises; acquire after release succeeds).

**Dependency chain, resolved in order:**
- `kokoro==0.9.4` pulled in `torch==2.14.0+cu130` as a transitive dependency (CUDA build auto-selected, no special index URL needed) -- confirmed `torch.cuda.is_available()` on the RTX 3070.
- `coqui-tts==0.27.5` needed `torchaudio` (missing), then `transformers>=4.57` (installed was 5.17.0, which had removed a symbol `coqui-tts`'s XTTS code imports -- pinned `transformers==4.57.6`, the newest 4.x release, since coqui-tts's own lower bound is `>=4.57` and 5.x broke it), then `coqui-tts[codec]` for `torchcodec` (torch>=2.9 made it the mandatory audio I/O backend), then **system FFmpeg** (`torchcodec` dlopens `libavutil.so.*` directly; no pip-only path around it once torch/torchaudio are this new). No passwordless sudo in this environment -- user ran `sudo apt-get install -y ffmpeg` themselves in a real terminal (a `!`-prefixed command in this session has no TTY for the password prompt either). Confirmed via `ldconfig -p | grep libavutil` (`libavutil.so.58`) and a successful XTTS synthesis afterward.
- XTTS v2 license (Coqui Public Model License 1.0, non-commercial) checked and confirmed with the user before downloading the ~1.87 GB checkpoint. Model registry confirms "XTTS-v2.0.3" exactly, matching ARCHITECTURE.md's pin -- `config.yaml`'s `# verify` note on `model_revision` removed. Also confirmed Kokoro's `af_heart`/`v1.0` pins while in there.

**Real bug found via real synthesis, not caught by tests:** XTTS logged "text length exceeds the character limit of 250 for language 'en'" on 18 of the first 51 chunks synthesized -- `config.yaml`'s `xtts.max_chars: 400` (an unverified M01 placeholder) exceeds XTTS's actual hard limit. Since the chunker's cap is `min(engine.max_chars)` across *all* configured engines (M04), this wrong value had been silently capping every book's chunks at 400 chars instead of the correct 250 since M04 -- meaning the `chunks.parquet` already committed to via `data/` (gitignored, not committed to git, but already generated in this environment) contained chunks that would truncate on XTTS. Fixed `max_chars: 250` for xtts (confirmed directly against the library's own limit); left `f5tts`/`chatterbox` at 400 with a note that the *effective* shared cap is 250 regardless until M08 verifies their own real limits. Regenerated `data/chunks.parquet` from scratch (`rm -rf data cache && nb prepare`) and re-synthesized `treasure_island` chapter 0 with all three engines (Piper, Kokoro, XTTS) against the corrected chunk boundaries -- no data was lost since `data/`/`cache/` are gitignored and fully regenerable.

### Verification output

```
$ . .venv/bin/activate && pytest -q
........................................................................ [ 76%]
......................                                                   [100%]
94 passed in 13.44s

$ rm -rf data cache && nb prepare   # after fixing max_chars: 250 for xtts
treasure_island: 34 chapters, 360675 chars
  2303 chunks, buckets={'XS': 585, 'S': 584, 'M': 574, 'L': 560}
... (all 5 books; max char_len across all chunks: 250, 0 rows over cap)

$ nb synthesize --engine piper --book treasure_island --chapter 0
treasure_island: 72 synthesized, 0 already cached, 72 total chunks   # real 0m31s

$ nb synthesize --engine kokoro --book treasure_island --chapter 0
treasure_island: 72 synthesized, 0 already cached, 72 total chunks   # real 3m55s

$ nb synthesize --engine xtts --book treasure_island --chapter 0
treasure_island: 72 synthesized, 0 already cached, 72 total chunks   # real 6m55s, no character-limit warnings this time
```

All three engines: 72/72 manifest rows `status="ok"`, all pass `conform.check()`. Piper wall_s 0.06-1.56s/chunk, Kokoro 0.46-4.77s/chunk, XTTS 0.70-8.94s/chunk (audio_dur_s 0.4-27s depending on bucket).

**5-chunk spot-check per engine** (Kokoro and XTTS -- Piper's was already done in M05), using waveform sanity stats as the closest verifiable proxy for a manual listen: peak exactly 0.891 (== -1 dBFS) on every sample, confirming `conform()`'s normalization; active-sample fraction (above -40 dBFS) 0.46-0.66, consistent with natural speech pauses rather than silence or a stuck tone; duration at or above the chars-per-second expectation for every chunk except the single-character "CHAPTER" heading chunks (already a known artifact from M04, not new here -- a lone letter spoken aloud is slower than 15 chars/s predicts, unsurprising).

**GPU residency check:** WSL2's `nvidia-smi` does not reliably report per-process VRAM for guest CUDA contexts (a known WSL2 limitation -- `--query-compute-apps` returned nothing during the live XTTS run despite GPU utilization visibly climbing from 18% to 25%+). Used `utilization.gpu` as corroborating evidence of real GPU compute activity instead, backed by `gpu_guard`'s unit-tested mutual exclusion as the actual correctness guarantee (only one GPU engine is ever constructed per `nb synthesize` process anyway, since the CLI takes a single `--engine` flag).

All acceptance criteria met.

## Proposed architecture changes

**Two venvs, not one** (approved by user mid-M08; folded into ARCHITECTURE.md's Environment and Concurrency sections rather than left as a pending proposal, since the user signed off in-session before implementation). `chatterbox-tts==0.1.7` hard-pins `transformers==5.2.0` exactly and `numpy<2.0` for Python<3.13. XTTS needs `transformers<5` (5.x removed `isin_mps_friendly`, which coqui-tts 0.27.5's tortoise layer imports and which has no drop-in replacement at that import site). The rest of the project needs `numpy>=2` (pandas 3.x, pyarrow 25.x, scipy). These three constraints cannot be satisfied by one interpreter's site-packages simultaneously -- confirmed by directly installing all three and hitting `ModuleNotFoundError`/`AttributeError` cascades, not inferred from version numbers alone.

Considered and rejected: (a) a monkeypatch shim for the missing transformers symbol, to keep one venv -- rejected by the user as more fragile than isolation, and it would not have addressed the numpy conflict anyway; (b) dropping Chatterbox from the benchmark -- rejected, since isolation is a known-working, if inelegant, fix and the benchmark's value depends on covering the engines ARCHITECTURE.md commits to.

Chosen: `.venv-chatterbox/` (from `requirements-chatterbox.lock`, `make install-chatterbox`), isolated from the main `.venv/`. `narrate_bench/engines/chatterbox.py` runs `narrate_bench/engines/chatterbox_worker.py` as a persistent subprocess under that interpreter, talking over a one-JSON-object-per-line stdin/stdout protocol (request: `{text, out_path}`; response: `{wall_s, peak_vram_mb, raw_sample_rate, error}`). The worker has no dependency on the `narrate_bench` package itself (not installed in that venv) -- it is a fully standalone script. `ChatterboxEngine` satisfies the exact same `TTSEngine` protocol as every in-process engine, so `registry.py`, `cli.py`, and `gpu_guard.py` need no special-casing; the isolation is invisible above the engine layer.

Two bugs specific to this design, found and fixed:
1. `chatterbox_worker.py` lives in the same directory as `narrate_bench/engines/chatterbox.py` (our own client wrapper). Running the worker as a script puts that directory first on `sys.path`, so `from chatterbox.tts import ...` resolved to our own file instead of the pip-installed `chatterbox` package. Fixed by stripping the script's own directory from `sys.path` before importing anything from the real package.
2. chatterbox-tts's `perth` dependency prints plain status lines (`"loaded PerthNet (Implicit) at step 250,000"`) directly to stdout during model load -- which corrupted the JSON protocol channel, since the client's `readline()` picked up that line instead of the `{"ready": ...}` response. Fixed by duplicating the process's real stdout file descriptor into a private handle used only for protocol messages, then redirecting the process's actual stdout (fd 1) to stderr, so any other library noise on stdout is harmless.

## M08 — F5-TTS and Chatterbox `2026-09-16`

Both engines needed their real capabilities checked against the library, not assumed from `config.yaml`'s M01 placeholders -- same lesson as M07's XTTS 250-char discovery.

**F5-TTS** (`narrate_bench/engines/f5tts.py`, package `f5-tts`, model `F5TTS_v1_Base`, license CC-BY-NC-4.0 -- confirmed with the user before downloading): unlike XTTS, F5-TTS's clone API needs the reference clip's *transcript* (`ref_text`), not just the audio -- passing `ref_text=""` triggers a one-time built-in ASR transcription (cached internally by audio-file hash), which correctly transcribed the shared reference clip as "Dear son, I have ever had pleasure in obtaining any little anecdotes of my ancestors..." (matches the real Franklin autobiography text the clip was cut from). `F5TTSEngine.__init__` calls `preprocess_ref_audio_text()` once and stores the resolved `(ref_file, ref_text)`, so per-chunk `infer()` calls skip re-transcription. No hard per-call text-length limit found in the library (unlike XTTS's explicit 250-char check); tested clean at 250-char chunks (the shared cap set in M07).

**Chatterbox** (`narrate_bench/engines/chatterbox.py` + `chatterbox_worker.py`, package `chatterbox-tts`, license MIT -- no confirmation needed): see "Proposed architecture changes" above for why and how this one runs out-of-process. `model.prepare_conditionals(reference_clip)` is called once in the worker at startup; `model.generate(text)` (no `audio_prompt_path`) reuses it per chunk. No hard text-length limit found either (tolerated even an empty-string input without raising).

**`peak_vram_mb`** now flows end-to-end: `gpu_guard.reset_peak_vram()`/`peak_vram_mb()` wrap each GPU engine's own inference call (XTTS and F5-TTS in-process; Chatterbox inside the worker subprocess, using its own torch/CUDA context identically), populate `SynthResult.peak_vram_mb`, and `cli.py`'s `_synthesize_chunk` threads it into the manifest row next to `wall_s`. CPU engines (Piper, Kokoro) report `None`, correctly.

Also fixed while getting a clean, fully-reproducible venv after the chatterbox-tts detour polluted the main one: `torch` had drifted to an inconsistent `2.6.0` (from an earlier `pip install transformers==... numpy==...` command that silently resolved a different torch version as a side effect) while `torchcodec` stayed pinned to a build expecting `torch==2.14.0`, breaking XTTS's audio loading with `OSError: libnvrtc.so.13: cannot open shared object file`. Fixed by rebuilding `.venv/` from scratch and installing `torch==2.14.0`, `torchaudio==2.11.0`, `torchcodec==0.16.0` together as a pinned trio *before* anything else, then `f5-tts` (which separately needed `datasets>=5.0.1` -- the version already present, `2.14.4`, used a pyarrow API removed in our pinned `pyarrow==25.0.1`).

### Verification output

```
$ . .venv/bin/activate && pytest -q
........................................................................ [ 76%]
......................                                                   [100%]
94 passed in 30.25s

$ rm -rf cache data/synth_manifest.parquet data/models && nb prepare > /dev/null
$ nb synthesize --engine piper --book treasure_island --chapter 0      # 72 synthesized, real 0m30s
$ nb synthesize --engine kokoro --book treasure_island --chapter 0     # 72 synthesized, real 4m01s
$ nb synthesize --engine xtts --book treasure_island --chapter 0       # 72 synthesized, real 6m56s
$ nb synthesize --engine f5tts --book treasure_island --chapter 0      # 72 synthesized, real 8m30s
$ nb synthesize --engine chatterbox --book treasure_island --chapter 0 # 72 synthesized, real 8m44s (includes ~2min worker/model startup)
```

All five engines, one Python one-liner over the full manifest: 72/72 `status="ok"` each (360 rows total), zero `conform.check()` failures. `peak_vram_mb`: XTTS 1857-2325 MB, F5-TTS 2307-2432 MB, Chatterbox 3457-3756 MB, all comfortably under the RTX 3070's 8192 MB. 5-chunk spot-check per engine (F5-TTS, Chatterbox) via the same waveform-sanity-proxy approach as M07: peak exactly 0.891 (-1 dBFS) on every sample; duration at or above the chars-per-second expectation for every chunk except the known single-character heading-chunk artifact; active-sample fraction 0.57-0.91, consistent with real speech.

`engine_error` handling: not re-triggered by a real malformed input this session (Chatterbox tolerated an empty string without error; F5-TTS and XTTS were not separately fuzzed) -- relying instead on the generic mechanism already proven in M05/M06 with mock engines (`_synthesize_chunk`'s `except Exception` around `cache.write_atomic`, structurally engine-agnostic) plus the fact that every GPU engine's own `synthesize()` also catches broadly and returns `SynthResult(error=...)`. Both layers exist independent of which specific engine is involved.

All acceptance criteria met.

### Post-M08 checkpoint: full-book synthesis (user-directed, not a milestone)

Before starting Track C, the user asked for a full-book synthesis run across all 5 engines against `treasure_island` (2303 chunks, the smallest book) as an extra checkpoint. Per-chunk rates measured in M07/M08 put only Piper safely under an hour for a full book (~10 min); Kokoro (~87 min), XTTS (~2.5 hr), F5-TTS (~4 hr), and Chatterbox (~3.4 hr) each exceed it, so these were launched as backgroundable jobs rather than run synchronously. Piper's full run completed in-session: **2299/2300 rows `status="ok"`, one real `engine_error`** (chunk `b1a1a0e18e77d57f`, text `"` -- a bare quote-mark-only chunk, a pysbd segmentation artifact around dialogue -- failed with `# channels not specified`, correctly caught and recorded rather than aborting the run; concrete real-world confirmation of the per-chunk failure handling ARCHITECTURE.md's non-negotiable 6 requires). Zero `conform.check()` failures on the rest. Total audio: 328 minutes.

Kokoro (CPU) and XTTS (GPU) were launched to run concurrently -- CPU and GPU don't contend. F5-TTS and Chatterbox were deliberately *not* launched alongside XTTS: all three are GPU engines sharing the RTX 3070's 8 GB, and ARCHITECTURE.md's concurrency section requires one GPU model resident at a time; running them concurrently as separate processes risks VRAM contention or OOM, since `gpu_guard`'s in-process lock has no reach across separate `nb synthesize` invocations (a known, documented gap -- see M07's TASK_LOG entry -- not fully closed until M14's orchestrator). Per explicit user direction mid-checkpoint, only one GPU engine (XTTS) runs at a time for this checkpoint; F5-TTS and Chatterbox were not queued to run after it.

Also discovered during this checkpoint, relevant to M09: `chunk_id = sha256(book_id + text)[:16]` (ARCHITECTURE.md's own schema) means chunks with identical text collapse to the same `chunk_id` regardless of position -- e.g. three separate isolated `"` chunks at different points in the book all hash to the same id and share one cache entry/synthesis. This is the specified design working as intended (content-addressed caching, no wasted resynthesis of identical text), not a bug; it just means a book's total *chunk rows* can slightly exceed its total *unique synthesized outputs*.

## M09 — LibriVox ingest `2026-09-16`

**`config.yaml` had more wrong placeholders**, found the same way M03 found wrong `gutenberg_id`/`chapter_regex` values -- checked against the real LibriVox API rather than trusted: `treasure_island`'s URL referenced a "version-4" recording that doesn't exist; `sherlock_holmes`'s URL had an incorrect "-by-arthur-conan-doyle" suffix; `franklin_autobiography`'s URL had a typo ("autobiography" vs the real "autobigraphy", LibriVox's own typo carried into their slug). Added a `librivox_id: int` field to `Book` (`config.py`) since the ingest code needs the numeric LibriVox book id to query the API directly -- `librivox_url` is now purely a human-readable citation link, not used programmatically.

**Narrator-count finding:** checked all 5 books' actual reader counts via the LibriVox API (not assumed). Only `franklin_autobiography` (id 1143, already used for the M07 reference clip) has a true single-narrator recording. The other 4 only have multi-reader recordings (11-13 different readers each) -- an apparent "solo" alternative existed for Pride and Prejudice (id 22765) and Sherlock Holmes (id 22681) but both are empty catalog stubs (`totaltimesecs: 0`, no `listen_url` on any section) with no real audio. Concluded this doesn't block anything: each LibriVox *section* is read by one consistent narrator throughout (readers are assigned per-section, not mixed mid-chapter), which is all the WER-floor scoring in Track D actually needs. The one place whole-book narrator consistency matters is M13's planned "human spk_sim_first median >0.7 (sanity: same narrator)" check -- noted for M13 to scope that check to within-section (or to `franklin_autobiography` specifically as the canary) rather than assume it holds book-wide for the other 4. No book substitutions made.

`narrate_bench/audio/librivox.py`: `fetch_sections(librivox_id)` hits the LibriVox API and returns the section list (number, title, `listen_url`, readers), sorted by section number.

`nb ingest --book <id>` (new CLI command, `cli.py`): fetches the section list, compares section count to the book's `chapters.json` chapter count. If they match and no `chapter_map` is configured, sections map 1:1 (`chapter_idx = section_number - 1`). If they don't match and no `chapter_map` is configured, exits with a clear error naming the exact section numbers and chapter count, and telling the user which config key to add -- never a silent partial result. If a `chapter_map` *is* configured (`Book.chapter_map`, already in the schema from M01), it's used directly; sections absent from the map (e.g. a LibriVox "Introduction" or "Appendix" with no text-chapter counterpart) are skipped. Each mapped section is downloaded once (cached via `ContentCache`, same fetch-once pattern as `nb prepare`'s Gutenberg download) and conformed to the audio contract via the existing `audio.conform()` from M05 -- no new conform logic needed. Output: `data/audio/human/{book_id}/{chapter_idx}.wav`.

`franklin_autobiography` is the clean 1:1 case after skipping its "Introduction" (section 0) and "Appendix" (section 20): sections 1-19 map directly to chapters 0-18, encoded as an explicit `chapter_map` in `config.yaml` (19 entries -- simple enough to hand-write once real API data was in hand, so no new config schema shape needed beyond what M01 already had). `treasure_island` (26 sections, 34 text chapters -- LibriVox groups multiple chapters per section, e.g. "Chapters 1-2" in one file) demonstrates the mismatch-error path, deliberately left unconfigured since only one book needs to fully succeed per this milestone's acceptance criteria; building out `chapter_map`s for the other 4 books is deferred to whenever their human baselines are actually needed.

`tests/test_ingest.py`: mocked `librivox.fetch_sections` and `audio_conform.conform` (no real network calls) prove the chapter_map path writes correctly-named per-chapter files, and that a section/chapter-count mismatch without a configured map raises `typer.Exit` rather than silently proceeding.

### Verification output

```
$ . .venv/bin/activate && pytest -q
........................................................................ [ 75%]
........................                                                 [100%]
96 passed in 49.68s

$ nb ingest --book franklin_autobiography
franklin_autobiography: 19 sections ingested to data/audio/human/franklin_autobiography

$ python3 -c "... conform.check() over all 19 files ..."
19 files
conform.check() failures: 0
total duration (min): 413.51  # ~6.9 hours

$ nb ingest --book treasure_island   # deliberate mismatch, no chapter_map configured
treasure_island: 26 LibriVox sections ['1', '2', ..., '26'] != 34 text chapters, and no chapter_map is
configured for this book. Add books.treasure_island.chapter_map to config.yaml mapping section_number -> chapter_idx.
exit=1
```

All acceptance criteria met: `data/audio/human/franklin_autobiography/{0..18}.wav` exist, all pass `conform.check()`; the mismatch case produces a clear, actionable error naming the exact counts and involved section numbers rather than a silent partial result.
