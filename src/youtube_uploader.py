"""Stage 4: upload a finished episode to YouTube and add it to the series playlist."""

from __future__ import annotations

import glob
import json
import logging
import os
import random
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import config

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
]
PRIVACY_OPTIONS = ("private", "unlisted", "public")
RETRYABLE_STATUS = {500, 502, 503, 504}
MAX_RETRIES = 8
CHUNK_SIZE = 8 * 1024 * 1024
TITLE_LIMIT = 100
DESCRIPTION_LIMIT = 5000


class UploadError(RuntimeError):
    """Raised when a YouTube upload cannot be completed."""


def format_timestamp(seconds: float) -> str:
    """``75`` -> ``"1:15"``, ``3725`` -> ``"1:02:05"``."""
    total = int(seconds)
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


def build_metadata(
    script: Dict[str, Any],
    series: Dict[str, Any],
    chapters: Optional[Sequence[Tuple[str, float]]] = None,
) -> Dict[str, Any]:
    """Build the YouTube title, description and tags for an episode."""
    episode = script.get("episode", "")
    episode_title = script.get("episode_title", "")
    series_title = series.get("title", "Python Basics")

    title = f"{series_title} #{episode}: {episode_title} | Python for Beginners"
    if len(title) > TITLE_LIMIT:
        title = f"{series_title} #{episode}: {episode_title}"[:TITLE_LIMIT]

    lines: List[str] = [str(script.get("hook", "")).strip(), ""]
    if series.get("description"):
        lines += [f"Episode {episode} of {series_title}: {series['description']}", ""]

    learnings = script.get("key_learnings") or []
    if learnings:
        lines.append("In this episode you'll learn:")
        lines += [f"✅ {item}" for item in learnings]
        lines.append("")

    # YouTube only shows chapters when there are 3+, starting at 0:00.
    if chapters and len(chapters) >= 3:
        lines.append("Chapters:")
        lines += [f"{format_timestamp(start)} {name}" for name, start in chapters]
        lines.append("")

    next_episode = _find_episode(series, _as_int(episode) + 1)
    if next_episode:
        lines += [f"Next episode: {next_episode['title']}", ""]
    lines.append(
        f"Subscribe for the whole series: https://www.youtube.com/{config.YOUTUBE_CHANNEL_HANDLE}"
    )
    lines += ["", "#python #learnpython #programming"]

    description = "\n".join(lines).replace("<", "‹").replace(">", "›")  # < > are rejected
    tags = list(dict.fromkeys(config.YOUTUBE_TAGS + [series_title.lower(), episode_title.lower()]))
    return {
        "title": title,
        "description": description[:DESCRIPTION_LIMIT],
        "tags": [tag for tag in tags if tag],
    }


def _find_episode(series: Dict[str, Any], number: int) -> Optional[Dict[str, Any]]:
    for episode in series.get("episodes", []):
        if episode.get("episode") == number:
            return dict(episode)
    return None


def _as_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def record_path(series_name: str, episode_number: int) -> str:
    """Where the upload record for an episode is stored."""
    return os.path.join(config.UPLOADS_DIR, f"{series_name}_ep{episode_number:02d}.json")


def load_upload_record(series_name: str, episode_number: int) -> Optional[Dict[str, Any]]:
    """Return the saved upload record for an episode, if it was uploaded before."""
    path = record_path(series_name, episode_number)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        data: Dict[str, Any] = json.load(f)
    return data


def find_latest_script(series_name: str, episode_number: int) -> Optional[str]:
    """Most recent saved script for an episode (``None`` if there is none)."""
    pattern = os.path.join(config.SCRIPTS_DIR, f"{series_name}_ep{episode_number:02d}_*.json")
    matches = sorted(glob.glob(pattern))
    return matches[-1] if matches else None


