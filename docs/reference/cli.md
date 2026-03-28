---
title: CLI Reference
description: Full reference for all stream CLI commands.
---

# CLI reference

The Stream CLI is exposed via `python -m stream`.

```bash
uv run python -m stream [OPTIONS] COMMAND [ARGS]...
```

---

## `run`

Execute a Stream source file.

```bash
uv run python -m stream run <file> [--tick-limit N] [--no-hud]
```

| Argument / Flag | Default | Description |
|-----------------|---------|-------------|
| `file` | required | Path to `.stream` source file |
| `--tick-limit N` | 100 000 | Safety cap — program exits after N ticks if not already drained |
| `--no-hud` | off | Suppress the Rich HUD; only program output is printed |

The HUD renders one table per tick with:

- Entropy bar (coloured by tier), season, temperature, and wind
- Node table: name, shape, activation state, input/output queue depths
- Edge table: stream kind, edge state, buffer depth, back-edge flag

The final panel shows termination reason, exit code, tick count, and final entropy.

---

## `lex`

Tokenise a source file and print the token stream.

```bash
uv run python -m stream lex <file>
```

Each line of output shows the token kind, raw value, line number, and column.  Useful for debugging lexer edge cases.

---

## `parse`

Parse a source file and print the Abstract Syntax Graph as a pretty-printed dict.

```bash
uv run python -m stream parse <file>
```

The output reflects the internal `ProgramASG` structure:

- `sections`: list of `Section` objects (header, body, etc.)
- Each section contains a list of statements (`AssignStmt`, `StreamEdge`, `EntryPointStmt`, …)
- `nodes`: all `GygeNode` objects
- `edges`: all `StreamEdge` objects

---

## `obfuscate`

Transform a `.stream` file into glyph form.

```bash
uv run python -m stream obfuscate <file> [--level N] [--seed N] [--output PATH]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--level N` | `5` | Obfuscation level 0–9 |
| `--seed N` | `0` | RNG seed for identifier scrambling (levels 5+) |
| `--output PATH` | `<stem>.obf.stm` | Output file path |

---

## `deobfuscate`

Restore a glyph-form file to human-readable Stream source.

```bash
uv run python -m stream deobfuscate <file> [--symbol-table PATH] [--seed N] [--output PATH]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--symbol-table PATH` | none | JSON file mapping scrambled identifiers back to originals (required for levels 5+) |
| `--seed N` | `0` | RNG seed (must match the seed used during obfuscation) |
| `--output PATH` | `<stem>.readable.stm` | Output file path |

For levels 1–4 no symbol table is needed — all substitutions are deterministic and reversible from the glyph table alone.
