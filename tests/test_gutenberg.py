import pytest

from narrate_bench.text.gutenberg import split_chapters, strip_boilerplate

FIXTURE = """Some preamble text about the book.
Produced by Example Team.

*** START OF THE PROJECT GUTENBERG EBOOK EXAMPLE ***

CHAPTER I.

It was a dark and stormy night.

CHAPTER II.

The plot thickened considerably.

*** END OF THE PROJECT GUTENBERG EBOOK EXAMPLE ***

More boilerplate license text goes here.
"""


def test_strip_boilerplate_removes_header_and_footer():
    stripped = strip_boilerplate(FIXTURE)
    assert "Produced by Example Team" not in stripped
    assert "More boilerplate license text" not in stripped
    assert "dark and stormy night" in stripped
    assert "START OF" not in stripped
    assert "END OF" not in stripped


def test_strip_boilerplate_raises_without_markers():
    with pytest.raises(ValueError):
        strip_boilerplate("no markers here at all")


def test_split_chapters_returns_heading_and_offsets():
    stripped = strip_boilerplate(FIXTURE)
    chapters = split_chapters(stripped, r"^CHAPTER [IVXLC]+\.?$")

    assert len(chapters) == 2
    assert chapters[0]["heading"] == "CHAPTER I."
    assert chapters[1]["heading"] == "CHAPTER II."

    # offsets slice back to the matched heading through the next heading
    assert "dark and stormy night" in stripped[chapters[0]["start_char"] : chapters[0]["end_char"]]
    assert "plot thickened" in stripped[chapters[1]["start_char"] : chapters[1]["end_char"]]
    assert chapters[0]["end_char"] == chapters[1]["start_char"]
    assert chapters[1]["end_char"] == len(stripped)


def test_split_chapters_raises_when_no_match():
    stripped = strip_boilerplate(FIXTURE)
    with pytest.raises(ValueError):
        split_chapters(stripped, r"^NOPE NOTHING MATCHES$")
