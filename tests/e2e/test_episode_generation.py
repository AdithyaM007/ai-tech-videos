"""End-to-end tests.

``TestVideoAssembly`` renders a real MP4 with MoviePy/FFmpeg (no API calls).
``TestEpisode1Generation`` hits the real Claude and ElevenLabs APIs and is
skipped unless ``RUN_API_TESTS=1`` and both API keys are set.
"""

import os
import subprocess  # nosec B404 - only used to call the bundled ffmpeg

import pytest

import config
from generate_episode import EpisodeGenerator
from video_generator import AdvancedVideoGenerator


def _make_silent_mp3(path: str, seconds: int) -> None:
    import imageio_ffmpeg

    subprocess.run(  # nosec B603 - fixed arguments
        [
            imageio_ffmpeg.get_ffmpeg_exe(),
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "anullsrc=r=44100:cl=mono",
            "-t",
            str(seconds),
            "-q:a",
            "9",
            path,
        ],
        check=True,
    )


@pytest.mark.e2e
@pytest.mark.slow
class TestVideoAssembly:
    def test_video_assembly(self, sample_script_path, temp_output_dir):
        from compat import patch_pil_antialias

        patch_pil_antialias()
        from moviepy.editor import VideoFileClip

        audio = os.path.join(temp_output_dir, "silence.mp3")
        _make_silent_mp3(audio, 12)
        output = os.path.join(temp_output_dir, "videos", "episode.mp4")

        AdvancedVideoGenerator().generate_episode_video(
            sample_script_path, audio, output, images_dir=os.path.join(temp_output_dir, "img")
        )

        clip = VideoFileClip(output)
        try:
            assert clip.size == [config.VIDEO_WIDTH, config.VIDEO_HEIGHT]
            assert clip.fps == config.VIDEO_FPS
            assert clip.duration == pytest.approx(12, abs=0.5)
            assert clip.audio is not None
        finally:
            clip.close()


@pytest.mark.e2e
@pytest.mark.api
@pytest.mark.skipif(
    os.getenv("RUN_API_TESTS") != "1"
    or not (os.getenv("ANTHROPIC_API_KEY") and os.getenv("ELEVENLABS_API_KEY")),
    reason="Requires RUN_API_TESTS=1 and real API keys",
)
class TestEpisode1Generation:
    def test_generate_episode_1_complete(self, config_with_mocks):
        assert EpisodeGenerator().generate_episode(1) is True
        assert os.path.exists(os.path.join(config.VIDEOS_DIR, "python_basics_ep01.mp4"))
