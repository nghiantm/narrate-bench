"""LibriVox section listing for the human-narration baseline (Track C)."""

from __future__ import annotations

import json
import urllib.request

API_URL = "https://librivox.org/api/feed/audiobooks/?id={id}&extended=1&format=json"


def fetch_sections(librivox_id: int) -> list[dict]:
    """Section list (section_number, title, listen_url, readers, ...) for a LibriVox book id."""
    req = urllib.request.Request(
        API_URL.format(id=librivox_id),
        headers={"User-Agent": "narrate-bench/0.1"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.load(resp)
    books = data.get("books") or []
    if not books:
        raise ValueError(f"no LibriVox book found for id {librivox_id}")
    sections = books[0].get("sections") or []
    return sorted(sections, key=lambda s: int(s["section_number"]))
