"""Unit tests for youtube_uploader.py."""

import json
import os
from unittest.mock import MagicMock, patch

import pytest

import config
from tests.fixtures.youtube_mocks import http_error, make_youtube_service
from video_generator import compute_chapters
from youtube_uploader import (
    UploadError,
    YouTubeUploader,
    build_metadata,
    find_latest_script,
    format_timestamp,
    load_upload_record,
)

SERIES = config.SERIES["python_basics"]


@pytest.fixture
def video_file(temp_output_dir):
    path = os.path.join(temp_output_dir, "video.mp4")
    with open(path, "wb") as f:
        f.write(b"\x00" * 1024)
    return path


def _uploader(service):
    return YouTubeUploader(service=service, sleep=lambda _: None)


@pytest.mark.unit
class TestMetadata:
    def test_format_timestamp(self):
        assert format_timestamp(0) == "0:00"
        assert format_timestamp(75.9) == "1:15"
        assert format_timestamp(3725) == "1:02:05"

    def test_title_and_tags(self, sample_script_json):
        meta = build_metadata(sample_script_json, SERIES)
        assert meta["title"] == "Python Basics #1: What is Python? | Python for Beginners"
        assert len(meta["title"]) <= 100
        assert "python" in meta["tags"]
        assert len(meta["tags"]) == len(set(meta["tags"]))

    def test_long_title_truncated(self, sample_script_json):
        script = {**sample_script_json, "episode_title": "x" * 150}
        assert len(build_metadata(script, SERIES)["title"]) == 100

    def test_description_contents(self, sample_script_json):
        chapters = compute_chapters(sample_script_json, 600)
        description = build_metadata(sample_script_json, SERIES, chapters)["description"]
        assert sample_script_json["hook"] in description
        for item in sample_script_json["key_learnings"]:
            assert item in description
        assert "0:00 Introduction" in description
        assert "Why Python?" in description
        assert "Next episode: Variables and Data Types" in description
        assert config.YOUTUBE_CHANNEL_HANDLE in description

    def test_description_strips_angle_brackets_and_limits_length(self, sample_script_json):
        script = {**sample_script_json, "hook": "<b>" + "a" * 6000}
        description = build_metadata(script, SERIES)["description"]
        assert "<" not in description and ">" not in description
        assert len(description) <= 5000

    def test_no_chapters_when_fewer_than_three(self, sample_script_json):
        meta = build_metadata(sample_script_json, SERIES, [("A", 0), ("B", 30)])
        assert "Chapters:" not in meta["description"]

    def test_chapters_start_at_zero_and_increase(self, sample_script_json):
        chapters = compute_chapters(sample_script_json, 600)
        starts = [start for _, start in chapters]
        assert starts[0] == 0
        assert starts == sorted(starts)
        assert starts[-1] < 600
        assert [name for name, _ in chapters][1:-1] == [
            s["title"] for s in sample_script_json["sections"]
        ]


