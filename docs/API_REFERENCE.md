# API Reference

All modules live in `src/` and are imported flat (`import config`).

## `config`

| Name | Description |
|---|---|
| `SERIES` | `{series_name: {title, description, target_audience, episodes: [...]}}` |
| `get_series(name)` | Series dict; `ValueError` if unknown |
| `get_episode(series, number)` | Episode dict; `ValueError` if unknown |
| `get_anthropic_api_key()` / `get_elevenlabs_api_key()` | Read keys from the environment at call time |
| `ensure_output_dirs()` | Create all output directories |
| `OUTPUT_DIR`, `SCRIPTS_DIR`, `VOICEOVERS_DIR`, `IMAGES_DIR`, `VIDEOS_DIR`, `LOGS_DIR` | Output paths |
| `CLAUDE_MODEL`, `CLAUDE_MAX_TOKENS` | Script generation settings |
| `ELEVENLABS_VOICE_ID`, `ELEVENLABS_MODEL`, `ELEVENLABS_STABILITY`, `ELEVENLABS_SIMILARITY_BOOST`, `ELEVENLABS_MAX_CHARS` | Voiceover settings |
| `VIDEO_WIDTH`, `VIDEO_HEIGHT`, `VIDEO_FPS`, `VIDEO_CODEC`, `AUDIO_CODEC` | Output video format |
| `CODE_ANIMATION_ENABLED`, `CODE_TYPING_SPEED`, `CODE_ANIMATION_SECONDS`, `CODE_FONT_SIZE` | Code animation |
| `THEME` | Colour palette |

## `script_generator`

### `PythonBasicsScriptGenerator(api_key=None, model=None, client=None)`

| Method | Returns | Notes |
|---|---|---|
| `generate_script(series_name, episode_number)` | `dict` | Calls Claude; raises `ScriptGenerationError` on refusal/truncation, `ValueError` on bad JSON or unknown episode |
| `generate_and_save(series_name, episode_number)` | `str` path | `generate_script` + `_save_script` |
| `_build_prompt(series, episode)` | `str` | |
| `_parse_script_response(response_text, episode)` | `dict` | Extracts + validates JSON, adds metadata |
| `_save_script(series_name, episode_number, script_data)` | `str` path | `SCRIPTS_DIR/<series>_epNN_<timestamp>.json` |
| `client` (property) | `anthropic.Anthropic` | Created lazily |

Module functions: `validate_script(script) -> list[str]`, `load_script(path) -> dict`.

## `generate_episode`

### `EpisodeGenerator(series_name="python_basics")`

| Method | Returns | Notes |
|---|---|---|
| `generate_episode(n, upload=False, privacy=None, publish_at=None, reupload=False)` | `bool` | Optional stage 4 |
| `upload_existing(n, privacy=None, publish_at=None, reupload=False)` | `bool` | Upload the latest generated video |
| `generate_all(episodes=None, **options)` | `dict[int, bool]` | `options` go to `generate_episode` |
| `check_configuration()` | `None` | Raises `ConfigurationError` if keys are missing |
| `_generate_script(episode_number)` | `str` path | Also sets `current_script` |
| `_generate_voiceover(script_path, script_data=None)` | `str` path | Loads the script from disk if `script_data` is `None`; raises `VoiceoverError` |
| `_generate_video(script_path, audio_path, episode_number)` | `str` path | `VIDEOS_DIR/<series>_epNN.mp4` |

Module functions: `build_narration(script)`, `split_text(text, max_chars)`,
`setup_logging(verbose=False)`, `main(argv=None) -> int`.

CLI: `--episode/-e N`, `--all`, `--list`, `--series NAME`, `--verbose/-v`,
`--upload`, `--upload-only`, `--privacy {private,unlisted,public}`,
`--publish-at ISO_DATETIME`, `--reupload`.

## `video_generator`

### `CodeAnimationGenerator(width, height, fps, typing_speed, font_size)`
- `generate_code_animation(code_text, output_dir, duration_seconds=6, prefix="code_frame", title="") -> list[str]`
- `render_static_code(code_text, output_path, title="") -> str`
- `_render_code_frame(code_text, output_path, title="", cursor=False)`

### `DiagramGenerator(width, height)`
- `generate_comparison_chart(title, items, output_path, value_label=...) -> str` – `items` is `[(label, value)]` or `[{"label", "value"}]`; empty uses defaults
- `generate_flowchart(title, steps, output_path) -> str`
- `generate_installation_flow(output_path) -> str`
- `generate_concept_card(title, description, output_path) -> str`

### `SlideGenerator(width, height)`
- `create_title_slide(series_title, episode_number, title, subtitle, output_path)`
- `create_content_slide(title, bullets, output_path)`
- `create_closing_slide(key_learnings, next_title, output_path)`

### `AdvancedVideoGenerator(width, height, fps)`
- `generate_episode_video(script_path, audio_path, output_path, images_dir=None) -> str`
- `build_timeline(script, total_seconds) -> list[(image_path, seconds)]`
- `_create_title_slide(script)`, `_create_section_slides(section, script, index)`,
  `_create_content_slide(section, index)`, `_generate_diagram(diagram, suffix)`,
  `_create_closing_slide(script)`, `_assemble_video(segments, audio_path, output_path)`

Module function: `frames_to_segments(frames, fps)`.

## `youtube_uploader`

### `YouTubeUploader(credentials_file=None, token_file=None, service=None)`

| Method | Returns | Notes |
|---|---|---|
| `upload_episode(series_name, script, video_path, chapters=None, thumbnail_path=None, privacy=None, publish_at=None)` | `dict` record | Upload + thumbnail + playlist + record file |
| `upload_video(video_path, metadata, privacy="private", publish_at=None)` | video ID | Resumable upload with retries; raises `UploadError` |
| `set_thumbnail(video_id, image_path)` | `bool` | |
| `get_or_create_playlist(title, description="")` | playlist ID | |
| `add_to_playlist(playlist_id, video_id)` | `None` | |
| `service` (property) | API client | Signs in on first use |

Module functions: `build_metadata(script, series, chapters=None)`,
`format_timestamp(seconds)`, `load_upload_record(series, episode)`,
`record_path(series, episode)`, `find_latest_script(series, episode)`.

`video_generator.compute_chapters(script, total_seconds)` returns
`[(title, start_seconds)]`; `video_generator.part_weights(script)` returns the
relative weights both the timeline and the chapters use.

## `compat`
- `patch_pil_antialias()` – restores `PIL.Image.ANTIALIAS` for MoviePy 1.0.3 on Pillow ≥ 10.
