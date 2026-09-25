"""Master orchestrator: Script -> Voiceover -> Video -> (optional) YouTube.

Usage::

    python src/generate_episode.py --episode 1
    python src/generate_episode.py --episode 1 --upload
    python src/generate_episode.py --episode 1 --upload-only --privacy unlisted
    python src/generate_episode.py --all
    python src/generate_episode.py --list
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

import requests

import config
from script_generator import PythonBasicsScriptGenerator, load_script
from video_generator import AdvancedVideoGenerator, compute_chapters
from youtube_uploader import (
    PRIVACY_OPTIONS,
    YouTubeUploader,
    find_latest_script,
    load_upload_record,
)

logger = logging.getLogger("generate_episode")


class ConfigurationError(RuntimeError):
    """Raised when required configuration (e.g. an API key) is missing."""


class VoiceoverError(RuntimeError):
    """Raised when ElevenLabs does not return audio."""


def build_narration(script: Dict[str, Any]) -> str:
    """Combine hook, intro, section scripts and outro into one narration."""
    parts: List[str] = [str(script.get("hook", "")), str(script.get("intro", ""))]
    for section in script.get("sections", []) or []:
        parts.append(str(section.get("script", "")))
    parts.append(str(script.get("outro", "")))
    return "\n\n".join(part.strip() for part in parts if part and part.strip())


def split_text(text: str, max_chars: int) -> List[str]:
    """Split ``text`` into chunks of at most ``max_chars`` on sentence boundaries."""
    if len(text) <= max_chars:
        return [text] if text else []
    sentences = re.split(r"(?<=[.!?])\s+", text)
    chunks: List[str] = []
    current = ""
    for sentence in sentences:
        while len(sentence) > max_chars:  # a single enormous "sentence"
            cut = sentence.rfind(" ", 0, max_chars)
            cut = cut if cut > 0 else max_chars
            if current:
                chunks.append(current)
                current = ""
            chunks.append(sentence[:cut].strip())
            sentence = sentence[cut:].strip()
        candidate = f"{current} {sentence}".strip() if current else sentence
        if len(candidate) > max_chars:
            chunks.append(current)
            current = sentence
        else:
            current = candidate
    if current:
        chunks.append(current)
    return [chunk for chunk in chunks if chunk]


class EpisodeGenerator:
    """Coordinates all three stages for one series."""

    def __init__(self, series_name: str = "python_basics") -> None:
        self.series_name = series_name
        self.series = config.get_series(series_name)
        self.script_generator = PythonBasicsScriptGenerator()
        self.video_generator = AdvancedVideoGenerator()
        self.current_script: Optional[Dict[str, Any]] = None
        self._uploader: Optional[YouTubeUploader] = None

    @property
    def uploader(self) -> YouTubeUploader:
        """YouTube uploader (created on first use)."""
        if self._uploader is None:
            self._uploader = YouTubeUploader()
        return self._uploader

    # ------------------------------------------------------------------
    # Workflow
    # ------------------------------------------------------------------
    def check_youtube_configuration(self) -> None:
        """Raise ``ConfigurationError`` if there is no way to sign in to YouTube."""
        if not (
            os.path.exists(config.YOUTUBE_CREDENTIALS_FILE)
            or os.path.exists(config.YOUTUBE_TOKEN_FILE)
        ):
            raise ConfigurationError(
                f"YouTube OAuth client file not found: {config.YOUTUBE_CREDENTIALS_FILE}. "
                "See docs/YOUTUBE.md."
            )

    def check_configuration(self, upload: bool = False) -> None:
        """Raise ``ConfigurationError`` if required API keys are missing."""
        if upload:
            self.check_youtube_configuration()
        missing = []
        if not config.get_anthropic_api_key():
            missing.append("ANTHROPIC_API_KEY")
        if not config.get_elevenlabs_api_key():
            missing.append("ELEVENLABS_API_KEY")
        if missing:
            raise ConfigurationError(
                f"Missing required environment variable(s): {', '.join(missing)}. "
                "Copy .env.example to .env and fill them in."
            )

    def generate_episode(
        self,
        episode_number: int,
        upload: bool = False,
        privacy: Optional[str] = None,
        publish_at: Optional[str] = None,
        reupload: bool = False,
    ) -> bool:
        """Run the full pipeline for one episode. Returns ``True`` on success.

        With ``upload=True`` the finished video is also uploaded to YouTube.
        Episodes that were already uploaded are skipped unless ``reupload``.
        """
        started = datetime.now()
        stages = 4 if upload else 3
        try:
            config.get_episode(self.series_name, episode_number)
            if upload and not reupload and self._already_uploaded(episode_number):
                return True
            self.check_configuration(upload=upload)
            config.ensure_output_dirs()

            logger.info("[1/%d] Generating script for episode %d", stages, episode_number)
            script_path = self._generate_script(episode_number)

            logger.info("[2/%d] Generating voiceover", stages)
            audio_path = self._generate_voiceover(script_path, self.current_script)

            logger.info("[3/%d] Assembling video", stages)
            video_path = self._generate_video(script_path, audio_path, episode_number)

            if upload:
                logger.info("[4/%d] Uploading to YouTube", stages)
                self._upload_video(script_path, video_path, episode_number, privacy, publish_at)
        except Exception as exc:
            logger.error("Episode %d failed: %s", episode_number, exc)
            logger.debug("Traceback", exc_info=True)
            return False

        elapsed = (datetime.now() - started).total_seconds()
        logger.info("Episode %d complete in %.0fs: %s", episode_number, elapsed, video_path)
        return True

    def upload_existing(
        self,
        episode_number: int,
        privacy: Optional[str] = None,
        publish_at: Optional[str] = None,
        reupload: bool = False,
    ) -> bool:
        """Upload an already generated episode (latest script + its video)."""
        try:
            config.get_episode(self.series_name, episode_number)
            if not reupload and self._already_uploaded(episode_number):
                return True
            self.check_youtube_configuration()
            script_path = find_latest_script(self.series_name, episode_number)
            video_path = self._video_path(episode_number)
            if not script_path or not os.path.exists(video_path):
                raise FileNotFoundError(
                    f"Episode {episode_number} has not been generated yet "
                    f"(need a script in {config.SCRIPTS_DIR} and {video_path})"
                )
            self._upload_video(script_path, video_path, episode_number, privacy, publish_at)
        except Exception as exc:
            logger.error("Upload of episode %d failed: %s", episode_number, exc)
            logger.debug("Traceback", exc_info=True)
            return False
        return True

    def generate_all(
        self, episodes: Optional[Sequence[int]] = None, **options: Any
    ) -> Dict[int, bool]:
        """Generate several episodes (all by default); return success per episode.

        ``options`` are passed to :meth:`generate_episode` (e.g. ``upload=True``).
        """
        numbers = list(episodes or [ep["episode"] for ep in self.series["episodes"]])
        return {number: self.generate_episode(number, **options) for number in numbers}

    # ------------------------------------------------------------------
    # Stages
    # ------------------------------------------------------------------
    def _generate_script(self, episode_number: int) -> str:
        """Stage 1: generate and save the script; return its path."""
        script = self.script_generator.generate_script(self.series_name, episode_number)
        self.current_script = script
        return self.script_generator._save_script(self.series_name, episode_number, script)

    def _generate_voiceover(
        self, script_path: str, script_data: Optional[Dict[str, Any]] = None
    ) -> str:
        """Stage 2: synthesize narration with ElevenLabs; return the MP3 path."""
        script = script_data if script_data is not None else load_script(script_path)
        narration = build_narration(script)
        if not narration:
            raise VoiceoverError("Script has no narration text")

        api_key = config.get_elevenlabs_api_key()
        if not api_key:
            raise ConfigurationError("ELEVENLABS_API_KEY is not set")

        url = config.ELEVENLABS_API_URL.format(voice_id=config.ELEVENLABS_VOICE_ID)
        headers = {
            "xi-api-key": api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        }
        chunks = split_text(narration, config.ELEVENLABS_MAX_CHARS)
        audio = bytearray()
        for index, chunk in enumerate(chunks, start=1):
            logger.info("  TTS chunk %d/%d (%d chars)", index, len(chunks), len(chunk))
            response = requests.post(
                url,
                headers=headers,
                json={
                    "text": chunk,
                    "model_id": config.ELEVENLABS_MODEL,
                    "voice_settings": {
                        "stability": config.ELEVENLABS_STABILITY,
                        "similarity_boost": config.ELEVENLABS_SIMILARITY_BOOST,
                    },
                },
                timeout=config.HTTP_TIMEOUT_SECONDS,
            )
            if response.status_code != 200:
                raise VoiceoverError(
                    f"ElevenLabs error {response.status_code}: {response.text[:300]}"
                )
            audio.extend(response.content)

        episode = script.get("episode", 0)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        os.makedirs(config.VOICEOVERS_DIR, exist_ok=True)
        path = os.path.join(config.VOICEOVERS_DIR, f"ep{int(episode or 0):02d}_{timestamp}.mp3")
        with open(path, "wb") as f:
            f.write(bytes(audio))
        logger.info("Saved voiceover to %s", path)
        return path

    def _video_path(self, episode_number: int) -> str:
        return os.path.join(config.VIDEOS_DIR, f"{self.series_name}_ep{episode_number:02d}.mp4")

    def _generate_video(self, script_path: str, audio_path: str, episode_number: int) -> str:
        """Stage 3: assemble the final MP4; return its path."""
        output_path = self._video_path(episode_number)
        return self.video_generator.generate_episode_video(script_path, audio_path, output_path)

    def _already_uploaded(self, episode_number: int) -> bool:
        record = load_upload_record(self.series_name, episode_number)
        if record:
            logger.info(
                "Episode %d is already on YouTube (%s); skipping. Use --reupload to upload again.",
                episode_number,
                record.get("url"),
            )
        return record is not None

    def _upload_video(
        self,
        script_path: str,
        video_path: str,
        episode_number: int,
        privacy: Optional[str] = None,
        publish_at: Optional[str] = None,
    ) -> str:
        """Stage 4: upload to YouTube with chapters and thumbnail; return the URL."""
        script = load_script(script_path)
        duration = self.video_generator._get_audio_duration(video_path)
        thumbnail = os.path.join(
            config.IMAGES_DIR, f"ep{episode_number:02d}", f"title_{episode_number:02d}.png"
        )
        record = self.uploader.upload_episode(
            self.series_name,
            script,
            video_path,
            chapters=compute_chapters(script, duration),
            thumbnail_path=thumbnail,
            privacy=privacy,
            publish_at=publish_at,
        )
        logger.info(
            "Episode %d is on YouTube (%s): %s", episode_number, record["privacy"], record["url"]
        )
        return str(record["url"])


def parse_publish_at(value: str) -> str:
    """Validate a future date/time and return it as UTC ISO 8601 (``...Z``).

    Accepts e.g. ``2026-10-01T18:30:00+05:30`` or ``2026-10-01T13:00:00Z``.
    """
    try:
        moment = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"Invalid date/time: {value!r}") from exc
    if moment.tzinfo is None:
        raise argparse.ArgumentTypeError("Include a time zone, e.g. 2026-10-01T18:30:00+05:30")
    moment = moment.astimezone(timezone.utc)
    if moment <= datetime.now(timezone.utc):
        raise argparse.ArgumentTypeError("--publish-at must be in the future")
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def setup_logging(verbose: bool = False) -> str:
    """Log to the console and to a timestamped file in ``LOGS_DIR``."""
    os.makedirs(config.LOGS_DIR, exist_ok=True)
    log_path = os.path.join(
        config.LOGS_DIR, f"generate_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    )
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        handlers=[logging.StreamHandler(), logging.FileHandler(log_path, encoding="utf-8")],
        force=True,
    )
    return log_path


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Command-line entry point."""
    parser = argparse.ArgumentParser(description="Generate Python Basics episodes")
    parser.add_argument("--series", default="python_basics", help="Series name")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--episode", "-e", type=int, default=1, help="Episode number")
    group.add_argument("--all", action="store_true", help="Generate every episode")
    group.add_argument("--list", action="store_true", help="List episodes and exit")
    parser.add_argument("--verbose", "-v", action="store_true", help="Debug logging")
    youtube = parser.add_argument_group("YouTube")
    youtube.add_argument("--upload", action="store_true", help="Upload after generating")
    youtube.add_argument(
        "--upload-only", action="store_true", help="Upload already generated video(s) only"
    )
    youtube.add_argument(
        "--privacy",
        choices=PRIVACY_OPTIONS,
        default=None,
        help=f"YouTube privacy (default: {config.YOUTUBE_PRIVACY})",
    )
    youtube.add_argument(
        "--publish-at",
        type=parse_publish_at,
        default=None,
        help="Schedule publishing, e.g. 2026-10-01T18:30:00+05:30 (uploads as private)",
    )
    youtube.add_argument(
        "--reupload", action="store_true", help="Upload even if already uploaded before"
    )
    args = parser.parse_args(argv)

    if args.list:
        for ep in config.get_series(args.series)["episodes"]:
            record = load_upload_record(args.series, ep["episode"])
            uploaded = f"  [uploaded: {record['url']}]" if record else ""
            print(
                f"{ep['episode']:>2}. {ep['title']} ({ep['duration_seconds'] // 60} min){uploaded}"
            )
        return 0

    setup_logging(args.verbose)
    generator = EpisodeGenerator(args.series)
    upload_options = {
        "privacy": args.privacy,
        "publish_at": args.publish_at,
        "reupload": args.reupload,
    }
    if args.all and args.publish_at:
        parser.error("--publish-at applies to one episode; use --episode with it")

    if args.upload_only:
        numbers = (
            [ep["episode"] for ep in generator.series["episodes"]] if args.all else [args.episode]
        )
        results = {n: generator.upload_existing(n, **upload_options) for n in numbers}
    elif args.all:
        results = generator.generate_all(upload=args.upload, **upload_options)
    else:
        results = {
            args.episode: generator.generate_episode(
                args.episode, upload=args.upload, **upload_options
            )
        }

    failed = [number for number, ok in results.items() if not ok]
    if failed:
        logger.error("Failed episodes: %s", failed)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