@pytest.mark.unit
class TestUploadVideo:
    def test_upload_returns_id_and_sends_metadata(self, video_file):
        service = make_youtube_service()
        video_id = _uploader(service).upload_video(
            video_file, {"title": "T", "description": "D", "tags": ["a"]}, privacy="unlisted"
        )
        assert video_id == "vid123"
        kwargs = service.videos.return_value.insert.call_args.kwargs
        assert kwargs["part"] == "snippet,status"
        assert kwargs["body"]["snippet"]["title"] == "T"
        assert kwargs["body"]["snippet"]["categoryId"] == "27"
        status = kwargs["body"]["status"]
        assert status["privacyStatus"] == "unlisted"
        assert status["selfDeclaredMadeForKids"] is False
        assert status["containsSyntheticMedia"] is True
        assert "publishAt" not in status

    def test_scheduled_upload_is_private(self, video_file):
        service = make_youtube_service()
        _uploader(service).upload_video(
            video_file, {"title": "T", "description": ""}, "public", "2030-01-01T00:00:00Z"
        )
        status = service.videos.return_value.insert.call_args.kwargs["body"]["status"]
        assert status == {**status, "privacyStatus": "private", "publishAt": "2030-01-01T00:00:00Z"}

    def test_invalid_privacy(self, video_file):
        with pytest.raises(ValueError):
            _uploader(make_youtube_service()).upload_video(video_file, {}, privacy="secret")

    def test_missing_file(self):
        with pytest.raises(UploadError):
            _uploader(make_youtube_service()).upload_video("nope.mp4", {"title": "T"})

    def test_retries_server_errors(self, video_file):
        service = make_youtube_service(
            chunk_results=[http_error(503), ConnectionError("reset"), (None, {"id": "ok"})]
        )
        sleeps = []
        uploader = YouTubeUploader(service=service, sleep=sleeps.append)
        assert uploader.upload_video(video_file, {"title": "T", "description": ""}) == "ok"
        assert len(sleeps) == 2

    def test_gives_up_after_max_retries(self, video_file):
        service = make_youtube_service(chunk_results=[http_error(500)] * 20)
        with pytest.raises(UploadError, match="retries"):
            _uploader(service).upload_video(video_file, {"title": "T", "description": ""})

    def test_client_error_not_retried(self, video_file):
        service = make_youtube_service(chunk_results=[http_error(403)])
        with pytest.raises(UploadError, match="rejected"):
            _uploader(service).upload_video(video_file, {"title": "T", "description": ""})

    def test_response_without_id(self, video_file):
        service = make_youtube_service(chunk_results=[(None, {"error": "?"})])
        with pytest.raises(UploadError, match="Unexpected"):
            _uploader(service).upload_video(video_file, {"title": "T", "description": ""})


@pytest.mark.unit
class TestThumbnailAndPlaylist:
    def test_set_thumbnail(self, video_file):
        service = make_youtube_service()
        assert _uploader(service).set_thumbnail("vid", video_file) is True
        assert service.thumbnails.return_value.set.call_args.kwargs["videoId"] == "vid"

    def test_thumbnail_refused(self, video_file):
        service = make_youtube_service(thumbnail_error=http_error(403))
        assert _uploader(service).set_thumbnail("vid", video_file) is False

    def test_thumbnail_missing_file(self):
        assert _uploader(make_youtube_service()).set_thumbnail("vid", "nope.png") is False

    def test_existing_playlist_reused(self):
        service = make_youtube_service(
            playlists=[{"id": "PL1", "snippet": {"title": "Python Basics"}}]
        )
        assert _uploader(service).get_or_create_playlist("Python Basics") == "PL1"
        service.playlists.return_value.insert.assert_not_called()

    def test_playlist_pagination_then_create(self):
        service = make_youtube_service()
        service.playlists.return_value.list.return_value.execute.side_effect = [
            {"items": [{"id": "PLx", "snippet": {"title": "Other"}}], "nextPageToken": "p2"},
            {"items": []},
        ]
        assert _uploader(service).get_or_create_playlist("Python Basics") == "PLnew"
        body = service.playlists.return_value.insert.call_args.kwargs["body"]
        assert body["snippet"]["title"] == "Python Basics"
        assert body["status"]["privacyStatus"] == config.YOUTUBE_PLAYLIST_PRIVACY

    def test_add_to_playlist(self):
        service = make_youtube_service()
        _uploader(service).add_to_playlist("PL1", "vid")
        body = service.playlistItems.return_value.insert.call_args.kwargs["body"]
        assert body["snippet"]["resourceId"]["videoId"] == "vid"


@pytest.mark.unit
class TestUploadEpisode:
    def test_upload_episode_saves_record(self, config_with_mocks, sample_script_json, video_file):
        service = make_youtube_service()
        record = _uploader(service).upload_episode(
            "python_basics", sample_script_json, video_file, thumbnail_path=video_file
        )
        assert record["url"] == "https://youtu.be/vid123"
        assert record["playlist_id"] == "PLnew"
        assert record["thumbnail_set"] is True
        assert record["privacy"] == config.YOUTUBE_PRIVACY
        assert load_upload_record("python_basics", 1) == record

    def test_playlist_failure_does_not_fail_upload(
        self, config_with_mocks, sample_script_json, video_file
    ):
        service = make_youtube_service()
        service.playlists.return_value.list.return_value.execute.side_effect = RuntimeError
        record = _uploader(service).upload_episode("python_basics", sample_script_json, video_file)
        assert record["video_id"] == "vid123"
        assert record["playlist_id"] is None

    def test_no_record(self, config_with_mocks):
        assert load_upload_record("python_basics", 1) is None

    def test_find_latest_script(self, config_with_mocks):
        os.makedirs(config.SCRIPTS_DIR)
        for stamp in ("20260101_000000", "20260202_000000"):
            with open(
                os.path.join(config.SCRIPTS_DIR, f"python_basics_ep01_{stamp}.json"), "w"
            ) as f:
                json.dump({}, f)
        assert find_latest_script("python_basics", 1).endswith("20260202_000000.json")
        assert find_latest_script("python_basics", 2) is None


