# IMPLEMENTATION_PLAN.md — Narrate Bench

Milestones are executed strictly in order. Each is small enough to finish in one agent session and ends in a verifiable state. Work on exactly one milestone at a time; it is loaded into CURRENT_TASK.md. Do not start the next milestone until the current one's acceptance criteria pass and TASK_LOG.md is updated.

Status legend: `[ ]` not started · `[~]` in progress · `[x]` done · `[!]` blocked

## Track A — Foundation

### M01 — Project skeleton and config `[x]`
- Create package layout from ARCHITECTURE.md, `pyproject.toml`, `requirements.lock`, `Makefile`, `.gitignore` (data/, cache/, results/).
- `config.py`: pydantic model for `config.yaml` (books, engines with voice/params/max_chars/device/model_revision, whisper settings, sample plan).
- `cli.py`: typer app with all stage commands stubbed to print "not implemented" and exit 2; `nb status` prints config summary.
- Accept: `pip install -e .` succeeds; `nb --help` lists all commands; `pytest` runs (zero tests OK); config loads and validation errors are readable.

### M02 — Content cache `[x]`
- `cache.py` per interface. Key derivation exactly as specified. `write_atomic` writes to `{path}.tmp` then `os.replace`.
- Accept: tests prove (a) identical inputs → identical key, (b) any single input change → different key, (c) a producer that raises leaves no file behind, (d) `has()` false before and true after write.

### M03 — Text: fetch and normalize `[ ]`
- `gutenberg.py`: download by Gutenberg ID, strip header/footer markers, split chapters on configured heading regex.
- `normalize.py`: NFKC, straight quotes, dash unification, abbreviation expansion table, numeral spelling (rule: integers <1000 and years spelled per config), collapse whitespace. Export `NORMALIZER_VERSION`.
- Accept: 50 golden-case tests pass; running on one book produces `data/text/{book}.norm.txt` and a chapter index JSON; rerun is byte-identical.

### M04 — Text: chunker `[ ]`
- `chunk.py`: sentence split (pysbd or nltk punkt), bucket rotation, hard cap by min `max_chars`. Writes `chunks.parquet` with all engine-independent columns (human fields null).
- Accept: tests prove no chunk exceeds cap; bucket counts per position decile are within ±20% of uniform; `nb prepare` works end to end for one book and prints chunk stats.

## Track B — Synthesis (all engines local, open-source)

### M05 — Engine base + Piper + audio conform `[ ]`
- `engines/base.py`, `registry.py`, `piper.py`. `audio/conform.py` enforcing the audio contract with a `check()` that raises on violation.
- `nb synthesize --engine piper --book <id>` iterates chunks, skips cached, conforms output, writes cache + a synth manifest row (synth_path, wall_s, dur_s, status).
- Accept: synthesize one chapter; every output passes `conform.check()`; second run makes zero engine calls (assert via mock in test); `nb status` shows coverage.

### M06 — Resumability proof `[ ]`
- Test that starts synthesis with a mock engine, kills after N chunks (raise in worker), restarts, and asserts total engine calls == total chunks.
- Add `status=silent` detection (RMS below threshold) and `status=truncated` (audio_dur_s < 0.4 × expected from chars-per-second prior).
- Accept: test passes; deliberately truncated mock output is flagged.

### M07 — Kokoro and XTTS `[ ]`
- `kokoro.py` (CPU), `xtts.py` (GPU, fixed reference clip, speaker embedding cached once). Add a GPU model guard in the runner: acquire before load, release after unload.
- Accept: one chapter each; outputs pass conform; listening spot-check of 5 chunks per engine noted in TASK_LOG; `nvidia-smi` shows one TTS model resident at a time.

### M08 — F5-TTS and Chatterbox `[ ]`
- `f5tts.py`, `chatterbox.py` using the same reference clip as XTTS. Record `peak_vram_mb` per chunk via `torch.cuda.max_memory_allocated`. Pin exact model revisions in config and `requirements.lock`.
- Accept: one chapter each on the 3070 without OOM; outputs pass conform; `engine_error` recorded rather than raised on a deliberately malformed input; spot-check noted in TASK_LOG.

## Track C — Human baseline

### M09 — LibriVox ingest `[ ]`
- Download configured chapter MP3s, conform to contract, verify chapter count matches text chapter index (or apply configured merge/split map).
- Accept: `data/audio/human/{book}/{chapter}.wav` for one book; mismatch produces a clear error naming the chapters.

### M10 — Forced alignment and slicing `[ ]`
- `align.py` via WhisperX → word timestamps per chapter. `slice.py` cuts chunk audio using first/last word times ± pad; computes `align_conf` = fraction of chunk words aligned with score >0.5; sets `human_audio=null` if <0.8.
- Update `chunks.parquet` in place with `human_audio`, `align_conf`.
- Accept: one book sliced; exclusion rate reported; 30 slices spot-checked by ear and noted in TASK_LOG; pad/threshold tuned if needed.

## Track D — Scoring

### M11 — Whisper transcription `[ ]`
- `asr/whisper.py` with frozen settings, cached by key with `model_version`. `nb transcribe --source {engine|human|all}`.
- Accept: transcribes one book's human slices and Piper output; rerun makes zero model calls; hypothesis text stored.

### M12 — WER scoring and excess_wer `[ ]`
- `asr/score.py` with jiwer + Whisper EnglishTextNormalizer on both sides; sub/ins/del counts. `nb score` joins engine rows to human rows on chunk_id, computes `excess_wer`, writes `results.parquet` and `human_results.parquet`.
- Accept: test proves excess_wer == 0 when hyp == human hyp; human WER distribution for one book is reported and plausibly low (median <5%); flagged chunks excluded.

### M13 — Speaker embeddings and MOS `[ ]`
- `speaker/ecapa.py`, `speaker/mos.py`, cached. `nb embed` fills spk_embed, spk_sim_first, spk_sim_centroid (rolling 50), mos.
- Accept: runs on one book, human + Piper; human spk_sim_first median >0.7 (sanity: same narrator).

## Track E — Full run and analysis

### M14 — Full run orchestration `[ ]`
- `nb run --all` executes stages in order for all books and engines (sample plan defaults to `full` since there is no API spend); `nb status` shows per-stage/engine/book coverage matrix.
- Accept: full run completes (may take days); coverage matrix 100% or every gap has a `status` reason.

### M15 — Statistics `[ ]`
- `analysis/stats.py`: per-engine OLS with HC3, coefficient table with CIs; bootstrap ranking; text-difficulty bins by human_wer; exclusion rates.
- Accept: `nb analyze` writes `reports/coefficients.csv`, `reports/ranking.csv`, `reports/exclusions.csv`; tests on synthetic data recover a known position coefficient.

### M16 — Charts and README `[ ]`
- `analysis/plots.py`: (1) excess_wer by engine, (2) vs char_len, (3) vs position with fit, (4) spk_sim vs position with human reference, (5) real-time factor and peak VRAM table (replaces the cost table).
- README with headline table, chart 3 near the top, methodology summary, findings, limitations, `make reproduce`.
- Accept: `make reproduce` completes in <10 min on CPU for the smallest book with Piper; README renders; findings section states which engine won, by how much, and one surprise.

## Backlog (not scheduled)
- Optional hosted-engine track (OpenAI tts-1, Polly) behind a separate `engines/hosted/` package with spend caps, if a paid comparison is wanted later.
- Second Whisper model as a robustness check on excess_wer.
- Per-chapter human re-alignment with a different aligner to bound alignment error.
- Additional engines via registry.
