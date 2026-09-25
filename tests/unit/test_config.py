"""Unit tests for config.py."""

import os

import pytest

import config


@pytest.mark.unit
class TestConfigBasics:
    def test_series_definition_exists(self):
        assert "python_basics" in config.SERIES

    def test_python_basics_series_has_episodes(self):
        series = config.SERIES["python_basics"]
        assert "episodes" in series
        assert len(series["episodes"]) >= 10

    def test_episode_1_specifications(self):
        episode = config.SERIES["python_basics"]["episodes"][0]
        assert episode["episode"] == 1
        assert episode["title"] == "What is Python?"
        assert episode["duration_seconds"] > 0
        assert "topics" in episode
        assert "code_examples" in episode
        assert "diagrams" in episode

    def test_episode_numbers_are_sequential(self):
        numbers = [ep["episode"] for ep in config.SERIES["python_basics"]["episodes"]]
        assert numbers == list(range(1, len(numbers) + 1))

    @pytest.mark.parametrize("episode", config.SERIES["python_basics"]["episodes"])
    def test_every_episode_is_complete(self, episode):
        for key in ("title", "subtitle", "duration_seconds", "topics", "code_examples"):
            assert episode[key]
        for example in episode["code_examples"]:
            compile(example["code"], "<example>", "exec")  # valid Python

    def test_get_episode(self):
        assert config.get_episode("python_basics", 2)["title"] == "Variables and Data Types"

    def test_get_episode_invalid_number(self):
        with pytest.raises(ValueError):
            config.get_episode("python_basics", 99)

    def test_get_series_invalid(self):
        with pytest.raises(ValueError):
            config.get_series("nope")


@pytest.mark.unit
class TestConfigPaths:
    def test_output_directories_defined(self):
        for path in (
            config.SCRIPTS_DIR,
            config.VOICEOVERS_DIR,
            config.IMAGES_DIR,
            config.VIDEOS_DIR,
            config.LOGS_DIR,
        ):
            assert path.startswith(config.OUTPUT_DIR)

    def test_ensure_output_dirs(self, config_with_mocks):
        config.ensure_output_dirs()
        for sub in ("scripts", "voiceovers", "images", "videos", "logs"):
            assert os.path.isdir(os.path.join(config_with_mocks, sub))

    def test_api_keys_loaded_from_env(self, mock_env):
        assert config.get_anthropic_api_key() == "test-key-123"
        assert config.get_elevenlabs_api_key() == "test-key-456"

    def test_api_keys_missing(self, no_api_keys):
        assert config.get_anthropic_api_key() is None
        assert config.get_elevenlabs_api_key() is None


@pytest.mark.unit
class TestConfigVideoSettings:
    def test_video_dimensions(self):
        assert config.VIDEO_WIDTH >= 1280
        assert config.VIDEO_HEIGHT >= 720

    def test_video_fps(self):
        assert config.VIDEO_FPS in [24, 25, 30, 50, 60]

    def test_code_animation_settings(self):
        assert config.CODE_ANIMATION_ENABLED in [True, False]
        assert config.CODE_TYPING_SPEED > 0

    def test_elevenlabs_settings(self):
        assert config.ELEVENLABS_VOICE_ID
        assert 0 <= config.ELEVENLABS_STABILITY <= 1
        assert 0 <= config.ELEVENLABS_SIMILARITY_BOOST <= 1
