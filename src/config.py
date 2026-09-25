"""Configuration for the Python Basics video generation system.

All settings can be overridden through environment variables (loaded from a
``.env`` file when present). Paths are computed from ``OUTPUT_DIR`` so a single
variable relocates every generated artifact.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Project paths
# ---------------------------------------------------------------------------
_SOURCE_ROOT = Path(__file__).resolve().parent.parent
# Source checkout -> repository root; installed package -> current directory.
PROJECT_ROOT: str = str(_SOURCE_ROOT if (_SOURCE_ROOT / "setup.py").exists() else Path.cwd())
OUTPUT_DIR: str = os.getenv("OUTPUT_DIR", os.path.join(PROJECT_ROOT, "output"))
SCRIPTS_DIR: str = os.path.join(OUTPUT_DIR, "scripts")
VOICEOVERS_DIR: str = os.path.join(OUTPUT_DIR, "voiceovers")
IMAGES_DIR: str = os.path.join(OUTPUT_DIR, "images")
VIDEOS_DIR: str = os.path.join(OUTPUT_DIR, "videos")
LOGS_DIR: str = os.path.join(OUTPUT_DIR, "logs")
UPLOADS_DIR: str = os.path.join(OUTPUT_DIR, "uploads")

# ---------------------------------------------------------------------------
# API configuration
# ---------------------------------------------------------------------------
ANTHROPIC_API_KEY: str | None = os.getenv("ANTHROPIC_API_KEY")
ELEVENLABS_API_KEY: str | None = os.getenv("ELEVENLABS_API_KEY")
YOUTUBE_CREDENTIALS_FILE: str = os.getenv("YOUTUBE_CREDENTIALS_FILE", "youtube_credentials.json")

YOUTUBE_TOKEN_FILE: str = os.getenv("YOUTUBE_TOKEN_FILE", "youtube_token.json")
# Uploads start private so each video can be reviewed before publishing.
YOUTUBE_PRIVACY: str = os.getenv("YOUTUBE_PRIVACY", "private")
YOUTUBE_PLAYLIST_PRIVACY: str = os.getenv("YOUTUBE_PLAYLIST_PRIVACY", "public")
YOUTUBE_CATEGORY_ID: str = os.getenv("YOUTUBE_CATEGORY_ID", "27")  # Education
YOUTUBE_CHANNEL_HANDLE: str = os.getenv("YOUTUBE_CHANNEL_HANDLE", "@techbytesexplained")
# The narration is an AI voice, so the upload declares synthetic media.
YOUTUBE_CONTAINS_SYNTHETIC_MEDIA: bool = os.getenv(
    "YOUTUBE_CONTAINS_SYNTHETIC_MEDIA", "true"
).lower() in ("1", "true", "yes")
YOUTUBE_TAGS: List[str] = [
    "python",
    "python tutorial",
    "python for beginners",
    "learn python",
    "programming",
    "coding for beginners",
]

CLAUDE_MODEL: str = os.getenv("CLAUDE_MODEL", "claude-opus-4-6")
CLAUDE_MAX_TOKENS: int = int(os.getenv("CLAUDE_MAX_TOKENS", "32000"))

ELEVENLABS_VOICE_ID: str = os.getenv("ELEVENLABS_VOICE_ID", "kdmDKE6EkgrWrrykO9Qt")
ELEVENLABS_MODEL: str = os.getenv("ELEVENLABS_MODEL", "eleven_v3")
ELEVENLABS_API_URL: str = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
ELEVENLABS_STABILITY: float = 0.5
ELEVENLABS_SIMILARITY_BOOST: float = 0.75
# Characters per TTS request; long narrations are split on sentence boundaries.
ELEVENLABS_MAX_CHARS: int = int(os.getenv("ELEVENLABS_MAX_CHARS", "4500"))
HTTP_TIMEOUT_SECONDS: int = 300

# ---------------------------------------------------------------------------
# Video settings
# ---------------------------------------------------------------------------
VIDEO_WIDTH: int = 1280
VIDEO_HEIGHT: int = 720
VIDEO_FPS: int = 30
VIDEO_CODEC: str = "libx264"
AUDIO_CODEC: str = "aac"

CODE_ANIMATION_ENABLED: bool = os.getenv("CODE_ANIMATION_ENABLED", "true").lower() in (
    "1",
    "true",
    "yes",
)
CODE_TYPING_SPEED: int = 2  # characters revealed per frame
CODE_HIGHLIGHT_ENABLED: bool = True
CODE_ANIMATION_SECONDS: int = 6
CODE_FONT_SIZE: int = 28

# Colour palette shared by slides, code frames and diagrams.
THEME: Dict[str, str] = {
    "background": "#1e1e2e",
    "surface": "#2a2a3d",
    "text": "#f5f5f5",
    "muted": "#a6adc8",
    "accent": "#ffd43b",  # Python yellow
    "accent2": "#4b8bbe",  # Python blue
}

# ---------------------------------------------------------------------------
# Series definition
# ---------------------------------------------------------------------------
SERIES: Dict[str, Dict[str, Any]] = {
    "python_basics": {
        "title": "Python Basics",
        "description": (
            "A complete beginner's introduction to Python programming, "
            "from installing Python to writing your first real programs."
        ),
        "target_audience": "Complete beginners who have never written code before",
        "episodes": [
            {
                "episode": 1,
                "title": "What is Python?",
                "subtitle": "Why Python, installing it, and your first program",
                "duration_seconds": 840,
                "topics": [
                    "Why Python",
                    "What Python is used for",
                    "Installing Python",
                    "Running your first program",
                ],
                "code_examples": [
                    {
                        "code": "print('Hello, World!')",
                        "explanation": "Your first Python program",
                    },
                    {
                        "code": "print(2 + 3)\nprint('Python' * 3)",
                        "explanation": "Python as a calculator",
                    },
                ],
                "diagrams": ["python_vs_languages", "installation_flow"],
            },
            {
                "episode": 2,
                "title": "Variables and Data Types",
                "subtitle": "Storing information in your programs",
                "duration_seconds": 840,
                "topics": ["Variables", "Strings", "Integers and floats", "Booleans"],
                "code_examples": [
                    {
                        "code": "name = 'Ada'\nage = 36\nprint(name, age)",
                        "explanation": "Creating variables",
                    },
                    {
                        "code": "price = 9.99\nis_open = True\nprint(type(price))",
                        "explanation": "Checking data types",
                    },
                ],
                "diagrams": ["variable_boxes", "data_types"],
            },
            {
                "episode": 3,
                "title": "Working with Strings",
                "subtitle": "Text manipulation made easy",
                "duration_seconds": 840,
                "topics": ["String methods", "f-strings", "Indexing", "Slicing"],
                "code_examples": [
                    {
                        "code": "greeting = 'hello'\nprint(greeting.upper())",
                        "explanation": "String methods",
                    },
                    {
                        "code": "name = 'Ada'\nprint(f'Hi, {name}!')",
                        "explanation": "f-strings",
                    },
                ],
                "diagrams": ["string_indexing"],
            },
            {
                "episode": 4,
                "title": "User Input and Type Conversion",
                "subtitle": "Making programs interactive",
                "duration_seconds": 840,
                "topics": ["input()", "int() and float()", "str()", "Common errors"],
                "code_examples": [
                    {
                        "code": "name = input('Your name: ')\nprint('Hello', name)",
                        "explanation": "Reading user input",
                    },
                    {
                        "code": "age = int(input('Age: '))\nprint(age + 1)",
                        "explanation": "Converting input to numbers",
                    },
                ],
                "diagrams": ["input_flow"],
            },
            {
                "episode": 5,
                "title": "Making Decisions with If Statements",
                "subtitle": "Conditions and branching",
                "duration_seconds": 840,
                "topics": ["Comparison operators", "if / elif / else", "Logical operators"],
                "code_examples": [
                    {
                        "code": (
                            "age = 18\nif age >= 18:\n    print('Adult')\n"
                            "else:\n    print('Minor')"
                        ),
                        "explanation": "A simple decision",
                    },
                ],
                "diagrams": ["if_else_flow"],
            },
            {
                "episode": 6,
                "title": "Loops: Repeating Actions",
                "subtitle": "for loops, while loops and range()",
                "duration_seconds": 840,
                "topics": ["for loops", "range()", "while loops", "break and continue"],
                "code_examples": [
                    {
                        "code": "for i in range(5):\n    print(i)",
                        "explanation": "Counting with a for loop",
                    },
                    {
                        "code": "count = 3\nwhile count > 0:\n    print(count)\n    count -= 1",
                        "explanation": "A while loop countdown",
                    },
                ],
                "diagrams": ["loop_flow"],
            },
            {
                "episode": 7,
                "title": "Lists: Storing Collections",
                "subtitle": "Working with ordered data",
                "duration_seconds": 840,
                "topics": ["Creating lists", "Indexing", "append and remove", "Looping over lists"],
                "code_examples": [
                    {
                        "code": (
                            "fruits = ['apple', 'banana']\n"
                            "fruits.append('cherry')\nprint(fruits)"
                        ),
                        "explanation": "Adding to a list",
                    },
                ],
                "diagrams": ["list_indexing"],
            },
            {
                "episode": 8,
                "title": "Dictionaries: Key-Value Data",
                "subtitle": "Looking things up by name",
                "duration_seconds": 840,
                "topics": ["Creating dictionaries", "Accessing values", "Updating", "Looping"],
                "code_examples": [
                    {
                        "code": "person = {'name': 'Ada', 'age': 36}\nprint(person['name'])",
                        "explanation": "Reading from a dictionary",
                    },
                ],
                "diagrams": ["dict_structure"],
            },
            {
                "episode": 9,
                "title": "Functions: Reusable Code",
                "subtitle": "def, parameters and return values",
                "duration_seconds": 840,
                "topics": ["Defining functions", "Parameters", "Return values", "Scope"],
                "code_examples": [
                    {
                        "code": (
                            "def greet(name):\n    return f'Hello, {name}!'\n\n"
                            "print(greet('Ada'))"
                        ),
                        "explanation": "Your first function",
                    },
                ],
                "diagrams": ["function_flow"],
            },
            {
                "episode": 10,
                "title": "Your First Real Project",
                "subtitle": "Building a number guessing game",
                "duration_seconds": 900,
                "topics": ["Planning a program", "random module", "Putting it all together"],
                "code_examples": [
                    {
                        "code": (
                            "import random\n\nsecret = random.randint(1, 10)\n"
                            "guess = int(input('Guess: '))\n"
                            "print('Correct!' if guess == secret else 'Try again')"
                        ),
                        "explanation": "A number guessing game",
                    },
                ],
                "diagrams": ["project_flow"],
            },
        ],
    }
}


def get_series(series_name: str) -> Dict[str, Any]:
    """Return a series definition, raising ``ValueError`` if it does not exist."""
    if series_name not in SERIES:
        raise ValueError(f"Unknown series: {series_name!r}")
    return SERIES[series_name]


def get_episode(series_name: str, episode_number: int) -> Dict[str, Any]:
    """Return a single episode definition, raising ``ValueError`` if missing."""
    episodes: List[Dict[str, Any]] = get_series(series_name)["episodes"]
    for episode in episodes:
        if episode["episode"] == episode_number:
            return episode
    raise ValueError(f"Episode {episode_number} not found in series {series_name!r}")


def get_anthropic_api_key() -> str | None:
    """Read the Anthropic API key at call time (so tests can patch the env)."""
    return os.getenv("ANTHROPIC_API_KEY") or ANTHROPIC_API_KEY


def get_elevenlabs_api_key() -> str | None:
    """Read the ElevenLabs API key at call time (so tests can patch the env)."""
    return os.getenv("ELEVENLABS_API_KEY") or ELEVENLABS_API_KEY


def ensure_output_dirs() -> None:
    """Create every output directory if it does not already exist."""
    for directory in (
        SCRIPTS_DIR,
        VOICEOVERS_DIR,
        IMAGES_DIR,
        VIDEOS_DIR,
        LOGS_DIR,
        UPLOADS_DIR,
    ):
        os.makedirs(directory, exist_ok=True)
