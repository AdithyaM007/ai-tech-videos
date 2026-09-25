"""Integration tests for the EpisodeGenerator orchestrator."""

import json
import os
from unittest.mock import MagicMock, patch

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
        gen.assert_called_once_with(3, upload=False, privacy=None, publish_at=None, reupload=False)

    def test_all_with_failure(self, config_with_mocks):
        with patch.object(EpisodeGenerator, "generate_all", return_value={1: True, 2: False}):
            assert main(["--all"]) == 1


@pytest.mark.integration
class TestYouTubeUpload:
    @pytest.fixture
    def youtube_ready(self, config_with_mocks, monkeypatch):
        secrets = os.path.join(config_with_mocks, "client.json")
        open(secrets, "w").close()
        monkeypatch.setattr(config, "YOUTUBE_CREDENTIALS_FILE", secrets)
        monkeypatch.setattr(config, "YOUTUBE_TOKEN_FILE", os.path.join(config_with_mocks, "t"))
        return config_with_mocks

    def _write_generated_episode(self, sample_script_json):
        os.makedirs(config.SCRIPTS_DIR, exist_ok=True)
        os.makedirs(config.VIDEOS_DIR, exist_ok=True)
        script_path = os.path.join(config.SCRIPTS_DIR, "python_basics_ep01_20260101_000000.json")
        with open(script_path, "w", encoding="utf-8") as f:
            json.dump(sample_script_json, f)
        video_path = os.path.join(config.VIDEOS_DIR, "python_basics_ep01.mp4")
        open(video_path, "wb").close()
        return script_path, video_path

    def test_generate_with_upload(self, mock_env, youtube_ready):
        with patch.object(
            EpisodeGenerator, "_generate_script", return_value="s.json"
        ), patch.object(
            EpisodeGenerator, "_generate_voiceover", return_value="a.mp3"
        ), patch.object(
            EpisodeGenerator, "_generate_video", return_value="v.mp4"
        ), patch.object(
            EpisodeGenerator, "_upload_video"
        ) as upload:
            assert EpisodeGenerator().generate_episode(1, upload=True, privacy="unlisted") is True
        upload.assert_called_once_with("s.json", "v.mp4", 1, "unlisted", None)

    def test_upload_requires_youtube_credentials(self, mock_env, config_with_mocks, monkeypatch):
        monkeypatch.setattr(config, "YOUTUBE_CREDENTIALS_FILE", "/nope/client.json")
        monkeypatch.setattr(config, "YOUTUBE_TOKEN_FILE", "/nope/token.json")
        with patch.object(EpisodeGenerator, "_generate_script") as script:
            assert EpisodeGenerator().generate_episode(1, upload=True) is False
        script.assert_not_called()

    def test_already_uploaded_is_skipped(self, mock_env, youtube_ready):
        os.makedirs(config.UPLOADS_DIR)
        with open(os.path.join(config.UPLOADS_DIR, "python_basics_ep01.json"), "w") as f:
            json.dump({"url": "https://youtu.be/x"}, f)
        with patch.object(EpisodeGenerator, "_generate_script") as script:
            assert EpisodeGenerator().generate_episode(1, upload=True) is True
            assert EpisodeGenerator().upload_existing(1) is True
        script.assert_not_called()

    def test_upload_video_stage(self, youtube_ready, sample_script_json):
        script_path, video_path = self._write_generated_episode(sample_script_json)
        gen = EpisodeGenerator()
        gen._uploader = MagicMock()
        gen._uploader.upload_episode.return_value = {"privacy": "private", "url": "u"}
        with patch.object(gen.video_generator, "_get_audio_duration", return_value=600.0):
            assert gen._upload_video(script_path, video_path, 1, "public", None) == "u"
        kwargs = gen._uploader.upload_episode.call_args.kwargs
        assert kwargs["privacy"] == "public"
        assert kwargs["chapters"][0] == ("Introduction", 0.0)
        assert kwargs["thumbnail_path"].endswith(os.path.join("ep01", "title_01.png"))

    def test_upload_existing(self, youtube_ready, sample_script_json):
        script_path, video_path = self._write_generated_episode(sample_script_json)
        with patch.object(EpisodeGenerator, "_upload_video") as upload:
            assert EpisodeGenerator().upload_existing(1, privacy="public") is True
        upload.assert_called_once_with(script_path, video_path, 1, "public", None)

    def test_upload_existing_not_generated(self, youtube_ready):
        assert EpisodeGenerator().upload_existing(1) is False

    def test_uploader_created_lazily(self):
        gen = EpisodeGenerator()
        assert gen.uploader is gen.uploader


@pytest.mark.integration
class TestUploadCli:
    def test_upload_only_all(self, config_with_mocks):
        with patch.object(EpisodeGenerator, "upload_existing", return_value=True) as up:
            assert main(["--all", "--upload-only", "--privacy", "unlisted"]) == 0
        assert up.call_count == len(config.SERIES["python_basics"]["episodes"])
        assert up.call_args.kwargs["privacy"] == "unlisted"

    def test_generate_all_with_upload(self, config_with_mocks):
        with patch.object(EpisodeGenerator, "generate_all", return_value={1: True}) as gen:
            assert main(["--all", "--upload"]) == 0
        assert gen.call_args.kwargs["upload"] is True

    def test_publish_at_converted_to_utc(self, config_with_mocks):
        with patch.object(EpisodeGenerator, "generate_episode", return_value=True) as gen:
            main(["-e", "1", "--upload", "--publish-at", "2099-01-01T05:30:00+05:30"])
        assert gen.call_args.kwargs["publish_at"] == "2099-01-01T00:00:00Z"

    @pytest.mark.parametrize("value", ["not-a-date", "2099-01-01T00:00:00", "2000-01-01T00:00:00Z"])
    def test_publish_at_rejected(self, value):
        with pytest.raises(SystemExit):
            main(["--upload", "--publish-at", value])

    def test_publish_at_with_all_rejected(self, config_with_mocks):
        with pytest.raises(SystemExit):
            main(["--all", "--upload", "--publish-at", "2099-01-01T00:00:00Z"])

    def test_list_shows_uploaded(self, config_with_mocks, capsys):
        os.makedirs(config.UPLOADS_DIR)
        with open(os.path.join(config.UPLOADS_DIR, "python_basics_ep01.json"), "w") as f:
            json.dump({"url": "https://youtu.be/x"}, f)
        main(["--list"])
        assert "[uploaded: https://youtu.be/x]" in capsys.readouterr().out
