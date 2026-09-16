# Narrate Bench — Project Description and Plan

## 1. What it is

Narrate Bench is a reproducible benchmark that measures how well text-to-speech (TTS) engines hold up on long-form content. Most TTS evaluations use short, curated sentences. Audiobooks are the opposite case: hours of continuous speech, proper nouns, archaic vocabulary, dialogue, and the risk of quality drifting over a long run.

The benchmark synthesizes five complete public-domain books with five TTS engines, transcribes the output with Whisper, and scores it against the source text. The key methodological choice is that the same books also have human narrations (LibriVox), which are run through the identical Whisper pipeline. The human-narration error rate is treated as Whisper's own floor on that text, and is subtracted from each engine's error so the engines are not penalized for passages Whisper cannot transcribe from anyone.

## 2. Questions the benchmark answers

1. **Intelligibility.** Which engine produces speech that Whisper transcribes most faithfully, after removing Whisper's baseline error?
2. **Long-form stability.** Does error grow with position in the book (drift, state leakage, degradation), or is it explained by chunk length and text difficulty alone?
3. **Voice consistency.** Does the speaker identity stay stable across hours of synthesis?
4. **Cost and throughput.** What does each engine cost, in dollars and wall-clock time, to narrate a full book?

Question 2 is the one that distinguishes this from existing TTS comparisons.

## 3. Data

**Books (5).** Public-domain titles that exist as both a Project Gutenberg text and a complete LibriVox solo recording (single narrator, so voice-consistency baselines are meaningful). Aim for variety: one dialogue-heavy novel, one with many proper nouns, one with archaic prose, one non-fiction, one straightforward modern-style prose. Candidates: *Pride and Prejudice*, *Treasure Island*, *The Adventures of Sherlock Holmes*, *The Autobiography of Benjamin Franklin*, *Anne of Green Gables*.

**Text preparation.**
- Strip Gutenberg boilerplate; split into chapters using the book's own headings.
- Normalize once: Unicode NFKC, curly quotes to straight, em-dashes to a consistent form, expand common abbreviations, spell out numerals under a fixed rule. Save the normalized text; every downstream stage reads only this version so TTS input and scoring reference are identical.
- Verify chapter alignment with the LibriVox track list by hand (LibriVox sometimes splits or merges chapters).

**Audio preparation.**
- Download LibriVox MP3s; convert to 16 kHz mono WAV.
- Everything synthetic is also resampled to 16 kHz mono so Whisper and SpeechBrain see identical formats.

## 4. Chunking

Split each chapter at sentence boundaries into chunks with deliberately varied target lengths, so chunk length is a real independent variable rather than a constant:

| Bucket | Target |
|---|---|
| XS | 1 sentence |
| S | ~3 sentences (~40–60 words) |
| M | ~8 sentences (~120–160 words) |
| L | ~20 sentences (~300–400 words) |

Assign buckets in a rotating pattern within each chapter so all four sizes appear at every position in the book. Record per chunk: `book`, `chapter`, `position_index` (global order), `bucket`, `char_len`, `word_count`, `text`, `text_hash`.

## 5. Engines

Five open-source engines behind a single interface, all run locally:

| Engine | Type | Why |
|---|---|---|
| Piper | Local, CPU | Fast, common in self-hosted setups |
| Kokoro | Local, CPU, 82M params | Strong quality-per-parameter |
| Coqui XTTS v2 | Local, GPU | Established cloning model, larger |
| F5-TTS | Local, GPU | Flow-matching architecture, recent |
| Chatterbox | Local, GPU | Recent open-weights cloning model |

All five are open-source and run locally: no accounts, keys, or spend. This also makes the benchmark reproducible, since hosted APIs are updated silently while pinned open-source releases are not. A hosted-engine comparison is left as an optional future track.

One fixed voice per engine, chosen to be a neutral English narrator voice; the three cloning engines (XTTS, F5-TTS, Chatterbox) share a single 10 s reference clip so voice-consistency results are comparable. Log for every chunk: synthesis wall time, output duration, and peak VRAM.

## 6. Human-audio alignment

To compare human and synthetic speech on the same chunks, cut the LibriVox chapter audio at the chunk boundaries:

1. Force-align each chapter's audio to its normalized text to obtain word-level timestamps (WhisperX alignment or a CTC aligner).
2. Slice the audio at the first and last word of each chunk, with a small padding margin.
3. Flag chunks where alignment confidence is low or the narrator skipped/added text; exclude those from the baseline rather than letting bad alignment masquerade as TTS error.

