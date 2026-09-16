# ARCHITECTURE.md — Narrate Bench

This file is the stable technical reference. Read it at the start of every session. Do not change it to make a task easier; if the design is wrong, propose a change in TASK_LOG.md and stop.

## Purpose

Benchmark five TTS engines on five full-length public-domain books. Score intelligibility with Whisper WER against source text, subtracting the WER Whisper gets on the human LibriVox narration of the same text chunk (`excess_wer`). Test whether error depends on chunk length rather than position in the book. Measure speaker drift with SpeechBrain ECAPA embeddings.

## Non-negotiables

1. **One normalized text per book.** `data/text/{book_id}.norm.txt` is produced once by `nb prepare` and is the only text any later stage reads. TTS input and scoring reference must be byte-identical.
2. **Content-hash cache, no progress files.** Every artifact lives at `cache/{stage}/{key[:2]}/{key}` where `key = sha256(stage + engine_id + voice_id + sorted_json(params) + model_version + chunk_id)`. A stage does work only if `cache.has(key)` is false. Writes go to a temp path then `os.replace`.
3. **Engines are pure.** `synthesize(text)` depends only on `(text, voice_id, params)`. No state across calls.
4. **Fixed audio contract.** Anything entering ASR or SpeechBrain is WAV PCM16, 16 kHz, mono, peak −1 dBFS, silence trimmed at −40 dBFS with 100 ms pad. Enforced by `audio.conform()`; downstream code may assume it.
5. **Whisper settings are frozen.** `large-v3`, faster-whisper, float16, beam 5, temperature 0, `condition_on_previous_text=False`, `vad_filter=True`, language `en`. Same for human and synthetic audio.
6. **Per-chunk failures never abort a run.** Record `status` and continue unless `--strict`.
7. **All engines are local and pinned.** No hosted APIs, no keys, no network calls during synthesis. Every engine is a specific open-source release recorded in `model_versions`, so the benchmark can be rerun identically later.

## Repository layout

```
narrate_bench/
  cli.py            typer app; one command per stage + `status`
  config.py         pydantic model for config.yaml
  cache.py          ContentCache: key(), has(), path(), write_atomic()
  text/
    gutenberg.py    fetch + boilerplate strip
    normalize.py    project normalizer (versioned: NORMALIZER_VERSION)
    chunk.py        sentence split + bucket rotation
  engines/
    base.py         TTSEngine Protocol, SynthResult
    piper.py kokoro.py xtts.py f5tts.py chatterbox.py
    registry.py     name -> engine factory
  audio/
    conform.py      resample/trim/normalize to contract
    slice.py        cut human chapter audio at chunk boundaries
    align.py        WhisperX forced alignment -> word timestamps
  asr/
    whisper.py      transcribe(path) -> hypothesis str
    score.py        jiwer WER/CER/sub/ins/del with EnglishTextNormalizer
  speaker/
    ecapa.py        embed(path) -> np.ndarray[192]
    mos.py          utmos(path) -> float
  analysis/
    stats.py        regressions, bootstrap
    plots.py        chart set
data/                gitignored: books, librivox mp3, norm text, chunks.parquet
cache/               gitignored
results/             results.parquet, human_results.parquet, reports/
tests/
config.yaml
Makefile             `make reproduce` = one short book, Piper only, CPU
```

## Data schemas

**chunks.parquet** (engine-independent)

| column | type | notes |
|---|---|---|
| chunk_id | str | sha256(book_id + text)[:16] |
| book_id | str | |
| chapter_idx | int | |
| position_index | int | global order in book, 0-based |
| bucket | str | XS/S/M/L |
| char_len, word_count | int | |
| text | str | normalized |
| human_audio | str? | null if alignment excluded |
| align_conf | float | |

**results.parquet** (one row per engine × chunk; `human_results.parquet` uses `engine_id="human"`)

| column | type |
|---|---|
| chunk_id, engine_id, voice_id, run_id | str |
| synth_path | str |
| synth_wall_s, audio_dur_s | float |
| peak_vram_mb | int? |
| whisper_hyp | str |
| wer, cer | float |
| sub, ins, del | int |
| human_wer, excess_wer | float |
| spk_embed | list[float] (192) |
| spk_sim_first, spk_sim_centroid | float |
| mos | float |
| status | str: ok/truncated/silent/engine_error/excluded |
| model_versions | struct |

## Interfaces

```python
class TTSEngine(Protocol):
    engine_id: str
    voice_id: str
    params: dict
    max_chars: int
    def synthesize(self, text: str, out_path: Path) -> SynthResult

@dataclass
class SynthResult:
    wall_s: float
    peak_vram_mb: int | None
    raw_sample_rate: int
    error: str | None = None
```

```python
class ContentCache:
    def key(self, stage, engine_id, voice_id, params, model_version, chunk_id) -> str
    def has(self, key) -> bool
    def path(self, key) -> Path
    def write_atomic(self, key, producer: Callable[[Path], None]) -> Path
```

## Chunk buckets

| bucket | target |
|---|---|
| XS | 1 sentence |
| S | ~3 sentences |
| M | ~8 sentences |
| L | ~20 sentences, capped at min(engine.max_chars) across configured engines |

Buckets rotate XS→S→M→L→XS… within each chapter so every bucket appears at every position decile.

## Pinned models

Whisper large-v3 (faster-whisper); WhisperX `WAV2VEC2_ASR_LARGE_LV60K_960H` aligner; SpeechBrain `spkrec-ecapa-voxceleb`; UTMOS22 strong. Engines (all open-source, local): Piper `en_US-lessac-medium` (CPU); Kokoro v1.0 `af_heart` (CPU); Coqui XTTS v2.0.3 (GPU, fixed 10 s reference clip); F5-TTS base (GPU, same reference clip); Chatterbox (GPU, same reference clip). The three cloning engines share one reference clip so voice-consistency comparisons are fair. Verify exact identifiers and license terms against current releases before pinning in config.

## Analysis contract

- Primary: `excess_wer ~ char_len + position_index + C(book_id)`, OLS, HC3 SEs, per engine.
- Ranking: mean excess_wer per engine, 10 000 bootstrap resamples stratified by book, 95% percentile CI.
- Exclude `status != ok` from intelligibility stats; report exclusion rate per engine separately.

## Concurrency

CPU engines (Piper, Kokoro): ProcessPoolExecutor, cores−2 workers. GPU engines (XTTS, F5-TTS, Chatterbox) and Whisper: strictly one model loaded at a time; the runner unloads before switching. Engine exceptions are caught per chunk and recorded as `engine_error`.

## Environment

Python 3.11, PyTorch 2.x, CUDA 12.x. ≥8 GB VRAM (e.g. RTX 3070) is sufficient provided only one GPU model is loaded at a time — Whisper and the GPU TTS engines must never share the card. If Whisper OOMs on long chunks, set `compute_type="int8_float16"` and record it in `model_versions`. CPU fallback = Whisper `medium` int8 and CPU engines only (record substitution in `model_versions`). Pin in `requirements.lock`.
