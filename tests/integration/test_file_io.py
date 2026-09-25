"""Integration tests exercising real file I/O with mocked APIs."""

import json
import os
from unittest.mock import patch

import pytest

import config
from generate_episode import EpisodeGenerator
from script_generator import PythonBasicsScriptGenerator, load_script
from tests.fixtures.mock_responses import (
    CLAUDE_RESPONSE_WITH_PREAMBLE,
    make_http_response,
    make_streaming_client,
)


@pytest.mark.integration
class TestFileIO:
    def test_script_json_roundtrip(self, config_with_mocks, sample_script_json):
        gen = PythonBasicsScriptGenerator()
        path = gen._save_script("python_basics", 1, sample_script_json)
        assert load_script(path) == sample_script_json

    def test_script_saved_as_utf8(self, config_with_mocks):
        path = PythonBasicsScriptGenerator()._save_script("python_basics", 1, {"hook": "Olá ✓"})
        with open(path, encoding="utf-8") as f:
            assert "Olá ✓" in f.read()

    def test_pipeline_to_video_stage(self, mock_env, config_with_mocks):
        """Script + voiceover for real (mocked APIs); video assembly mocked."""
        gen = EpisodeGenerator()
        gen.script_generator = PythonBasicsScriptGenerator(
            client=make_streaming_client(CLAUDE_RESPONSE_WITH_PREAMBLE)
        )
        with patch(
            "generate_episode.requests.post", return_value=make_http_response()
        ), patch.object(
            gen.video_generator, "_get_audio_duration", return_value=60.0
        ), patch.object(
            gen.video_generator, "_assemble_video"
        ) as assemble:
            assemble.side_effect = lambda plan, audio, out: out
            assert gen.generate_episode(1) is True

        scripts = os.listdir(config.SCRIPTS_DIR)
        voiceovers = os.listdir(config.VOICEOVERS_DIR)
        assert len(scripts) == 1 and scripts[0].startswith("python_basics_ep01_")
        assert len(voiceovers) == 1 and voiceovers[0].endswith(".mp3")

        plan, audio_path, output_path = assemble.call_args.args
        assert output_path == os.path.join(config.VIDEOS_DIR, "python_basics_ep01.mp4")
        assert audio_path == os.path.join(config.VOICEOVERS_DIR, voiceovers[0])
        images = os.listdir(os.path.join(config.IMAGES_DIR, "ep01"))
        assert "title_01.png" in images and "closing_01.png" in images
        assert all(os.path.exists(path) for path, _ in plan)

        with open(os.path.join(config.SCRIPTS_DIR, scripts[0]), encoding="utf-8") as f:
            assert json.load(f)["model"] == gen.script_generator.model
