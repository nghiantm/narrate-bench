import numpy as np
import soundfile as sf

from narrate_bench.audio.slice import MIN_ALIGN_CONF, PAD_MS, slice_chunk


def _make_chapter_wav(path, duration_s=10.0, sr=16000):
    t = np.arange(int(duration_s * sr))
    tone = (np.sin(2 * np.pi * 220 * t / sr) * 8000).astype(np.int16)
    sf.write(str(path), tone, sr, subtype="PCM_16", format="WAV")
    return sr


def _words(*, start, end, score):
    return [{"word": "w", "start": start, "end": end, "score": score}]


def test_high_confidence_words_produce_a_slice(tmp_path):
    chapter_wav = tmp_path / "chapter.wav"
    sr = _make_chapter_wav(chapter_wav)
    words = [
        {"word": "one", "start": 1.0, "end": 1.2, "score": 0.9},
        {"word": "two", "start": 1.3, "end": 1.6, "score": 0.8},
        {"word": "three", "start": 1.7, "end": 2.0, "score": 0.95},
    ]
    out_path = tmp_path / "out.wav"

    conf, human_audio = slice_chunk(chapter_wav, words, out_path)

    assert conf == 1.0
    assert human_audio == str(out_path)
    assert out_path.exists()

    info = sf.info(str(out_path))
    expected_dur = (2.0 - 1.0) + 2 * PAD_MS / 1000
    assert abs(info.duration - expected_dur) < 0.05


def test_low_confidence_words_produce_no_slice(tmp_path):
    chapter_wav = tmp_path / "chapter.wav"
    _make_chapter_wav(chapter_wav)
    words = [
        {"word": "one", "start": 1.0, "end": 1.2, "score": 0.1},
        {"word": "two", "start": 1.3, "end": 1.6, "score": 0.2},
    ]
    out_path = tmp_path / "out.wav"

    conf, human_audio = slice_chunk(chapter_wav, words, out_path)

    assert conf < MIN_ALIGN_CONF
    assert human_audio is None
    assert not out_path.exists()


def test_align_conf_is_fraction_above_threshold_not_average_score(tmp_path):
    chapter_wav = tmp_path / "chapter.wav"
    _make_chapter_wav(chapter_wav)
    # 3 of 4 words score above 0.5 -> align_conf should be 0.75, not the mean score
    words = [
        {"word": "a", "start": 1.0, "end": 1.1, "score": 0.9},
        {"word": "b", "start": 1.1, "end": 1.2, "score": 0.9},
        {"word": "c", "start": 1.2, "end": 1.3, "score": 0.9},
        {"word": "d", "start": 1.3, "end": 1.4, "score": 0.1},
    ]
    conf, _ = slice_chunk(chapter_wav, words, tmp_path / "out.wav")
    assert conf == 0.75


def test_pad_is_clamped_to_audio_bounds(tmp_path):
    chapter_wav = tmp_path / "chapter.wav"
    _make_chapter_wav(chapter_wav, duration_s=1.0)  # short chapter
    words = [{"word": "first", "start": 0.02, "end": 0.9, "score": 0.9}]
    out_path = tmp_path / "out.wav"

    conf, human_audio = slice_chunk(chapter_wav, words, out_path)

    assert human_audio is not None
    info = sf.info(str(out_path))
    assert info.duration <= 1.0 + 0.01  # never runs past the source audio's own length
