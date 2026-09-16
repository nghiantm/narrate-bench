# CURRENT_TASK.md — Narrate Bench

Read ARCHITECTURE.md first. Work only on the milestone below. When its acceptance criteria pass, append an entry to TASK_LOG.md, mark the milestone `[x]` in IMPLEMENTATION_PLAN.md, and stop. Do not begin the next milestone in the same session.

---

## Active milestone: M03 — Text: fetch and normalize

### Goal
Produce the single normalized text file each book gets, per ARCHITECTURE.md non-negotiable 1: `data/text/{book_id}.norm.txt`, written once by `nb prepare` and read byte-identically by every later stage.

### Scope
1. `narrate_bench/text/gutenberg.py`: `fetch(gutenberg_id: int) -> str` downloads the Gutenberg plain-text edition; `strip_boilerplate(raw: str) -> str` removes the standard Gutenberg header/footer (`*** START OF ... ***` / `*** END OF ... ***` markers and variants); `split_chapters(text: str, chapter_regex: str) -> list[tuple[str, str]]` splits on the book's configured heading regex, returning `(heading, body)` pairs.
2. `narrate_bench/text/normalize.py`: `NORMALIZER_VERSION` constant; `normalize(text: str) -> str` doing, in a fixed documented order: Unicode NFKC, curly/smart quotes → straight, dash unification (em/en dash variants → one consistent form), abbreviation expansion via a small lookup table (e.g. `Mr.` → `Mister`, config-driven or a module-level table — pick one and document it), numeral spelling (integers under 1000 and years spelled out per a stated rule), whitespace collapse (no double spaces, no trailing whitespace, single `\n` between paragraphs).
3. Wire `nb prepare` (in `cli.py`) to: for each book in `config.yaml`, fetch, strip boilerplate, split chapters, normalize the full text, write `data/text/{book_id}.norm.txt` and a chapter index JSON (`data/text/{book_id}.chapters.json`: list of `{heading, start_char, end_char}` into the normalized text) — using `ContentCache` so a rerun with the same inputs does not re-download. Print per-book chunk/chapter stats.
4. `tests/test_normalize.py`: 50 golden-case tests, each a `(input, expected_output)` pair covering NFKC, quote straightening, dash unification, abbreviation expansion, numeral spelling, and whitespace collapse (a table-driven test is fine — 50 rows in a list, not 50 separate test functions, unless that reads better).
5. `tests/test_gutenberg.py`: boilerplate stripping and chapter splitting against a small fixture text (do not hit the network in tests — use a fixture string, not a live download).

### Out of scope
Chunking into buckets (M04), any engine/synthesis code, any audio code, downloading more than the one book used for the "one book" acceptance check during development (the full 5-book run happens naturally once `nb prepare` is correct, but is not itself a milestone requirement to execute here).

### Acceptance criteria
- 50 golden-case normalizer tests pass.
- Gutenberg fetch/strip/split tests pass against fixtures (no network in tests).
- Running `nb prepare` on one configured book produces `data/text/{book_id}.norm.txt` and `data/text/{book_id}.chapters.json`.
- Running `nb prepare` again on the same book produces a byte-identical `.norm.txt` (diff is empty) and does not re-fetch (assert via cache hit / mock).
- `pytest -q` passes, including all prior milestone tests.

### Verification commands
```
. .venv/bin/activate
pytest -q
nb prepare
diff <(nb prepare 2>&1; cat data/text/pride_and_prejudice.norm.txt) <(cat data/text/pride_and_prejudice.norm.txt)
```

### On completion
Append the TASK_LOG entry with the exact `pytest -q` output and `nb prepare` output, mark M03 `[x]` in IMPLEMENTATION_PLAN.md, then replace this file's active milestone with M04 — Text: chunker (copy its scope and acceptance criteria from IMPLEMENTATION_PLAN.md and expand into the same sections as above).
