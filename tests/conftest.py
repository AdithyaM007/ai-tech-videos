"""Shared pytest fixtures."""

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterator

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def temp_output_dir() -> Iterator[str]:
    """Create a temporary directory for test outputs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def mock_env(monkeypatch: pytest.MonkeyPatch) -> Dict[str, str]:
    """Provide fake API keys through the environment."""
    keys = {"ANTHROPIC_API_KEY": "test-key-123", "ELEVENLABS_API_KEY": "test-key-456"}
    for name, value in keys.items():
        monkeypatch.setenv(name, value)
    return keys


@pytest.fixture
def no_api_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove API keys from both the environment and the loaded config."""
    import config

    for name in ("ANTHROPIC_API_KEY", "ELEVENLABS_API_KEY"):
        monkeypatch.delenv(name, raising=False)
        monkeypatch.setattr(config, name, None)


@pytest.fixture
def sample_script_json() -> Dict[str, Any]:
    """Load the sample valid script JSON."""
    with open(FIXTURES_DIR / "sample_script.json", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def sample_script_path(temp_output_dir: str, sample_script_json: Dict[str, Any]) -> str:
    """Write the sample script to a temp file and return its path."""
    path = os.path.join(temp_output_dir, "script.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(sample_script_json, f)
    return path


@pytest.fixture
def sample_audio_path(temp_output_dir: str) -> str:
    """Create a dummy MP3 file (ID3 header + padding)."""
    audio_path = os.path.join(temp_output_dir, "test_audio.mp3")
    with open(audio_path, "wb") as f:
        f.write(b"ID3" + b"\x00" * 100)
    return audio_path


@pytest.fixture
def config_with_mocks(monkeypatch: pytest.MonkeyPatch, temp_output_dir: str) -> str:
    """Point every output directory at a temporary folder."""
    import config

    monkeypatch.setattr(config, "OUTPUT_DIR", temp_output_dir)
    for attr, sub in (
        ("SCRIPTS_DIR", "scripts"),
        ("VOICEOVERS_DIR", "voiceovers"),
        ("IMAGES_DIR", "images"),
        ("VIDEOS_DIR", "videos"),
        ("LOGS_DIR", "logs"),
    ):
        monkeypatch.setattr(config, attr, os.path.join(temp_output_dir, sub))
    return temp_output_dir