After this step every chunk has six audio files: five synthetic, one human.

## 7. Metrics

**Intelligibility (primary).**
- Transcribe all six versions of every chunk with the same Whisper model (e.g. `large-v3` via faster-whisper), same decoding settings, same text normalizer applied to hypothesis and reference.
- Compute WER and CER with `jiwer`.
- `excess_WER = WER_tts − WER_human` per chunk. This is the headline number. Also report raw WER so the subtraction can be inspected.
- Break out substitution/insertion/deletion counts; deletions are the signal for dropped or truncated audio, which is a distinct TTS failure mode.

**Voice consistency.**
- Extract SpeechBrain ECAPA-TDNN speaker embeddings for every chunk.
- For each engine and book, compute cosine similarity of each chunk to the book's first chunk and to a rolling centroid. Track how this evolves with `position_index`.
- Run the same on the human narration as a reference for natural within-speaker variation.

**Naturalness (secondary).**
- Automatic MOS prediction (UTMOS or equivalent) per chunk. Treat as indicative, not definitive.

**Cost and throughput.**
- Characters per second, real-time factor (audio seconds produced per wall second), and peak VRAM per engine.

## 8. Analysis

Store one row per `(engine, chunk)` in Parquet/SQLite with all metrics and metadata.

**Long-form stability test.** For each engine fit

```
excess_WER ~ char_len + position_index + book (fixed effect)
```

with robust standard errors. The hypothesis is that `char_len` is significant and `position_index` is not. Report coefficients with confidence intervals and plot residual error against position with a rolling mean. Do the same for speaker similarity. This is what backs the claim that quality held over full-length runs.

**Text-difficulty control.** Human WER per chunk is itself a proxy for text difficulty. Show engine excess WER binned by human WER to check whether any engine degrades disproportionately on hard passages.

**Engine ranking.** Mean and median excess WER per engine with bootstrap confidence intervals over chunks. Rank on the primary metric; present the others alongside rather than blending into a composite score.

**Deliverable chart set.**
1. Excess WER by engine (box/violin, all chunks).
2. Excess WER vs chunk length, one line per engine.
3. Excess WER vs position in book, one line per engine, with regression fit.
4. Speaker similarity vs position, engines plus human reference.
5. Cost and real-time factor table.

## 9. System design

```
narrate_bench/
  cli.py              # typer: prepare | synthesize | align | transcribe | score | analyze
  config.yaml         # books, engines, voices, whisper settings, sample plan
  text/               # gutenberg fetch, normalize, chunk
  engines/            # base.py + one module per engine
  audio/              # resample, slice, alignment
  asr/                # whisper wrapper, jiwer scoring
  speaker/            # speechbrain embeddings, similarity
  cache/              # hash-keyed content store
  analysis/           # stats + plots
```

**Caching and resumability.**
- Every artifact (synth WAV, transcript JSON, embedding, human slice) is stored under a content hash: `sha256(stage, engine_id, voice, params, text_hash)`.
- A stage checks for its output hash before doing work; a killed run resumes by rescanning the cache directory. No separate progress file to corrupt.
- Configuration changes that affect output (Whisper model, voice, normalizer version) are part of the hash, so stale results are never silently reused.
- Test this deliberately: kill a synthesis run midway, restart, confirm no duplicate engine calls.

**Concurrency.** CPU engines run in a process pool sized to available cores. GPU engines and Whisper load strictly one model at a time so an 8 GB card suffices.

**Reproducibility.** Pin model versions and package versions; record them in each result row. Fix Whisper decoding parameters (temperature 0, beam size fixed).

## 10. Plan and milestones

**Phase 0 — Scoping (2–3 days)**
- Choose books; confirm Gutenberg text and complete LibriVox solo recording exist for each.
- Choose engines and voices; pin model revisions and check licenses; record a shared 10 s reference clip for the cloning engines.
- Write `config.yaml`.

**Phase 1 — Text pipeline (3–4 days)**
- Gutenberg fetch and boilerplate stripping.
- Normalizer with unit tests on tricky cases (numbers, abbreviations, quotes).
- Chunker with bucket rotation; verify chunk statistics per book.

**Phase 2 — Engine layer and cache (4–5 days)**
- `TTSEngine` base class; implement Piper first as the fast path.
- Hash-keyed cache; resumability test.
- Add remaining four engines; synthesize one chapter with each and listen to it.

