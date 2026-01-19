set shell := ["bash", "-eu", "-o", "pipefail", "-c"]

lint:
    uv run ruff check .
    uv run mypy src

format:
    uv run ruff format .
    uv run ruff check --fix .

test:
    uv run pytest
