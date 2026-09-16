from pathlib import Path

import pytest

from narrate_bench.cache import ContentCache


def make_cache(tmp_path) -> ContentCache:
    return ContentCache(tmp_path / "cache")


BASE_ARGS = dict(
    stage="synthesize",
    engine_id="piper",
    voice_id="en_US-lessac-medium",
    params={"speed": 1.0},
    model_version="1.2.0",
    chunk_id="abc123",
)


def test_identical_inputs_same_key(tmp_path):
    cache = make_cache(tmp_path)
    k1 = cache.key(**BASE_ARGS)
    k2 = cache.key(**BASE_ARGS)
    assert k1 == k2


def test_param_key_order_does_not_affect_hash(tmp_path):
    cache = make_cache(tmp_path)
    k1 = cache.key(**{**BASE_ARGS, "params": {"a": 1, "b": 2}})
    k2 = cache.key(**{**BASE_ARGS, "params": {"b": 2, "a": 1}})
    assert k1 == k2


@pytest.mark.parametrize(
    "field,value",
    [
        ("stage", "transcribe"),
        ("engine_id", "kokoro"),
        ("voice_id", "other_voice"),
        ("params", {"speed": 2.0}),
        ("model_version", "1.3.0"),
        ("chunk_id", "def456"),
    ],
)
def test_single_input_change_changes_key(tmp_path, field, value):
    cache = make_cache(tmp_path)
    baseline = cache.key(**BASE_ARGS)
    changed = cache.key(**{**BASE_ARGS, field: value})
    assert baseline != changed


def test_write_atomic_raising_producer_leaves_no_file(tmp_path):
    cache = make_cache(tmp_path)
    key = cache.key(**BASE_ARGS)

    def bad_producer(path: Path) -> None:
        path.write_text("partial")
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        cache.write_atomic(key, bad_producer)

    assert not cache.path(key).exists()
    assert not cache.path(key).with_suffix(cache.path(key).suffix + ".tmp").exists()


def test_has_false_before_true_after_write(tmp_path):
    cache = make_cache(tmp_path)
    key = cache.key(**BASE_ARGS)

    assert cache.has(key) is False

    cache.write_atomic(key, lambda path: path.write_text("data"))

    assert cache.has(key) is True
    assert cache.path(key).read_text() == "data"