**Phase 3 — Human alignment (3–4 days)**
- Force-align LibriVox chapters; slice into chunks.
- Spot-check 30 slices by ear; tune padding and exclusion thresholds.

**Phase 4 — Scoring (3–4 days)**
- Whisper wrapper with fixed settings; transcribe human and synthetic audio for one book.
- WER/CER scoring; sanity-check that human WER is low and plausible, and that excess WER is near zero for a chunk where TTS and human sound equally clear.
- SpeechBrain embeddings and similarity.

**Phase 5 — Full run (3–7 days, mostly machine time)**
- Synthesize and score all books across all engines. Local GPU engines dominate the wall time.
- Monitor for engine-specific failures (truncation, silence, rate limits) and add them to the error taxonomy.

**Phase 6 — Analysis and write-up (4–5 days)**
- Fit regressions; produce chart set; compute bootstrap intervals.
- Write README with headline table and the position-vs-length chart near the top.
- Write a short findings section: which engine won, by how much, what surprised you, and where the method is weak.

Total: roughly five to six weeks part-time, with Phase 5 running unattended.

## 11. Risks and mitigations

| Risk | Mitigation |
|---|---|
| LibriVox narrator errors inflate the baseline | Exclude low-confidence alignments; report human WER distribution so readers can see it |
| Whisper hallucinates on silence or truncated audio | Detect near-silent outputs before ASR; count as a TTS failure, not a transcription |
| GPU OOM on 8 GB card | One GPU model resident at a time; Whisper `int8_float16` fallback |
| Engine truncates long chunks | L-bucket exists to expose this; log output duration vs expected |
| Text normalizer mismatch between TTS input and scoring reference | Single normalized text file per book; hash includes normalizer version |
| "Position doesn't matter" is trivially true for stateless engines | Speaker-drift metric and the pipeline-stability interpretation give the finding substance either way |

## 12. Deliverables

- Public repository with the pipeline, config, and `make reproduce` for a single small book.
- Results Parquet file and the chart set.
- README with headline table, methodology summary, findings, and limitations.
- Optional: short blog post walking through the baseline-subtraction idea and the stability result.

## 13. Stack

Python 3.11, typer, pandas/pyarrow, faster-whisper, jiwer, speechbrain, torchaudio, WhisperX (alignment), statsmodels, matplotlib/seaborn, pytest.

---

# Appendix — Technical Specification

## A. Environment and hardware

- Python 3.11, CUDA 12.x, PyTorch 2.x. Pin everything in `requirements.lock`.
- Minimum for the full run: one GPU with ≥12 GB VRAM (Whisper large-v3 in fp16 needs ~6 GB; XTTS v2 ~4 GB; run them in separate processes, not concurrently on a 12 GB card). 8+ CPU cores for Piper/Kokoro. ~200 GB disk: five books × six audio versions at 16 kHz/16-bit is roughly 60–80 GB, plus MP3 sources and cache.
- Without a GPU: swap Whisper to `medium` int8 on CPU and drop XTTS; document the substitution in results metadata.

## B. Audio specification

All audio entering ASR or SpeechBrain must be: WAV, PCM 16-bit, 16 000 Hz, mono, peak-normalized to −1 dBFS. Resampling via `torchaudio.functional.resample` (sinc, Kaiser window). Leading/trailing silence trimmed at −40 dBFS with 100 ms padding retained. Any file failing these checks is rejected at ingest, not silently converted downstream.

## C. Pinned models and settings

| Component | Version / setting |
|---|---|
| Whisper | `large-v3` via faster-whisper, compute_type `float16`, beam_size 5, temperature 0, `condition_on_previous_text=False`, `vad_filter=True`, language forced `en`, `word_timestamps=False` for scoring |
| Alignment | WhisperX `WAV2VEC2_ASR_LARGE_LV60K_960H` aligner; chunks with <80 % of words aligned at confidence >0.5 are flagged |
| Speaker embeddings | SpeechBrain `spkrec-ecapa-voxceleb` (192-dim), input clipped to first 20 s of chunk |
| MOS | UTMOS22 strong learner (`sarulab-speech/UTMOS22`) |
| Text normalizer | Whisper's `EnglishTextNormalizer` applied to both hypothesis and reference at scoring time; project normalizer (Section 3) applied once to source text only |
| Engines | Piper `en_US-lessac-medium`; Kokoro v1.0 `af_heart`; XTTS v2.0.3, F5-TTS base, Chatterbox — all three cloning engines use the same fixed 10 s reference clip |

