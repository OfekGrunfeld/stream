#!/usr/bin/env bash
# run.sh — demonstrate each Stream example program
#
# Prerequisites:
#   uv venv && uv pip install -e .   (from the repo root)
#
# Usage:
#   ./examples/run.sh           # run all examples
#   ./examples/run.sh 01        # run only example 01
#
# The .stream files are the human-readable source.
# The .st files are level-3 obfuscated forms (operators + keywords replaced
# with Unicode glyphs, but identifiers kept readable).

set -euo pipefail
cd "$(dirname "$0")/.."

RUN() { echo; echo "▶ $*"; echo "───────────────────────────────────────"; uv run "$@"; }
TITLE() { echo; echo "══════════════════════════════════════════════════"; echo "  $1"; echo "══════════════════════════════════════════════════"; }
COMMENT() { echo "  # $*"; }

FILTER="${1:-}"

# ──────────────────────────────────────────────────────────────────────────────
# 01 — Hello, Stream!
# ──────────────────────────────────────────────────────────────────────────────
if [[ -z "$FILTER" || "$FILTER" == "01" ]]; then
    TITLE "01 — Hello, Stream!"
    COMMENT "The simplest program: one gyge, one edge, one print."
    COMMENT "Expected output: Hello, Stream!"
    RUN python -m stream run examples/01_hello.stream
fi

# ──────────────────────────────────────────────────────────────────────────────
# 02 — Pipeline
# ──────────────────────────────────────────────────────────────────────────────
if [[ -z "$FILTER" || "$FILTER" == "02" ]]; then
    TITLE "02 — Pipeline"
    COMMENT "Multi-step chain: value → upper → print"
    COMMENT "Expected output: STREAM LANGUAGE IS REACTIVE"
    RUN python -m stream run examples/02_pipeline.stream
fi

# ──────────────────────────────────────────────────────────────────────────────
# 03 — Counter
# ──────────────────────────────────────────────────────────────────────────────
if [[ -z "$FILTER" || "$FILTER" == "03" ]]; then
    TITLE "03 — Counter"
    COMMENT "Numeric value → str → print"
    COMMENT "Expected output: 7"
    RUN python -m stream run examples/03_counter.stream
fi

# ──────────────────────────────────────────────────────────────────────────────
# 04 — Lossy stream (two entropy levels)
# ──────────────────────────────────────────────────────────────────────────────
if [[ -z "$FILTER" || "$FILTER" == "04" ]]; then
    TITLE "04 — Lossy stream"
    COMMENT "At entropy 0 the message almost always arrives:"
    COMMENT "Expected output: maybe you'll see this"
    RUN python -m stream run examples/04_lossy.stream
fi

# ──────────────────────────────────────────────────────────────────────────────
# 05 — Error handling
# ──────────────────────────────────────────────────────────────────────────────
if [[ -z "$FILTER" || "$FILTER" == "05" ]]; then
    TITLE "05 — Error handling"
    COMMENT "Value routed over -!-> error stream to |print|"
    COMMENT "Expected output: -1"
    RUN python -m stream run examples/05_error_handling.stream
fi

# ──────────────────────────────────────────────────────────────────────────────
# Obfuscation demo
# ──────────────────────────────────────────────────────────────────────────────
if [[ -z "$FILTER" || "$FILTER" == "obfuscate" ]]; then
    TITLE "Obfuscation demo"
    COMMENT "The .st files are level-3 obfuscated versions of each .stream file."
    COMMENT "You can view one with:"
    echo "  cat examples/01_hello.st"
    echo
    COMMENT "Obfuscate 01_hello.stream at level 3:"
    RUN python -m stream obfuscate examples/01_hello.stream --level 3
    echo
    COMMENT "Deobfuscate back:"
    RUN python -m stream deobfuscate examples/01_hello.st
    echo
    COMMENT "Try level 7 (hex-encoded strings) on example 02:"
    RUN python -m stream obfuscate examples/02_pipeline.stream --level 7
fi
