# Setup

## Prerequisites

- Windows 10/11, macOS or Linux
- Python 3.10, 3.11 or 3.12
- An [Anthropic API key](https://console.anthropic.com) and an [ElevenLabs API key](https://elevenlabs.io)

FFmpeg does **not** need to be installed separately: `imageio-ffmpeg` ships a binary
that MoviePy uses automatically. If you prefer your own FFmpeg, set
`IMAGEIO_FFMPEG_EXE` to its path.

## Install

```powershell
git clone https://github.com/AdithyaM007/ai-tech-videos.git
cd ai-tech-videos
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt        # or: pip install -e .
```

## Configure

```powershell
copy .env.example .env
```

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | yes | – | Script generation |
| `ELEVENLABS_API_KEY` | yes | – | Voiceover |
| `ELEVENLABS_VOICE_ID` | no | `kdmDKE6EkgrWrrykO9Qt` | Narrator voice |
| `ELEVENLABS_MODEL` | no | `eleven_v3` | TTS model |
| `ELEVENLABS_MAX_CHARS` | no | `4500` | Characters per TTS request (long narrations are split) |
| `CLAUDE_MODEL` | no | `claude-opus-4-6` | Model used for scripts |
| `CLAUDE_MAX_TOKENS` | no | `32000` | Output token limit per script |
| `OUTPUT_DIR` | no | `./output` | Root for all generated files |
| `CODE_ANIMATION_ENABLED` | no | `true` | `false` renders static code slides (faster) |
| `YOUTUBE_CREDENTIALS_FILE` | for upload | `youtube_credentials.json` | OAuth client file ([YOUTUBE.md](YOUTUBE.md)) |
| `YOUTUBE_TOKEN_FILE` | no | `youtube_token.json` | Saved YouTube login |
| `YOUTUBE_PRIVACY` | no | `private` | Default privacy for uploads |
| `YOUTUBE_PLAYLIST_PRIVACY` | no | `public` | Privacy of the series playlist when it is created |
| `YOUTUBE_CHANNEL_HANDLE` | no | `@techbytesexplained` | Used in the description's subscribe link |
| `YOUTUBE_CONTAINS_SYNTHETIC_MEDIA` | no | `true` | Declares the AI voice to YouTube |

## First run

```powershell
python src\generate_episode.py --episode 1
```

Expected output (paths relative to `OUTPUT_DIR`):

```
scripts/python_basics_ep01_<timestamp>.json
voiceovers/ep01_<timestamp>.mp3
images/ep01/*.png
videos/python_basics_ep01.mp4
logs/generate_<timestamp>.log
uploads/python_basics_ep01.json      (only with --upload)
```

To publish to YouTube, see [YOUTUBE.md](YOUTUBE.md).

If you installed with `pip install -e .`, the `python-basics-videos` command is
equivalent to `python src/generate_episode.py`.

## Customisation

- **Add or edit episodes** – edit `SERIES["python_basics"]["episodes"]` in
  `src/config.py`. Each episode needs `episode`, `title`, `subtitle`,
  `duration_seconds`, `topics`, `code_examples` and `diagrams`.
- **Add a new series** – add another key to `SERIES` and run with `--series <name>`.
- **Colours** – change `THEME` in `src/config.py`.
- **Re-render a video without paying for APIs again** – reuse existing files:

  ```python
  from video_generator import AdvancedVideoGenerator
  AdvancedVideoGenerator().generate_episode_video(
      "output/scripts/python_basics_ep01_....json",
      "output/voiceovers/ep01_....mp3",
      "output/videos/python_basics_ep01.mp4",
  )
  ```
