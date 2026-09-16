# CURRENT_TASK.md — Narrate Bench

Read ARCHITECTURE.md first. Work only on the milestone below. When its acceptance criteria pass, append an entry to TASK_LOG.md, mark the milestone `[x]` in IMPLEMENTATION_PLAN.md, and stop. Do not begin the next milestone in the same session.

---

## Active milestone: M04 — Text: chunker

### Goal
Split each book's normalized text into the engine-independent chunks every later stage keys off, writing `chunks.parquet` per the ARCHITECTURE.md schema.

### Scope
1. `narrate_bench/text/chunk.py`:
   - Sentence splitting: use `pysbd` or NLTK's punkt (pick one, add it to `pyproject.toml`/`requirements.lock` — this is the first real NLP dependency, still no ML/GPU libraries).
   - Bucket rotation: XS (1 sentence) -> S (~3 sentences) -> M (~8 sentences) -> L (~20 sentences, capped at `min(engine.max_chars)` across `config.yaml`'s configured engines) -> XS -> ... within each chapter, per ARCHITECTURE.md "Chunk buckets". A chunk that would exceed the cap is truncated at the last full sentence that fits, not mid-sentence.
   - `chunk_id = sha256(book_id + text)[:16]`.
   - Build one `chunks.parquet` (pyarrow, via pandas) across all books with columns exactly per ARCHITECTURE.md's `chunks.parquet` schema: `chunk_id, book_id, chapter_idx, position_index, bucket, char_len, word_count, text, human_audio, align_conf` — `human_audio`/`align_conf` are null (this milestone doesn't touch human audio; that's M09/M10).
   - `chapter_idx`: 0-based index into the book's chapter list (from `{book_id}.chapters.json`, written by M03's `nb prepare`). `position_index`: 0-based global order of the chunk within the whole book (across all chapters).
2. Wire `chunk.py` into `nb prepare`: after writing `{book_id}.norm.txt` and `{book_id}.chapters.json`, chunk each book's normalized text and append its rows to the shared `chunks.parquet` (rewrite the full file each run — this is cheap CPU work with no need for the content cache here, unlike the network fetch).
3. `tests/test_chunk.py`.

### Out of scope
Any engine/synthesis code, any audio code, human baseline handling (`human_audio`/`align_conf` stay null), parallelizing the chunker (it's CPU-cheap, no need).

### Acceptance criteria
- Test: no chunk's `char_len` exceeds `min(engine.max_chars)` from the config used to chunk it.
- Test: for a book chunked with the full bucket rotation, bucket counts per position decile (split `position_index` into 10 equal-width bins across the book) are within ±20% of a uniform distribution across buckets.
- `nb prepare` works end to end for the real 5-book config and prints chunk stats per book (count, bucket distribution).
- `pytest -q` passes, including all prior milestone tests.

### Verification commands
```
. .venv/bin/activate
pytest -q
nb prepare
python -c "import pandas as pd; df = pd.read_parquet('results/../data/chunks.parquet') if False else pd.read_parquet('data/chunks.parquet'); print(df.groupby('book_id').size()); print(df['bucket'].value_counts())"
```

### On completion
Append the TASK_LOG entry with the exact `pytest -q` and chunk-stats output, mark M04 `[x]` in IMPLEMENTATION_PLAN.md, then replace this file's active milestone with M05 — Engine base + Piper + audio conform (copy its scope and acceptance criteria from IMPLEMENTATION_PLAN.md and expand into the same sections as above). Note before starting M05: Track B introduces the first real ML/engine dependencies (Piper) and the audio contract — check whether Piper needs anything from me (model download, license) before assuming it can run unattended.
