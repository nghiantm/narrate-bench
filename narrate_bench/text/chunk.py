"""Sentence splitting and bucket-rotation chunker."""

from __future__ import annotations

import hashlib
import itertools

import pysbd

BUCKET_ORDER = ["XS", "S", "M", "L"]
BUCKET_TARGET_SENTENCES = {"XS": 1, "S": 3, "M": 8, "L": 20}

_segmenter = pysbd.Segmenter(language="en", clean=False)


def segment_sentences(text: str) -> list[str]:
    return [s.strip() for s in _segmenter.segment(text) if s.strip()]


def _cap_group(sentences: list[str], max_chars: int) -> list[str]:
    """Keep sentences up to max_chars, never splitting mid-sentence. Always
    keeps at least the first sentence, even if it alone exceeds max_chars,
    so the caller always makes forward progress."""
    kept = [sentences[0]]
    total = len(sentences[0])
    for s in sentences[1:]:
        total_with_next = total + 1 + len(s)  # +1 for the joining space
        if total_with_next > max_chars:
            break
        kept.append(s)
        total = total_with_next
    return kept


def build_chunks(book_id: str, norm_text: str, chapters: list[dict], max_chars: int) -> list[dict]:
    """Chunk a book's normalized text per ARCHITECTURE.md's chunks.parquet
    schema. Buckets rotate XS->S->M->L->XS.. restarting at each chapter.
    Every sentence appears in exactly one chunk; a group is shrunk (never
    split mid-sentence) if it would exceed max_chars."""
    rows = []
    position_index = 0
    for chapter_idx, chapter in enumerate(chapters):
        chapter_text = norm_text[chapter["start_char"] : chapter["end_char"]]
        sentences = segment_sentences(chapter_text)
        bucket_cycle = itertools.cycle(BUCKET_ORDER)
        i = 0
        while i < len(sentences):
            bucket = next(bucket_cycle)
            target_n = BUCKET_TARGET_SENTENCES[bucket]
            candidate = sentences[i : i + target_n]
            kept = _cap_group(candidate, max_chars)
            text = " ".join(kept)
            rows.append(
                {
                    "chunk_id": hashlib.sha256((book_id + text).encode()).hexdigest()[:16],
                    "book_id": book_id,
                    "chapter_idx": chapter_idx,
                    "position_index": position_index,
                    "bucket": bucket,
                    "char_len": len(text),
                    "word_count": len(text.split()),
                    "text": text,
                    "human_audio": None,
                    "align_conf": None,
                }
            )
            i += len(kept)
            position_index += 1
    return rows