class YouTubeUploader:
    """Uploads videos with the YouTube Data API v3 (OAuth 2.0 installed-app flow)."""

    def __init__(
        self,
        credentials_file: Optional[str] = None,
        token_file: Optional[str] = None,
        service: Any = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.credentials_file = credentials_file or config.YOUTUBE_CREDENTIALS_FILE
        self.token_file = token_file or config.YOUTUBE_TOKEN_FILE
        self._service = service
        self._sleep = sleep

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------
    @property
    def service(self) -> Any:
        """Authenticated YouTube API client (created on first use)."""
        if self._service is None:
            from googleapiclient.discovery import build

            self._service = build("youtube", "v3", credentials=self._load_credentials())
        return self._service

    def _load_credentials(self) -> Any:
        """Load the saved token, refreshing it or running the browser sign-in."""
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow

        creds = None
        if os.path.exists(self.token_file):
            creds = Credentials.from_authorized_user_file(self.token_file, SCOPES)

        if creds and creds.valid and creds.has_scopes(SCOPES):
            return creds
        if creds and creds.expired and creds.refresh_token and creds.has_scopes(SCOPES):
            try:
                creds.refresh(Request())
            except Exception:  # revoked or expired refresh token -> sign in again
                logger.warning("Saved YouTube token could not be refreshed; signing in again")
                creds = None
        else:
            creds = None

        if creds is None:
            if not os.path.exists(self.credentials_file):
                raise UploadError(
                    f"YouTube OAuth client file not found: {self.credentials_file}. "
                    "See docs/YOUTUBE.md for how to create it."
                )
            flow = InstalledAppFlow.from_client_secrets_file(self.credentials_file, SCOPES)
            logger.info("Opening a browser to sign in to YouTube...")
            creds = flow.run_local_server(port=0)

        with open(self.token_file, "w", encoding="utf-8") as f:
            f.write(creds.to_json())
        return creds

    # ------------------------------------------------------------------
    # Upload
    # ------------------------------------------------------------------
    def upload_video(
        self,
        video_path: str,
        metadata: Dict[str, Any],
        privacy: str = "private",
        publish_at: Optional[str] = None,
    ) -> str:
        """Upload ``video_path`` (resumable) and return the new video ID.

        ``publish_at`` is an ISO 8601 UTC time; the video stays private until
        then and YouTube publishes it automatically.
        """
        from googleapiclient.errors import HttpError
        from googleapiclient.http import MediaFileUpload

        if privacy not in PRIVACY_OPTIONS:
            raise ValueError(f"privacy must be one of {PRIVACY_OPTIONS}")
        if not os.path.exists(video_path):
            raise UploadError(f"Video file not found: {video_path}")

        status: Dict[str, Any] = {
            "privacyStatus": "private" if publish_at else privacy,
            "selfDeclaredMadeForKids": False,
            "containsSyntheticMedia": config.YOUTUBE_CONTAINS_SYNTHETIC_MEDIA,
        }
        if publish_at:
            status["publishAt"] = publish_at
        body = {
            "snippet": {
                "title": metadata["title"],
                "description": metadata["description"],
                "tags": metadata.get("tags", []),
                "categoryId": config.YOUTUBE_CATEGORY_ID,
                "defaultLanguage": "en",
                "defaultAudioLanguage": "en",
            },
            "status": status,
        }
        media = MediaFileUpload(
            video_path, mimetype="video/mp4", chunksize=CHUNK_SIZE, resumable=True
        )
        request = self.service.videos().insert(part="snippet,status", body=body, media_body=media)

        logger.info("Uploading %s (%s)", os.path.basename(video_path), status["privacyStatus"])
        response = None
        retries = 0
        while response is None:
            try:
                progress, response = request.next_chunk()
                if progress is not None:
                    logger.info("  upload %d%%", int(progress.progress() * 100))
                retries = 0
            except HttpError as error:
                if error.resp.status not in RETRYABLE_STATUS:
                    raise UploadError(f"YouTube rejected the upload: {error}") from error
                retries = self._backoff(retries, error)
            except (ConnectionError, TimeoutError, OSError) as error:
                retries = self._backoff(retries, error)

        if "id" not in response:
            raise UploadError(f"Unexpected upload response: {response}")
        logger.info("Uploaded: https://youtu.be/%s", response["id"])
        return str(response["id"])

    def _backoff(self, retries: int, error: Exception) -> int:
        retries += 1
        if retries > MAX_RETRIES:
            raise UploadError(f"Upload failed after {MAX_RETRIES} retries: {error}") from error
        delay = min(2**retries, 64) + random.random()  # nosec B311
        logger.warning("Upload error (%s); retry %d in %.0fs", error, retries, delay)
        self._sleep(delay)
        return retries

    def set_thumbnail(self, video_id: str, image_path: str) -> bool:
        """Set a custom thumbnail. Returns ``False`` if YouTube refuses it.

        Custom thumbnails need a phone-verified channel, so failure is not fatal.
        """
        from googleapiclient.errors import HttpError
        from googleapiclient.http import MediaFileUpload

        if not os.path.exists(image_path):
            return False
        try:
            self.service.thumbnails().set(
                videoId=video_id, media_body=MediaFileUpload(image_path)
            ).execute()
            return True
        except HttpError as error:
            logger.warning("Could not set thumbnail (is the channel verified?): %s", error)
            return False

    # ------------------------------------------------------------------
    # Playlists
    # ------------------------------------------------------------------
    def get_or_create_playlist(self, title: str, description: str = "") -> str:
        """Return the ID of the channel's playlist called ``title``, creating it if needed."""
        page_token = None
        while True:
            response = (
                self.service.playlists()
                .list(part="snippet", mine=True, maxResults=50, pageToken=page_token)
                .execute()
            )
            for item in response.get("items", []):
                if item["snippet"]["title"] == title:
                    return str(item["id"])
            page_token = response.get("nextPageToken")
            if not page_token:
                break

        created = (
            self.service.playlists()
            .insert(
                part="snippet,status",
                body={
                    "snippet": {"title": title, "description": description},
                    "status": {"privacyStatus": config.YOUTUBE_PLAYLIST_PRIVACY},
                },
            )
            .execute()
        )
        logger.info("Created playlist %r", title)
        return str(created["id"])

    def add_to_playlist(self, playlist_id: str, video_id: str) -> None:
        """Append a video to a playlist."""
        self.service.playlistItems().insert(
            part="snippet",
            body={
                "snippet": {
                    "playlistId": playlist_id,
                    "resourceId": {"kind": "youtube#video", "videoId": video_id},
                }
            },
        ).execute()

    # ------------------------------------------------------------------
    # High level
    # ------------------------------------------------------------------
    def upload_episode(
        self,
        series_name: str,
        script: Dict[str, Any],
        video_path: str,
        chapters: Optional[Sequence[Tuple[str, float]]] = None,
        thumbnail_path: Optional[str] = None,
        privacy: Optional[str] = None,
        publish_at: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Upload an episode, set its thumbnail, add it to the series playlist
        and save an upload record. Returns the record."""
        series = config.get_series(series_name)
        episode_number = _as_int(script.get("episode"))
        metadata = build_metadata(script, series, chapters)
        video_id = self.upload_video(
            video_path, metadata, privacy or config.YOUTUBE_PRIVACY, publish_at
        )

        thumbnail_set = self.set_thumbnail(video_id, thumbnail_path) if thumbnail_path else False
        playlist_id = None
        try:
            playlist_id = self.get_or_create_playlist(
                series.get("title", series_name), series.get("description", "")
            )
            self.add_to_playlist(playlist_id, video_id)
        except Exception as error:  # the video is up; a playlist problem shouldn't hide that
            logger.warning("Could not add video to playlist: %s", error)

        record = {
            "series": series_name,
            "episode": episode_number,
            "video_id": video_id,
            "url": f"https://youtu.be/{video_id}",
            "title": metadata["title"],
            "privacy": "private" if publish_at else (privacy or config.YOUTUBE_PRIVACY),
            "publish_at": publish_at,
            "playlist_id": playlist_id,
            "thumbnail_set": thumbnail_set,
            "uploaded_at": datetime.now().isoformat(timespec="seconds"),
        }
        os.makedirs(config.UPLOADS_DIR, exist_ok=True)
        with open(record_path(series_name, episode_number), "w", encoding="utf-8") as f:
            json.dump(record, f, indent=2)
        return record
