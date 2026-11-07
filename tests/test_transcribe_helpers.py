"""Offline tests for the Watcher transcription helpers (watcher/knowledge/tools/transcribe.py).

These cover the pure parsing logic the pipeline depends on, so the module is exercised on
every PR without network, ffmpeg, or Whisper. Network/ASR behaviour is proven separately by
the learning-loop workflow and the committed transcript artifacts.
"""

import importlib.util
from pathlib import Path

import pytest

_MODULE_PATH = Path(__file__).resolve().parents[1] / "watcher" / "knowledge" / "tools" / "transcribe.py"


@pytest.fixture(scope="module")
def tr():
    spec = importlib.util.spec_from_file_location("watcher_transcribe", _MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_slugify(tr):
    assert tr.slugify("How to Share With Just Friends") == "how-to-share-with-just-friends"
    assert tr.slugify("  Multi   Space & Symbols!!  ") == "multi-space-symbols"


def test_stamp_seconds(tr):
    assert tr.stamp(0) == "00:00"
    assert tr.stamp(74.304) == "01:14"


def test_stamp_vtt_hms_and_ms(tr):
    assert tr._stamp("00:00:03.500") == "00:03"
    assert tr._stamp("00:01:14.000") == "01:14"
    assert tr._stamp("01:02:03.999") == "62:03"


def test_stamp_vtt_mmss(tr):
    assert tr._stamp("02:03.500") == "02:03"


def test_stamp_fallback(tr):
    assert tr._stamp("garbage") == "00:00"
