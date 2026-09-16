import pytest

from narrate_bench.text.chunk import BUCKET_ORDER, build_chunks, segment_sentences

CHAPTER_TEXT = " ".join(f"This is sentence number {i}." for i in range(1, 61))

CHAPTERS = [{"heading": "CHAPTER I.", "start_char": 0, "end_char": len(CHAPTER_TEXT)}]


def test_segment_sentences_splits_on_periods():
    sentences = segment_sentences("One. Two. Three.")
    assert sentences == ["One.", "Two.", "Three."]


def test_no_chunk_exceeds_max_chars():
    max_chars = 50
    rows = build_chunks("book", CHAPTER_TEXT, CHAPTERS, max_chars)
    assert len(rows) > 0
    for row in rows:
        assert row["char_len"] <= max_chars or len(row["text"].split(" ", 1)[0]) == len(row["text"])
        # a chunk may exceed max_chars only when it is a single sentence
        # that alone is longer than the cap (unavoidable without mid-sentence splits)
        if row["char_len"] > max_chars:
            assert len(segment_sentences(row["text"])) == 1


def test_no_chunk_exceeds_max_chars_generous_cap():
    max_chars = 1000  # large enough that no single sentence ever needs to overflow
    rows = build_chunks("book", CHAPTER_TEXT, CHAPTERS, max_chars)
    for row in rows:
        assert row["char_len"] <= max_chars


def test_every_sentence_covered_exactly_once():
    max_chars = 1000
    rows = build_chunks("book", CHAPTER_TEXT, CHAPTERS, max_chars)
    reconstructed = " ".join(row["text"] for row in rows)
    original_sentences = segment_sentences(CHAPTER_TEXT)
    reconstructed_sentences = segment_sentences(reconstructed)
    assert reconstructed_sentences == original_sentences


def test_bucket_rotation_restarts_per_chapter():
    max_chars = 1000
    two_chapters = [
        {"heading": "CHAPTER I.", "start_char": 0, "end_char": len(CHAPTER_TEXT)},
        {"heading": "CHAPTER II.", "start_char": len(CHAPTER_TEXT), "end_char": 2 * len(CHAPTER_TEXT)},
    ]
    double_text = CHAPTER_TEXT + " " + CHAPTER_TEXT
    rows = build_chunks("book", double_text, two_chapters, max_chars)
    ch0_buckets = [r["bucket"] for r in rows if r["chapter_idx"] == 0]
    ch1_buckets = [r["bucket"] for r in rows if r["chapter_idx"] == 1]
    assert ch0_buckets[0] == "XS"
    assert ch1_buckets[0] == "XS"  # rotation restarts, not continues from chapter 0


def test_position_index_is_global_and_sequential():
    max_chars = 1000
    two_chapters = [
        {"heading": "CHAPTER I.", "start_char": 0, "end_char": len(CHAPTER_TEXT)},
        {"heading": "CHAPTER II.", "start_char": len(CHAPTER_TEXT), "end_char": 2 * len(CHAPTER_TEXT)},
    ]
    double_text = CHAPTER_TEXT + " " + CHAPTER_TEXT
    rows = build_chunks("book", double_text, two_chapters, max_chars)
    assert [r["position_index"] for r in rows] == list(range(len(rows)))


def test_bucket_distribution_within_20pct_of_uniform_per_decile():
    # A long single-chapter book with many chunks, checked per position decile.
    long_text = " ".join(f"Sentence number {i} appears here now." for i in range(1, 2001))
    chapters = [{"heading": "CHAPTER I.", "start_char": 0, "end_char": len(long_text)}]
    rows = build_chunks("book", long_text, chapters, max_chars=1000)

    n = len(rows)
    decile_size = n // 10
    assert decile_size > len(BUCKET_ORDER) * 3  # enough chunks per decile to judge distribution

    for d in range(10):
        decile_rows = rows[d * decile_size : (d + 1) * decile_size]
        counts = {b: sum(1 for r in decile_rows if r["bucket"] == b) for b in BUCKET_ORDER}
        expected = len(decile_rows) / len(BUCKET_ORDER)
        for b in BUCKET_ORDER:
            assert abs(counts[b] - expected) <= 0.2 * expected + 1