`condition_on_previous_text=False` matters: it prevents Whisper from carrying context across segments, which would otherwise mask TTS errors.

## D. Data schemas

**chunks.parquet** — one row per chunk, engine-independent

```
chunk_id        str   sha256(book_id + normalized_text)[:16]
book_id         str
chapter_idx     int
position_index  int   global order within book, 0-based
bucket          str   XS | S | M | L
char_len        int
word_count      int
text            str   normalized
human_audio     str   path or null if alignment excluded
align_conf      float
```

**results.parquet** — one row per (engine, chunk)

```
chunk_id, engine_id, voice_id, run_id
synth_path         str
synth_wall_s       float
audio_dur_s        float
peak_vram_mb       int    null for CPU engines
whisper_hyp        str
wer, cer           float
sub, ins, del      int
human_wer          float  joined from human transcription
excess_wer         float  wer − human_wer
spk_embed          list[float] 192
spk_sim_first      float  cosine to book's first chunk
spk_sim_centroid   float  cosine to rolling 50-chunk centroid
mos                float
status             str    ok | truncated | silent | engine_error | excluded
model_versions     struct whisper, aligner, ecapa, engine
```

**human_results.parquet** — same ASR fields, `engine_id = "human"`.

## E. Interfaces

```python
class TTSEngine(Protocol):
    engine_id: str
    voice_id: str
    params: dict          # anything affecting output; goes into the hash
    max_chars: int        # engine's hard input limit; chunker respects it
    def synthesize(self, text: str, out_path: Path) -> SynthResult

@dataclass
class SynthResult:
    wall_s: float
    peak_vram_mb: int | None
    raw_sample_rate: int
    error: str | None
```

Engines must be pure functions of `(text, voice_id, params)`; no hidden state between calls. XTTS satisfies this by re-loading the reference embedding per call from a cached tensor.

**Cache key**

```
key = sha256(
    stage            # synth | asr | embed | mos | align
  + engine_id + voice_id
  + json.dumps(params, sort_keys=True)
  + model_version    # e.g. whisper large-v3 + faster-whisper version
  + chunk_id
).hexdigest()
path = cache_root / stage / key[:2] / key
```

`cache.has(key)` is the resumability check. Writes go to a temp file then `os.replace`, so a crash mid-write never leaves a partial artifact that looks complete.

## F. CLI contract

```
nb prepare   --config cfg.yaml                 # fetch, normalize, chunk → chunks.parquet
nb synthesize --engine piper --book all        # idempotent, resumable
nb align     --book all                        # human slices, align_conf
nb transcribe --source all                     # engines + human
nb score                                       # wer/cer/excess → results.parquet
nb embed                                       # ecapa + mos
nb analyze   --out reports/                    # stats + figures
nb status                                      # cache coverage per stage/engine/book
```

Every command exits non-zero on any unhandled per-chunk error only if `--strict`; otherwise it records `status` and continues.

## G. Concurrency and rate limits

- Local engines: `ProcessPoolExecutor`, workers = cores − 2; one GPU engine process at a time.
- GPU engines: one model resident at a time; runner unloads before switching. Engine exceptions recorded per chunk as `status=engine_error`.

## H. Statistics

- Regression: `statsmodels.OLS` on `excess_wer ~ char_len + position_index + C(book_id)`, HC3 robust SEs, fit separately per engine. Also a version with `position_index` replaced by `chapter_idx` to check granularity.
- Rankings: 10 000-resample bootstrap over chunks, stratified by book, for mean excess WER per engine; report 95 % percentile intervals.
- Exclude `status != ok` from intelligibility stats but report exclusion rates per engine as their own metric.

## I. Tests

- Normalizer: golden tests on ~50 hand-picked sentences (numbers, abbreviations, quotes, dashes).
- Chunker: bucket distribution is uniform across position deciles; no chunk exceeds any engine's `max_chars`.
- Cache: killing a synthesis mid-run and restarting produces zero duplicate engine calls (assert via call counter on a mock engine).
- Scoring: `excess_wer` is exactly 0 when hypothesis equals human transcript.
- End-to-end: `make reproduce` runs one short book through Piper only in under 10 minutes on CPU.
