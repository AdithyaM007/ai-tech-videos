"""Stage 1: generate an episode script with the Claude API."""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

import anthropic

import config

logger = logging.getLogger(__name__)

REQUIRED_SCRIPT_KEYS = ("hook", "intro", "sections", "outro")

SYSTEM_PROMPT = (
    "You are an expert programming educator who writes scripts for YouTube "
    "tutorial videos aimed at complete beginners. Your scripts are friendly, "
    "clear, accurate and paced for narration. You always reply with a single "
    "valid JSON object and nothing else."
)


class ScriptGenerationError(RuntimeError):
    """Raised when Claude does not return a usable script."""


class PythonBasicsScriptGenerator:
    """Generates structured episode scripts using Anthropic's Claude API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        client: Optional[anthropic.Anthropic] = None,
    ) -> None:
        self.api_key = api_key
        self.model: str = model or config.CLAUDE_MODEL
        self.max_tokens: int = config.CLAUDE_MAX_TOKENS
        self._client = client

    @property
    def client(self) -> anthropic.Anthropic:
        """Lazily construct the Anthropic client on first use."""
        if self._client is None:
            api_key = self.api_key or config.get_anthropic_api_key()
            self._client = anthropic.Anthropic(api_key=api_key)
        return self._client

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def generate_script(self, series_name: str, episode_number: int) -> Dict[str, Any]:
        """Generate the script for one episode and return it as a dict."""
        series = config.get_series(series_name)
        episode = config.get_episode(series_name, episode_number)
        prompt = self._build_prompt(series, episode)

        logger.info("Requesting script for %s episode %d", series_name, episode_number)
        # Streaming avoids HTTP timeouts on long generations.
        with self.client.messages.stream(
            model=self.model,
            max_tokens=self.max_tokens,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            message = stream.get_final_message()

        if message.stop_reason == "refusal":
            raise ScriptGenerationError("Claude declined to generate this script")
        if message.stop_reason == "max_tokens":
            raise ScriptGenerationError(
                "Script was truncated (max_tokens reached); raise CLAUDE_MAX_TOKENS"
            )

        text = "".join(block.text for block in message.content if block.type == "text")
        script = self._parse_script_response(text, episode)
        script["series"] = series_name
        script["model"] = self.model
        return script

    def generate_and_save(self, series_name: str, episode_number: int) -> str:
        """Generate a script and write it to ``SCRIPTS_DIR``; return the file path."""
        script = self.generate_script(series_name, episode_number)
        return self._save_script(series_name, episode_number, script)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _build_prompt(self, series: Dict[str, Any], episode: Dict[str, Any]) -> str:
        """Build the script-writing prompt for one episode."""
        duration = int(episode.get("duration_seconds", 840))
        minutes = max(1, round(duration / 60))
        topics = "\n".join(f"- {topic}" for topic in episode.get("topics", [])) or "- (none)"
        examples = (
            "\n".join(
                f"- {ex.get('explanation', '')}:\n```python\n{ex.get('code', '')}\n```"
                for ex in episode.get("code_examples", [])
            )
            or "- Choose simple, runnable examples that fit the topics."
        )
        diagrams = ", ".join(episode.get("diagrams", [])) or "none required"

        return f"""Write the narration script for a YouTube tutorial episode.

SERIES: {series.get('title', '')}
TARGET AUDIENCE: {series.get('target_audience', '')}
EPISODE {episode.get('episode')}: {episode.get('title', '')}
SUBTITLE: {episode.get('subtitle', '')}
TARGET DURATION: about {minutes} minutes ({duration} seconds) of narration,
roughly {int(duration * 2.5)} spoken words in total.

TOPICS TO COVER (in order):
{topics}

CODE EXAMPLES TO INCLUDE (you may add more):
{examples}

DIAGRAMS TO REFERENCE: {diagrams}

GUIDELINES:
- Assume the viewer has never written code. Define every new term.
- Write for the ear: short sentences, conversational tone, no markdown.
- Every code block must be valid, runnable Python 3.
- Explain each code block line by line in the section script.
- Section durations should add up to roughly the target duration.

OUTPUT FORMAT: Respond with ONLY a JSON object (no preamble, no code fences)
matching this structure:
{{
  "hook": "10-15 second attention-grabbing opening",
  "intro": "about 30 seconds introducing the episode",
  "sections": [
    {{
      "title": "Section title",
      "duration_seconds": 120,
      "script": "Narration for this section",
      "key_points": ["Short bullet for the slide", "..."],
      "code_blocks": [
        {{"code": "print('Hello')", "explanation": "What it shows", "timing_seconds": 30}}
      ],
      "diagrams": [
        {{"name": "diagram_name", "type": "chart|flowchart|concept", "description": "..."}}
      ]
    }}
  ],
  "outro": "Recap and call to action for the next episode",
  "total_duration_seconds": {duration},
  "key_learnings": ["...", "..."]
}}"""

    def _parse_script_response(self, response_text: str, episode: Dict[str, Any]) -> Dict[str, Any]:
        """Extract the JSON script from Claude's reply and add metadata.

        Handles replies wrapped in code fences or preceded by preamble text.
        Raises ``ValueError`` when no valid script object can be found.
        """
        data = _extract_json_object(response_text)
        if data is None:
            raise ValueError("No valid JSON object found in Claude response")

        errors = validate_script(data)
        if errors:
            raise ValueError("Invalid script structure: " + "; ".join(errors))

        data["episode"] = episode.get("episode")
        data["episode_title"] = episode.get("title")
        data["generated_at"] = datetime.now().isoformat(timespec="seconds")
        return data

    def _save_script(
        self, series_name: str, episode_number: int, script_data: Dict[str, Any]
    ) -> str:
        """Write the script JSON to disk and return its path."""
        os.makedirs(config.SCRIPTS_DIR, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{series_name}_ep{episode_number:02d}_{timestamp}.json"
        path = os.path.join(config.SCRIPTS_DIR, filename)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(script_data, f, indent=2, ensure_ascii=False)
        logger.info("Saved script to %s", path)
        return path


def _extract_json_object(text: str) -> Optional[Dict[str, Any]]:
    """Return the first JSON object embedded in ``text`` (or ``None``)."""
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    candidates: List[str] = [fenced.group(1)] if fenced else []
    candidates.append(text)

    decoder = json.JSONDecoder()
    for candidate in candidates:
        start = candidate.find("{")
        while start != -1:
            try:
                obj, _ = decoder.raw_decode(candidate, start)
            except json.JSONDecodeError:
                start = candidate.find("{", start + 1)
                continue
            if isinstance(obj, dict):
                return obj
            start = candidate.find("{", start + 1)
    return None


def validate_script(script: Dict[str, Any]) -> List[str]:
    """Return a list of structural problems with a script (empty if valid)."""
    errors = [f"missing '{key}'" for key in REQUIRED_SCRIPT_KEYS if key not in script]
    sections = script.get("sections", [])
    if not isinstance(sections, list):
        errors.append("'sections' must be a list")
        return errors
    for index, section in enumerate(sections):
        if not isinstance(section, dict):
            errors.append(f"section {index} must be an object")
            continue
        for block in section.get("code_blocks", []) or []:
            if not isinstance(block, dict) or "code" not in block:
                errors.append(f"section {index} has a code block without 'code'")
    return errors


def load_script(path: str) -> Dict[str, Any]:
    """Load a script JSON file from disk."""
    with open(path, encoding="utf-8") as f:
        data: Dict[str, Any] = json.load(f)
    return data
