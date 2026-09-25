# Contributing to Python Basics Videos

## Getting Started

1. Fork the repository
2. Clone your fork: `git clone https://github.com/YOUR_USERNAME/ai-tech-videos.git`
3. Create virtual env: `python -m venv venv`
4. Activate venv: `venv\Scripts\activate` (Windows) or `source venv/bin/activate` (Mac/Linux)
5. Install dev dependencies: `pip install -r requirements-dev.txt`
6. Install pre-commit: `pre-commit install`

## Development Workflow

1. Create feature branch: `git checkout -b feature/your-feature`
2. Make changes
3. Run tests: `pytest`
4. Run linting: `black src/ tests/ && flake8 src/ tests/ && mypy src/`
5. Commit: `git commit -m "type(scope): description"`
6. Push: `git push origin feature/your-feature`
7. Create Pull Request against `develop` or `main`

## Code Style

- Black formatting, line length 100 (`pyproject.toml`)
- PEP 8, checked by flake8 (`.flake8`)
- Type hints on all functions (checked by mypy)
- Docstrings on all public classes and methods
- 80% test coverage minimum (enforced in CI)

## Testing

```bash
pytest                          # everything except real-API tests
pytest tests/unit -v            # unit tests only
pytest -m "not slow"            # skip rendering-heavy tests
pytest --cov=src --cov-report=html   # then open htmlcov/index.html
RUN_API_TESTS=1 pytest -m api   # real Claude + ElevenLabs calls (costs money)
```

- Write tests for all new features
- Use the fixtures in `tests/conftest.py` (`temp_output_dir`, `mock_env`,
  `config_with_mocks`, `sample_script_json`, ...)
- Mock external API calls (`tests/fixtures/mock_responses.py`)

## Commit Messages

Format: `type(scope): description`

- `feat(script-gen): add custom code examples`
- `fix(video-gen): correct timing calculation`
- `docs(readme): update setup instructions`
- `test(orchestration): add integration tests`

Types: feat, fix, docs, test, refactor, perf, chore
