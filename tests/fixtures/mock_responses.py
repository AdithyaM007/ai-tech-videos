"""Canned API responses for tests."""

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List
from unittest.mock import MagicMock

SAMPLE_SCRIPT: Dict[str, Any] = json.loads(
    (Path(__file__).parent / "sample_script.json").read_text(encoding="utf-8")
)

# What Claude returns: the script body without our metadata fields.
CLAUDE_SCRIPT_BODY: Dict[str, Any] = {
    key: value
    for key, value in SAMPLE_SCRIPT.items()
    if key not in ("episode", "episode_title", "series")
}

CLAUDE_RESPONSE_WITH_PREAMBLE = "Here's the script you asked for:\n\n" + json.dumps(
    CLAUDE_SCRIPT_BODY, indent=2
)

CLAUDE_RESPONSE_FENCED = "```json\n" + json.dumps(CLAUDE_SCRIPT_BODY) + "\n```"

FAKE_MP3_BYTES = b"ID3" + b"\x00" * 256


def make_claude_message(text: str, stop_reason: str = "end_turn") -> SimpleNamespace:
    """Build an object shaped like ``anthropic.types.Message``."""
    blocks: List[SimpleNamespace] = [SimpleNamespace(type="text", text=text)]
    return SimpleNamespace(content=blocks, stop_reason=stop_reason)


def make_streaming_client(text: str, stop_reason: str = "end_turn") -> MagicMock:
    """A mock Anthropic client whose ``messages.stream`` yields ``text``."""
    client = MagicMock()
    stream = MagicMock()
    stream.get_final_message.return_value = make_claude_message(text, stop_reason)
    client.messages.stream.return_value.__enter__.return_value = stream
    return client


def make_http_response(status_code: int = 200, content: bytes = FAKE_MP3_BYTES) -> MagicMock:
    """A mock ``requests.Response``."""
    response = MagicMock()
    response.status_code = status_code
    response.content = content
    response.text = content.decode("latin-1") if status_code != 200 else ""
    return response
