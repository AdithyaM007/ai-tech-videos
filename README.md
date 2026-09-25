# Python Basics Videos

[![Tests](https://github.com/AdithyaM007/ai-tech-videos/actions/workflows/test.yml/badge.svg)](https://github.com/AdithyaM007/ai-tech-videos/actions/workflows/test.yml)
[![Lint](https://github.com/AdithyaM007/ai-tech-videos/actions/workflows/lint.yml/badge.svg)](https://github.com/AdithyaM007/ai-tech-videos/actions/workflows/lint.yml)

Automated generation of the **Python Basics** YouTube series (10 episodes, 12–15
minutes each, for complete beginners). One command turns an episode definition into
a finished 1280×720, 30 FPS MP4 with a narrated voiceover, animated code and diagrams.

```
Episode spec ──► Claude (script JSON) ──► ElevenLabs (MP3) ──► MoviePy (MP4)
 config.py        script_generator.py      generate_episode.py   video_generator.py
```

## Quick start

```powershell
python -m venv venv
venv\Scripts\activate            # macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
copy .env.example .env           # then add your API keys
python src\generate_episode.py --episode 1
```

The video is written to `output/videos/python_basics_ep01.mp4`.

```powershell
python src\generate_episode.py --list      # show all episodes
python src\generate_episode.py --all       # generate all 10
python src\generate_episode.py -e 3 -v     # episode 3 with debug logging
```

## Project layout

```
src/
  config.py             Series/episode definitions, API + video settings, paths
  script_generator.py   Stage 1 – Claude script generation and JSON parsing
  generate_episode.py   Orchestrator + Stage 2 – ElevenLabs voiceover, CLI entry point
  video_generator.py    Stage 3 – code animation, diagrams, slides, MoviePy assembly
  compat.py             Pillow 10 / MoviePy 1.0.3 compatibility shim
tests/                  unit / integration / e2e pytest suites (+ fixtures)
docs/                   Setup, architecture, API reference, troubleshooting
.github/workflows/      test.yml, lint.yml, build.yml
```

## Development

```powershell
pip install -r requirements-dev.txt
pre-commit install
pytest --cov=src                   # 80% minimum coverage is enforced
black src tests; flake8 src tests; mypy src
```

See [CONTRIBUTING.md](CONTRIBUTING.md) and the [docs](docs/README.md).
