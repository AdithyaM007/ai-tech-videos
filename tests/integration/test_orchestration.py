"""Integration tests for the EpisodeGenerator orchestrator."""

import os
from unittest.mock import patch

import pytest

import config
from generate_episode import ConfigurationError, EpisodeGenerator, VoiceoverError, main
from tests.fixtures.mock_responses import FAKE_MP3_BYTES, make_http_response


@pytest.mark.integration
class TestEpisodeGeneratorWorkflow:
    def test_episode_generator_init(self, mock_env):
        gen = EpisodeGenerator()
        assert gen.series_name == "python_basics"
        assert gen.series["title"] == "Python Basics"

    def test_invalid_series(self):
        with pytest.raises(ValueError):
            EpisodeGenerator("unknown_series")

    def test_episode_generation_workflow(self, mock_env, config_with_mocks):
        with patch.object(EpisodeGenerator, "_generate_script") as mock_script, patch.object(
            EpisodeGenerator, "_generate_voiceover"
        ) as mock_audio, patch.object(EpisodeGenerator, "_generate_video") as mock_video:
            mock_script.return_value = "/path/to/script.json"
            mock_audio.return_value = "/path/to/audio.mp3"
            mock_video.return_value = "/path/to/video.mp4"

            assert EpisodeGenerator().generate_episode(1) is True

            mock_script.assert_called_once_with(1)
            mock_audio.assert_called_once_with("/path/to/script.json", None)
            mock_video.assert_called_once_with("/path/to/script.json", "/path/to/audio.mp3", 1)

    def test_error_handling_missing_api_key(self, no_api_keys, config_with_mocks):
        gen = EpisodeGenerator()
        with pytest.raises(ConfigurationError, match="ANTHROPIC_API_KEY"):
            gen.check_configuration()
        with patch.object(EpisodeGenerator, "_generate_script") as mock_script:
            assert gen.generate_episode(1) is False
            mock_script.assert_not_called()

    def test_error_handling_invalid_episode(self, mock_env, config_with_mocks):
        with patch.object(EpisodeGenerator, "_generate_script") as mock_script:
            assert EpisodeGenerator().generate_episode(99) is False
            mock_script.assert_not_called()

    def test_stage_failure_returns_false(self, mock_env, config_with_mocks):
        with patch.object(EpisodeGenerator, "_generate_script", side_effect=RuntimeError("boom")):
            with patch.object(EpisodeGenerator, "_generate_voiceover") as mock_audio:
                assert EpisodeGenerator().generate_episode(1) is False
                mock_audio.assert_not_called()

    def test_generate_all(self, mock_env):
        with patch.object(EpisodeGenerator, "generate_episode", side_effect=[True, False]):
            assert EpisodeGenerator().generate_all([1, 2]) == {1: True, 2: False}


@pytest.mark.integration
class TestVoiceover:
    def test_voiceover_written(self, mock_env, config_with_mocks, sample_script_path):
        with patch("generate_episode.requests.post", return_value=make_http_response()) as post:
            path = EpisodeGenerator()._generate_voiceover(sample_script_path)

        assert os.path.dirname(path) == config.VOICEOVERS_DIR
        assert os.path.basename(path).startswith("ep01_")
        with open(path, "rb") as f:
            assert f.read() == FAKE_MP3_BYTES
        kwargs = post.call_args.kwargs
        assert kwargs["headers"]["xi-api-key"] == "test-key-456"
        assert kwargs["json"]["model_id"] == config.ELEVENLABS_MODEL
        assert kwargs["json"]["voice_settings"]["stability"] == 0.5
        assert kwargs["timeout"] > 0
        assert config.ELEVENLABS_VOICE_ID in post.call_args.args[0]

    def test_long_narration_is_chunked(
        self, mock_env, config_with_mocks, sample_script_json, monkeypatch
    ):
        monkeypatch.setattr(config, "ELEVENLABS_MAX_CHARS", 120)
        with patch("generate_episode.requests.post", return_value=make_http_response()) as post:
            path = EpisodeGenerator()._generate_voiceover("unused", sample_script_json)
        assert post.call_count > 1
        assert all(len(c.kwargs["json"]["text"]) <= 120 for c in post.call_args_list)
        assert os.path.getsize(path) == len(FAKE_MP3_BYTES) * post.call_count

    def test_api_error_raises(self, mock_env, config_with_mocks, sample_script_json):
        with patch(
            "generate_episode.requests.post",
            return_value=make_http_response(401, b'{"detail":"invalid key"}'),
        ):
            with pytest.raises(VoiceoverError, match="401"):
                EpisodeGenerator()._generate_voiceover("unused", sample_script_json)

    def test_missing_key_raises(self, no_api_keys, sample_script_json):
        with pytest.raises(ConfigurationError):
            EpisodeGenerator()._generate_voiceover("unused", sample_script_json)

    def test_empty_narration_raises(self, mock_env):
        with pytest.raises(VoiceoverError):
            EpisodeGenerator()._generate_voiceover("unused", {"sections": []})


@pytest.mark.integration
class TestCli:
    def test_list(self, capsys):
        assert main(["--list"]) == 0
        assert "What is Python?" in capsys.readouterr().out

    def test_single_episode(self, config_with_mocks):
        with patch.object(EpisodeGenerator, "generate_episode", return_value=True) as gen:
            assert main(["--episode", "3"]) == 0
        gen.assert_called_once_with(3)

    def test_all_with_failure(self, config_with_mocks):
        with patch.object(EpisodeGenerator, "generate_all", return_value={1: True, 2: False}):
            assert main(["--all"]) == 1
