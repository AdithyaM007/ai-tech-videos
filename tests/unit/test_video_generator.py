"""Unit tests for video_generator.py."""

import os
from unittest.mock import patch

import pytest
from PIL import Image

import config
from video_generator import (
    AdvancedVideoGenerator,
    CodeAnimationGenerator,
    DiagramGenerator,
    SlideGenerator,
)


def _assert_frame(path):
    assert os.path.exists(path)
    with Image.open(path) as image:
        assert image.size == (config.VIDEO_WIDTH, config.VIDEO_HEIGHT)


@pytest.mark.unit
class TestCodeAnimationGenerator:
    def test_generator_initializes(self):
        gen = CodeAnimationGenerator()
        assert gen.width == 1280
        assert gen.height == 720
        assert gen.fps == 30

    def test_animation_frame_paths_created(self, temp_output_dir):
        gen = CodeAnimationGenerator()
        with patch.object(gen, "_render_code_frame"):
            frames = gen.generate_code_animation(
                "print('hello')", temp_output_dir, duration_seconds=3
            )
        assert len(frames) == 90  # 3 seconds x 30 FPS

    def test_only_distinct_frames_rendered(self, temp_output_dir):
        gen = CodeAnimationGenerator()
        code = "print('hello')"
        with patch.object(gen, "_render_code_frame") as render:
            frames = gen.generate_code_animation(code, temp_output_dir, duration_seconds=3)
        assert render.call_count == len(set(frames))
        assert render.call_count <= len(code)
        # The last rendered frame shows the full code without a cursor.
        last_call = render.call_args_list[-1]
        assert last_call.args[0] == code
        assert last_call.kwargs["cursor"] is False

    def test_long_code_finishes_typing_before_end(self, temp_output_dir):
        gen = CodeAnimationGenerator()
        code = "x = 1\n" * 200
        with patch.object(gen, "_render_code_frame") as render:
            frames = gen.generate_code_animation(code, temp_output_dir, duration_seconds=2)
        full_index = frames.index(render.call_args_list[-1].args[1])
        assert full_index <= (len(frames) * 2) // 3

    def test_code_animation_output_format(self, temp_output_dir):
        gen = CodeAnimationGenerator()
        frames = gen.generate_code_animation(
            "for i in range(3):\n    print(i)",
            temp_output_dir,
            duration_seconds=1,
            title="Loop",
        )
        assert all(f.endswith(".png") for f in frames)
        _assert_frame(frames[-1])

    def test_render_static_code(self, temp_output_dir):
        path = os.path.join(temp_output_dir, "static.png")
        CodeAnimationGenerator().render_static_code("print(1)", path)
        _assert_frame(path)


@pytest.mark.unit
class TestDiagramGenerator:
    def test_generator_initializes(self):
        assert DiagramGenerator().width == 1280

    @pytest.mark.slow
    def test_diagram_generator_comparison(self, temp_output_dir):
        output = os.path.join(temp_output_dir, "chart.png")
        DiagramGenerator().generate_comparison_chart("Test", [], output)
        _assert_frame(output)

    @pytest.mark.slow
    def test_comparison_chart_accepts_dicts_and_tuples(self, temp_output_dir):
        gen = DiagramGenerator()
        a = gen.generate_comparison_chart(
            "Dicts", [{"label": "A", "value": 3}], os.path.join(temp_output_dir, "a.png")
        )
        b = gen.generate_comparison_chart(
            "Tuples", [("A", 3), ("B", 5)], os.path.join(temp_output_dir, "b.png")
        )
        assert os.path.exists(a) and os.path.exists(b)

    @pytest.mark.slow
    def test_diagram_generator_flowchart(self, temp_output_dir):
        output = os.path.join(temp_output_dir, "flow.png")
        DiagramGenerator().generate_installation_flow(output)
        _assert_frame(output)

    @pytest.mark.slow
    def test_concept_card(self, temp_output_dir):
        output = os.path.join(temp_output_dir, "card.png")
        DiagramGenerator().generate_concept_card("Variables", "Boxes that hold values", output)
        _assert_frame(output)


@pytest.mark.unit
class TestSlideGenerator:
    def test_slide_generator_title(self, temp_output_dir):
        path = os.path.join(temp_output_dir, "title.png")
        SlideGenerator().create_title_slide("Python Basics", 1, "What is Python?", "Sub", path)
        _assert_frame(path)

    def test_content_slide_many_long_bullets(self, temp_output_dir):
        path = os.path.join(temp_output_dir, "content.png")
        SlideGenerator().create_content_slide("Title", ["word " * 60] * 10, path)
        _assert_frame(path)

    def test_closing_slide(self, temp_output_dir):
        path = os.path.join(temp_output_dir, "closing.png")
        SlideGenerator().create_closing_slide(["One", "Two"], "", path)
        _assert_frame(path)


@pytest.mark.unit
class TestAdvancedVideoGenerator:
    def test_generator_initializes(self):
        gen = AdvancedVideoGenerator()
        assert gen.width == 1280
        assert gen.height == 720

    def test_build_timeline_matches_audio_length(self, temp_output_dir, sample_script_json):
        gen = AdvancedVideoGenerator()
        gen.images_dir = temp_output_dir
        timeline = gen.build_timeline(sample_script_json, 120.0)

        assert sum(duration for _, duration in timeline) == pytest.approx(120.0)
        assert all(duration > 0 for _, duration in timeline)
        assert all(os.path.exists(path) for path, _ in timeline)
        names = [os.path.basename(path) for path, _ in timeline]
        assert names[0] == "title_01.png"
        assert names[-1] == "closing_01.png"
        assert any(n.startswith("code_s00_b00_") for n in names)
        assert any(n.startswith("diagram_python_vs_languages") for n in names)
        assert any(n.startswith("diagram_installation_flow") for n in names)

    def test_build_timeline_without_animation(
        self, temp_output_dir, sample_script_json, monkeypatch
    ):
        monkeypatch.setattr(config, "CODE_ANIMATION_ENABLED", False)
        gen = AdvancedVideoGenerator()
        gen.images_dir = temp_output_dir
        timeline = gen.build_timeline(sample_script_json, 60.0)
        names = [os.path.basename(path) for path, _ in timeline]
        assert "code_s00_b00.png" in names

    def test_generate_diagram_handles_strings_and_errors(self, temp_output_dir):
        gen = AdvancedVideoGenerator()
        gen.images_dir = temp_output_dir
        assert gen._generate_diagram("variable_boxes").endswith(".png")
        flow = {"name": "loop", "type": "flowchart", "steps": ["a", "b", "c", "d", "e"]}
        assert gen._generate_diagram(flow) is not None
        with patch.object(gen.diagrams, "generate_concept_card", side_effect=RuntimeError):
            assert gen._generate_diagram({"name": "broken"}) is None

    def test_generate_episode_video_wires_stages(self, sample_script_path, temp_output_dir):
        gen = AdvancedVideoGenerator()
        with patch.object(gen, "_get_audio_duration", return_value=30.0), patch.object(
            gen, "_assemble_video", return_value="out.mp4"
        ) as assemble:
            result = gen.generate_episode_video(
                sample_script_path, "audio.mp3", "out.mp4", images_dir=temp_output_dir
            )
        assert result == "out.mp4"
        plan, audio, output = assemble.call_args.args
        assert audio == "audio.mp3" and output == "out.mp4"
        assert sum(d for _, d in plan) == pytest.approx(30.0)
