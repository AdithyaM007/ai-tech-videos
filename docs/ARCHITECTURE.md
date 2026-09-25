# Architecture

```
                     ┌────────────────────────── EpisodeGenerator ──────────────────────────┐
 config.SERIES ──►   │ 1. _generate_script ──► 2. _generate_voiceover ──► 3. _generate_video │ ──► MP4
                     └──────────┬──────────────────────┬───────────────────────────┬─────────┘
                                ▼                      ▼                           ▼
                   PythonBasicsScriptGenerator   ElevenLabs REST API     AdvancedVideoGenerator
                   (Claude Messages API,          (chunked, MP3)          ├─ SlideGenerator
                    streaming)                                            ├─ CodeAnimationGenerator
                                                                          ├─ DiagramGenerator
                                                                          └─ MoviePy assembly
```

## Stage 1 – script (`script_generator.py`)

`PythonBasicsScriptGenerator.generate_script()` builds a prompt from the episode
definition (topics, code examples, diagrams, target duration ≈ 2.5 words/second)
and streams a response from Claude. Streaming avoids HTTP timeouts on long outputs.

`_parse_script_response()` is deliberately tolerant: it accepts a bare JSON object,
a fenced ```` ```json ```` block, or JSON preceded/followed by prose, by trying
`json.JSONDecoder.raw_decode` at each `{`. The result is validated
(`validate_script`) and stamped with `episode`, `episode_title`, `generated_at`.
A `refusal` or `max_tokens` stop reason raises `ScriptGenerationError`.

### Script JSON

```json
{
  "hook": "...", "intro": "...",
  "sections": [{
    "title": "...", "duration_seconds": 120, "script": "...",
    "key_points": ["..."],
    "code_blocks": [{"code": "...", "explanation": "...", "timing_seconds": 30}],
    "diagrams": [{"name": "...", "type": "chart|flowchart|concept", "description": "..."}]
  }],
  "outro": "...", "total_duration_seconds": 840, "key_learnings": ["..."],
  "episode": 1, "episode_title": "...", "generated_at": "...", "series": "...", "model": "..."
}
```

## Stage 2 – voiceover (`generate_episode.py`)

`build_narration()` joins hook, intro, each section's `script` and outro.
`split_text()` breaks it into ≤ `ELEVENLABS_MAX_CHARS` chunks on sentence
boundaries; each chunk is sent to `POST /v1/text-to-speech/{voice_id}` with
stability 0.5 / similarity boost 0.75, and the MP3 responses are concatenated.

## Stage 3 – video (`video_generator.py`)

1. **Visuals** – for every part of the script:
   - title slide (hook + intro)
   - per section: a bullet slide, a typing animation for each code block, one
     image per diagram
   - closing slide (key learnings + next episode)
2. **Timing** – `build_timeline()` gives every part a weight (section
   `duration_seconds`, or word count for hook/intro/outro) and scales the weights so
   the total equals the real audio length. Typing frames keep real-time durations;
   the final "code complete" frame absorbs the remaining time.
3. **Assembly** – `_assemble_video()` creates one `ImageClip` per timeline segment,
   concatenates them, attaches the MP3, and encodes H.264/AAC.

### Code animation

`CodeAnimationGenerator.generate_code_animation()` returns one frame path per video
frame (`duration × fps`), but only renders a PNG when the visible text changes;
repeated frames reuse the previous path. Typing finishes within the first two
thirds of the clip so the viewer can read the finished code. Highlighting uses
Pygments' `monokai` style.

### Diagrams

`_generate_diagram()` routes by name/type: names containing `install` →
installation flowchart; `python_vs_languages` or type `chart` → bar chart;
type `flowchart` with `steps` → generic flowchart; anything else → a concept card
with the description. A failing diagram is logged and skipped, not fatal.

## Error handling

`EpisodeGenerator.generate_episode()` validates the episode number and API keys
before spending money, runs the stages in order, logs any exception (full traceback
at `-v`), and returns `False` instead of raising. The CLI exits non-zero on failure.