@pytest.mark.unit
class TestCredentials:
    def _patches(self, creds=None, flow_creds=None):
        credentials_cls = MagicMock()
        credentials_cls.from_authorized_user_file.return_value = creds
        flow_cls = MagicMock()
        flow_cls.from_client_secrets_file.return_value.run_local_server.return_value = flow_creds
        return (
            patch("google.oauth2.credentials.Credentials", credentials_cls),
            patch("google_auth_oauthlib.flow.InstalledAppFlow", flow_cls),
            flow_cls,
        )

    def _creds(self, valid=True, expired=False, scopes=True):
        creds = MagicMock(valid=valid, expired=expired, refresh_token="r")
        creds.has_scopes.return_value = scopes
        creds.to_json.return_value = '{"token": "t"}'
        return creds

    def test_valid_saved_token(self, temp_output_dir):
        token = os.path.join(temp_output_dir, "token.json")
        open(token, "w").close()
        saved = self._creds()
        p1, p2, flow = self._patches(creds=saved)
        with p1, p2:
            assert YouTubeUploader("c.json", token)._load_credentials() is saved
        flow.from_client_secrets_file.assert_not_called()

    def test_expired_token_refreshed(self, temp_output_dir):
        token = os.path.join(temp_output_dir, "token.json")
        open(token, "w").close()
        saved = self._creds(valid=False, expired=True)
        p1, p2, flow = self._patches(creds=saved)
        with p1, p2:
            assert YouTubeUploader("c.json", token)._load_credentials() is saved
        saved.refresh.assert_called_once()
        flow.from_client_secrets_file.assert_not_called()

    def test_browser_sign_in_when_no_token(self, temp_output_dir):
        token = os.path.join(temp_output_dir, "token.json")
        secrets = os.path.join(temp_output_dir, "client.json")
        open(secrets, "w").close()
        new = self._creds()
        p1, p2, flow = self._patches(flow_creds=new)
        with p1, p2:
            assert YouTubeUploader(secrets, token)._load_credentials() is new
        flow.from_client_secrets_file.assert_called_once()
        with open(token) as f:
            assert f.read() == '{"token": "t"}'

    def test_failed_refresh_signs_in_again(self, temp_output_dir):
        token = os.path.join(temp_output_dir, "token.json")
        secrets = os.path.join(temp_output_dir, "client.json")
        open(token, "w").close()
        open(secrets, "w").close()
        saved = self._creds(valid=False, expired=True)
        saved.refresh.side_effect = Exception("revoked")
        new = self._creds()
        p1, p2, flow = self._patches(creds=saved, flow_creds=new)
        with p1, p2:
            assert YouTubeUploader(secrets, token)._load_credentials() is new

    def test_missing_client_file(self, temp_output_dir):
        p1, p2, _ = self._patches()
        with p1, p2, pytest.raises(UploadError, match="not found"):
            YouTubeUploader(
                os.path.join(temp_output_dir, "missing.json"),
                os.path.join(temp_output_dir, "token.json"),
            )._load_credentials()

    def test_service_built_lazily(self):
        uploader = YouTubeUploader()
        with patch.object(uploader, "_load_credentials", return_value="creds"), patch(
            "googleapiclient.discovery.build", return_value="svc"
        ) as build:
            assert uploader.service == "svc"
            assert uploader.service == "svc"
        build.assert_called_once_with("youtube", "v3", credentials="creds")
