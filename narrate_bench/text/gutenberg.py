"""Fetch a Project Gutenberg book by ID and strip boilerplate."""

from __future__ import annotations

import re
import urllib.request

GUTENBERG_URL = "https://www.gutenberg.org/cache/epub/{id}/pg{id}.txt"

START_RE = re.compile(r"^\*\*\* ?START OF (THE|THIS) PROJECT GUTENBERG EBOOK.*\*\*\*\s*$", re.MULTILINE | re.IGNORECASE)
END_RE = re.compile(r"^\*\*\* ?END OF (THE|THIS) PROJECT GUTENBERG EBOOK.*\*\*\*\s*$", re.MULTILINE | re.IGNORECASE)


def fetch(gutenberg_id: int) -> str:
    req = urllib.request.Request(
        GUTENBERG_URL.format(id=gutenberg_id),
        headers={"User-Agent": "narrate-bench/0.1"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8")


def strip_boilerplate(raw: str) -> str:
    start_match = START_RE.search(raw)
    end_match = END_RE.search(raw)
    if not start_match or not end_match:
        raise ValueError("could not find Gutenberg START/END markers")
    return raw[start_match.end() : end_match.start()].strip("\n")


def split_chapters(text: str, chapter_regex: str) -> list[dict]:
    """Split text at each chapter_regex match. Each entry spans from the
    start of its heading to the start of the next heading (or end of text),
    so chapters[i]["end_char"] == chapters[i + 1]["start_char"]."""
    pattern = re.compile(chapter_regex, re.MULTILINE)
    matches = list(pattern.finditer(text))
    if not matches:
        raise ValueError(f"no chapter headings matched {chapter_regex!r}")

    chapters = []
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        chapters.append({"heading": m.group(0).strip(), "start_char": start, "end_char": end})
    return chapters
