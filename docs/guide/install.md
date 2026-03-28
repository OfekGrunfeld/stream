---
title: Installation
description: How to install Stream and its dependencies using uv.
---

# Installation

## Requirements

- Python **3.12+**
- [`uv`](https://docs.astral.sh/uv/) (recommended) or `pip`

## Clone and install

```bash
git clone https://github.com/OfekGrunfeld/stream.git
cd stream

# Create a virtual environment and install the package + dev extras
uv venv
uv pip install -e ".[dev]"
```

The editable install exposes the `stream` package and the `python -m stream` CLI entry point.

## Verify

```bash
uv run python -m stream --help
```

Expected output:

```
 Usage: python -m stream [OPTIONS] COMMAND [ARGS]...

 Stream language interpreter.

╭─ Commands ──────────────────────────────────────────╮
│ run          Run a Stream source file.               │
│ lex          Tokenise a Stream source file.          │
│ parse        Parse a Stream source file.             │
│ obfuscate    Obfuscate a Stream source file.         │
│ deobfuscate  Deobfuscate a Stream source file.       │
╰─────────────────────────────────────────────────────╯
```

## Run the test suite

```bash
uv run pytest tests/ -q
```

All tests should pass (187 at the time of writing).

## Optional: MkDocs preview

```bash
uv pip install mkdocs-material
uv run mkdocs serve
```

Then open [http://127.0.0.1:8000](http://127.0.0.1:8000).
