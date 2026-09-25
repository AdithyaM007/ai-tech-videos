"""Unit tests for helper functions."""

import pytest
from PIL import Image

from compat import patch_pil_antialias
from generate_episode import build_narration, split_text
from video_generator import _scale_segments, _summarize, frames_to_segments, load_font


@pytest.mark.unit
class TestBuildNarration:
    def test_combines_parts_in_order(self, sample_script_json):
        text = build_narration(sample_script_json)
        assert text.startswith(sample_script_json["hook"])
        assert text.endswith(sample_script_json["outro"])
        for section in sample_script_json["sections"]:
            assert section["script"] in text

    def test_skips_empty_parts(self):
        assert build_narration({"hook": "", "intro": "Hi", "sections": [{}]}) == "Hi"


@pytest.mark.unit
class TestSplitText:
    def test_short_text_single_chunk(self):
        assert split_text("Hello there.", 100) == ["Hello there."]

    def test_empty_text(self):
        assert split_text("", 100) == []

    def test_splits_on_sentences(self):
        text = "One two three. " * 20
        chunks = split_text(text.strip(), 50)
        assert all(len(chunk) <= 50 for chunk in chunks)
        assert " ".join(chunks) == text.strip()

    def test_long_sentence_is_hard_split(self):
        text = "word " * 50
        chunks = split_text(text.strip(), 30)
        assert all(len(chunk) <= 30 for chunk in chunks)
        assert " ".join(chunks).split() == text.split()


@pytest.mark.unit
class TestTimingHelpers:
    def test_frames_to_segments(self):
        segments = frames_to_segments(["a", "a", "b", "b", "b", "a"], fps=10)
        assert [p for p, _ in segments] == ["a", "b", "a"]
        assert [round(d, 2) for _, d in segments] == [0.2, 0.3, 0.1]

    def test_scale_segments_fills_budget(self):
        scaled = _scale_segments([("a", 1.0), ("b", 3.0)], 20.0)
        assert sum(d for _, d in scaled) == pytest.approx(20.0)
        assert scaled[1][1] == pytest.approx(15.0)

    def test_scale_segments_keeps_typing_real_time(self):
        segments = [
            ("slide", 3.0),
            ("__fixed__", 0.0),
            ("f1", 0.5),
            ("f2", 0.5),
            ("hold", 10.0),
            ("__endfixed__", 0.0),
        ]
        scaled = dict(_scale_segments(segments, 27.0))
        assert scaled["f1"] == scaled["f2"] == 0.5
        assert scaled["slide"] + scaled["hold"] == pytest.approx(26.0)

    def test_summarize(self):
        bullets = _summarize("First point. Second point. Third. Fourth. Fifth.")
        assert bullets[0] == "First point"
        assert len(bullets) == 4


@pytest.mark.unit
class TestCompat:
    def test_patch_pil_antialias(self, monkeypatch):
        monkeypatch.delattr(Image, "ANTIALIAS", raising=False)
        patch_pil_antialias()
        assert Image.ANTIALIAS == Image.LANCZOS

    def test_load_font_fallback(self):
        assert load_font(20, ("definitely-not-a-font.ttf",)) is not None
