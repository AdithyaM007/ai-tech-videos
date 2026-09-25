# Troubleshooting

Always start with the log in `output/logs/` and re-run with `-v` for full tracebacks.

| Symptom | Cause | Fix |
|---|---|---|
| `Missing required environment variable(s): ANTHROPIC_API_KEY` | `.env` missing or empty | `copy .env.example .env` and fill in keys |
| `Expecting ',' delimiter` / `No valid JSON object found` | Claude added prose around the JSON, or the output was cut off | Parsing already tolerates preamble and code fences. If it persists, look at the raw reply with `-v`, and raise `CLAUDE_MAX_TOKENS` |
| `Script was truncated (max_tokens reached)` | Output limit too low | Set `CLAUDE_MAX_TOKENS` higher |
| `Claude declined to generate this script` | Refusal stop reason | Check the episode's topics/examples in `config.py` |
| `TypeError: Client.__init__() got an unexpected keyword argument 'proxies'` | Old `anthropic` (e.g. 0.32) with `httpx` ≥ 0.28 | `pip install -r requirements.txt` (pins `anthropic==1.8.0`) |
| `ElevenLabs error 401` | Bad key | Check `ELEVENLABS_API_KEY` |
| `ElevenLabs error 400 … text too long` | Chunk above the model's limit | Lower `ELEVENLABS_MAX_CHARS` |
| `ElevenLabs error 429` | Quota / concurrency | Wait or upgrade the plan |
| `ImportError` from `moviepy` | MoviePy 2.x installed | `pip install moviepy==1.0.3` |
| `AttributeError: module 'PIL.Image' has no attribute 'ANTIALIAS'` | Pillow ≥ 10 with MoviePy 1.0.3 | Handled by `compat.patch_pil_antialias()`; make sure you import MoviePy through `video_generator` |
| Video renders slowly | Many code frames | Set `CODE_ANIMATION_ENABLED=false` for static code slides |
| Boxes instead of text on slides | No TrueType font found | Install DejaVu fonts, or add a font filename to `SANS_FONTS`/`MONO_FONTS` in `video_generator.py` |
| `ModuleNotFoundError: config` when running tests | `src/` not on path | Run `pytest` from the repo root (`pytest.ini` sets `pythonpath = src`) |

## FAQ

**How much does an episode cost?** Roughly $0.10 for the script and $0.20 for the
voiceover at the brief's estimates; check current pricing on each provider.

**Can I regenerate only the video?** Yes, see "Re-render a video" in
[SETUP.md](SETUP.md).

**How do I upload to YouTube?** See [YOUTUBE.md](YOUTUBE.md). It includes its own
troubleshooting table.

**Can I run the real end-to-end test?** `RUN_API_TESTS=1 pytest tests/e2e -m api`
(uses real API credits).
