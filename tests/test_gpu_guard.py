import pytest

from narrate_bench.engines import gpu_guard


@pytest.fixture(autouse=True)
def _reset_guard():
    gpu_guard._holder = None
    if gpu_guard._lock.locked():
        gpu_guard._lock.release()
    yield
    gpu_guard._holder = None
    if gpu_guard._lock.locked():
        gpu_guard._lock.release()


def test_second_acquire_before_release_raises():
    gpu_guard.acquire("xtts")
    with pytest.raises(RuntimeError):
        gpu_guard.acquire("f5tts")


def test_acquire_after_release_succeeds():
    gpu_guard.acquire("xtts")
    gpu_guard.release("xtts")
    gpu_guard.acquire("f5tts")  # should not raise
    gpu_guard.release("f5tts")


def test_release_by_non_holder_raises():
    gpu_guard.acquire("xtts")
    with pytest.raises(RuntimeError):
        gpu_guard.release("f5tts")
