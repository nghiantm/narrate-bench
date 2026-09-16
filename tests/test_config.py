from pathlib import Path

import pytest
from pydantic import ValidationError

from narrate_bench.config import load_config

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_valid_config_loads():
    cfg = load_config(REPO_ROOT / "config.yaml")
    assert len(cfg.books) == 5
    assert len(cfg.engines) == 5
    assert cfg.whisper.model == "large-v3"


def test_missing_required_field_names_it(tmp_path):
    bad = tmp_path / "config.yaml"
    bad.write_text(
        """
books:
  - book_id: x
    librivox_url: "https://example.com"
    chapter_regex: "^Chapter"
engines: {}
"""
    )
    with pytest.raises(ValidationError) as exc_info:
        load_config(bad)
    assert "gutenberg_id" in str(exc_info.value)
