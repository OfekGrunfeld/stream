---
title: Usage
description: Running, inspecting, and obfuscating Stream programs from the CLI.
---

# Usage

All commands are invoked through the `stream` package:

```bash
uv run python -m stream <command> [options] <file>
```

---

## `run` — Execute a program

```bash
uv run python -m stream run examples/01_hello.stream
```

The HUD is printed every tick showing entropy, node states, and edge buffers.  The program terminates with one of four reasons printed in a summary panel.

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `--tick-limit N` | 100 000 | Maximum ticks before forced exit |
| `--no-hud` | — | Suppress the Rich HUD (useful for scripting) |

### Exit codes

| Code | Meaning |
|------|---------|
| `0` | Natural drain or exit stream with code 0 |
| `1` | File not found / parse error |
| `99` | Terminal cascade |
| other | Value carried by `-!!->` packet |

---

## `lex` — Inspect tokens

Tokenise a file and print the flat token stream.  Useful when debugging lexer behaviour or learning the grammar.

```bash
uv run python -m stream lex examples/01_hello.stream
```

```
SECTION        'header'     line=13 col=1
ENTRY_POINT    '<o->'       line=14 col=5
STRING         'hello'      line=14 col=10
SECTION        'body'       line=17 col=1
GYGE           'greeting'   line=18 col=5
ASSIGN         ':='         line=18 col=16
STRING         'Hello, ...' line=18 col=19
GYGE           'greeting'   line=19 col=5
STREAM_BASIC   '->'         line=19 col=16
GYGE           'print'      line=19 col=19
EOF                         line=20 col=1
```

---

## `parse` — Inspect the ASG

Parse a file and print the Abstract Syntax Graph as JSON.

```bash
uv run python -m stream parse examples/02_pipeline.stream
```

The output is the `ProgramASG` dataclass serialised to a pretty-printed dict, showing all sections, nodes, edges, and header statements.

---

## `obfuscate` — Transform to glyph form

```bash
uv run python -m stream obfuscate examples/01_hello.stream --level 3
```

Writes an obfuscated copy to `<stem>.obf.stm` by default.  Use `--output` to specify a path.

```bash
uv run python -m stream obfuscate examples/01_hello.stream --level 7 --output out.st
```

Obfuscation levels:

| Level | What changes |
|-------|-------------|
| 0 | Identity — no change |
| 1–2 | Operators + delimiters replaced with Unicode glyphs |
| 3–4 | Keywords and modifiers also replaced |
| 5–6 | Identifiers scrambled (deterministic, seed-based) |
| 7–8 | String literals hex-encoded |
| 9 | All of the above + whitespace stripped |

See the [Obfuscator reference](../reference/obfuscator.md) for full details.

---

## `deobfuscate` — Restore human-readable form

```bash
uv run python -m stream deobfuscate examples/01_hello.st
```

For levels 1–4 no extra input is needed.  For levels 5–9 (scrambled identifiers) pass the symbol table JSON produced during obfuscation:

```bash
uv run python -m stream deobfuscate out.st --symbol-table symbols.json
```

---

## Example programs

The `examples/` directory contains five annotated programs:

| File | Demonstrates |
|------|-------------|
| `01_hello.stream` | Minimal program — one gyge, one edge |
| `02_pipeline.stream` | Multi-step chain: `\|sentence\| -> \|upper\| -> \|print\|` |
| `03_counter.stream` | Numeric value through `\|str\| -> \|print\|` |
| `04_lossy.stream` | `~>` lossy edge — probabilistic packet drop |
| `05_error_handling.stream` | `-!->` error stream routing |

Run them all with:

```bash
bash examples/run.sh
```

Or run a single example:

```bash
bash examples/run.sh 02
```
