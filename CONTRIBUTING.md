# Contributing to dockerlens

Thanks for your interest in contributing! Here's how to get started.

## Development Setup

1. **Clone the repository:**

   ```bash
   git clone https://github.com/tinkerera/dockerlens.git
   cd dockerlens
   ```

2. **Create a virtual environment:**

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```

3. **Install in editable mode with dev dependencies:**

   ```bash
   pip install -e ".[dev]"
   ```

4. **Install pre-commit hooks:**

   ```bash
   pre-commit install
   ```

## Running Tests

Tests are designed to run **without a Docker daemon** — all Docker SDK calls are mocked.

```bash
pytest tests/ -v
```

## Code Style

We use [ruff](https://docs.astral.sh/ruff/) for linting and formatting:

```bash
# Lint
ruff check src/ tests/

# Format
ruff format src/ tests/
```

## Type Checking

```bash
mypy src/
```

## Pull Request Process

1. Fork the repo and create a feature branch from `main`.
2. Write tests for any new functionality.
3. Ensure all checks pass: `ruff check`, `mypy`, `pytest`.
4. Open a PR with a clear description of your changes.
5. Wait for review — we aim to respond within 48 hours.

## Reporting Issues

Please use [GitHub Issues](https://github.com/tinkerera/dockerlens/issues) and include:
- Python version
- Docker version
- Steps to reproduce
- Expected vs. actual behavior
