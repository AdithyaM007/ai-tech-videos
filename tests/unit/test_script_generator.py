"""Unit tests for script_generator.py."""

import json
import os
from unittest.mock import patch

import pytest

import config
from script_generator import (
    PythonBasicsScriptGenerator,
    ScriptGenerationError,
    load_script,
    validate_script,
)
from tests.fixtures.mock_responses import (
    CLAUDE_RESPONSE_FENCED,
    CLAUDE_RESPONSE_WITH_PREAMBLE,
    CLAUDE_SCRIPT_BODY,
    make_streaming_client,
)

EPISODE = {"episode": 1, "title": "Test Episode", "duration_seconds": 60}
MINIMAL = {"hook": "Hook", "intro": "Intro", "sections": [], "outro": "Outro"}


@pytest.mark.unit
class TestScriptGeneratorInit:
    def test_generator_initializes(self, mock_env):
        with patch("script_generator.anthropic.Anthropic"):
            gen = PythonBasicsScriptGenerator()
            assert gen.model == config.CLAUDE_MODEL

    def test_client_created_lazily_with_key(self, mock_env):
        with patch("script_generator.anthropic.Anthropic") as mock_client:
            gen = PythonBasicsScriptGenerator()
            mock_client.assert_not_called()
            assert gen.client is mock_client.return_value
            mock_client.assert_called_once_with(api_key="test-key-123")
            assert gen.client is mock_client.return_value  # cached
            assert mock_client.call_count == 1

    def test_model_override(self):
        assert PythonBasicsScriptGenerator(model="custom").model == "custom"


@pytest.mark.unit
class TestPromptGeneration:
    def _prompt(self):
        series = {"title": "Python Basics", "target_audience": "beginners"}
        episode = {
            "episode": 1,
            "title": "What is Python?",
            "subtitle": "Intro",
            "duration_seconds": 840,
            "topics": ["Why Python"],
            "code_examples": [{"code": "print('hi')", "explanation": "Greeting"}],
            "diagrams": ["python_vs_languages"],
        }
        return PythonBasicsScriptGenerator()._build_prompt(series, episode)

    def test_prompt_includes_episode_info(self):
        prompt = self._prompt()
        assert "Python Basics" in prompt
        assert "What is Python?" in prompt
        assert "beginners" in prompt
        assert "Why Python" in prompt
        assert "print('hi')" in prompt
        assert "python_vs_languages" in prompt
        assert "14 minutes" in prompt

    def test_prompt_includes_json_format_instruction(self):
        assert "JSON" in self._prompt()

    def test_prompt_handles_missing_optional_fields(self):
        prompt = PythonBasicsScriptGenerator()._build_prompt(
            {"title": "T", "target_audience": "a"}, {"episode": 1, "title": "X"}
        )
        assert "none required" in prompt


@pytest.mark.unit
class TestJsonParsing:
    def test_parse_valid_json(self):
        result = PythonBasicsScriptGenerator()._parse_script_response(
            json.dumps({**MINIMAL, "hook": "Test hook"}), EPISODE
        )
        assert result["hook"] == "Test hook"
        assert result["episode"] == 1

    def test_parse_json_with_preamble(self):
        result = PythonBasicsScriptGenerator()._parse_script_response(
            CLAUDE_RESPONSE_WITH_PREAMBLE, EPISODE
        )
        assert result["hook"] == CLAUDE_SCRIPT_BODY["hook"]

    def test_parse_json_in_code_fence(self):
        result = PythonBasicsScriptGenerator()._parse_script_response(
            CLAUDE_RESPONSE_FENCED, EPISODE
        )
        assert len(result["sections"]) == len(CLAUDE_SCRIPT_BODY["sections"])

    def test_parse_json_with_braces_in_preamble(self):
        text = "Note {this} is not JSON.\n" + json.dumps(MINIMAL) + "\nThanks!"
        result = PythonBasicsScriptGenerator()._parse_script_response(text, EPISODE)
        assert result["outro"] == "Outro"

    def test_parse_invalid_json_raises_error(self):
        with pytest.raises(ValueError):
            PythonBasicsScriptGenerator()._parse_script_response("This is not JSON", EPISODE)

    def test_parse_truncated_json_raises_error(self):
        with pytest.raises(ValueError):
            PythonBasicsScriptGenerator()._parse_script_response(json.dumps(MINIMAL)[:-5], EPISODE)

    def test_parse_missing_keys_raises_error(self):
        with pytest.raises(ValueError, match="missing 'outro'"):
            PythonBasicsScriptGenerator()._parse_script_response(
                json.dumps({"hook": "h", "intro": "i", "sections": []}), EPISODE
            )

    def test_parsed_script_has_metadata(self):
        result = PythonBasicsScriptGenerator()._parse_script_response(json.dumps(MINIMAL), EPISODE)
        assert result["episode"] == 1
        assert result["episode_title"] == "Test Episode"
        assert "generated_at" in result


@pytest.mark.unit
class TestValidateScript:
    def test_valid_script(self, sample_script_json):
        assert validate_script(sample_script_json) == []

    def test_sections_not_list(self):
        assert "'sections' must be a list" in validate_script({**MINIMAL, "sections": "x"})

    def test_bad_section_and_code_block(self):
        errors = validate_script({**MINIMAL, "sections": ["x", {"code_blocks": [{"a": 1}]}]})
        assert len(errors) == 2


@pytest.mark.unit
class TestGenerateScript:
    def test_generate_script_episode_1(self):
        client = make_streaming_client(CLAUDE_RESPONSE_WITH_PREAMBLE)
        gen = PythonBasicsScriptGenerator(client=client)
        script = gen.generate_script("python_basics", 1)

        assert script["episode"] == 1
        assert script["episode_title"] == "What is Python?"
        assert script["series"] == "python_basics"
        kwargs = client.messages.stream.call_args.kwargs
        assert kwargs["model"] == gen.model
        assert "What is Python?" in kwargs["messages"][0]["content"]

    @pytest.mark.parametrize("stop_reason", ["refusal", "max_tokens"])
    def test_bad_stop_reason_raises(self, stop_reason):
        client = make_streaming_client(CLAUDE_RESPONSE_FENCED, stop_reason=stop_reason)
        with pytest.raises(ScriptGenerationError):
            PythonBasicsScriptGenerator(client=client).generate_script("python_basics", 1)

    def test_invalid_episode_raises(self):
        gen = PythonBasicsScriptGenerator(client=make_streaming_client("{}"))
        with pytest.raises(ValueError):
            gen.generate_script("python_basics", 42)

    def test_generate_and_save(self, config_with_mocks):
        gen = PythonBasicsScriptGenerator(client=make_streaming_client(CLAUDE_RESPONSE_FENCED))
        path = gen.generate_and_save("python_basics", 1)
        assert os.path.dirname(path) == config.SCRIPTS_DIR
        assert os.path.basename(path).startswith("python_basics_ep01_")
        assert load_script(path)["episode"] == 1
