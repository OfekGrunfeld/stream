---
title: Obfuscator
description: Bidirectional human-readable ↔ glyph-form transformation at levels 0–9.
---

# Obfuscator

The obfuscator converts Stream source into a *fucked form* — semantically identical Unicode-heavy source that is mechanically reversible.  The transformation is bijective: `deobfuscate(obfuscate(src)) == src` for all levels.

---

## Levels

| Level | What is replaced |
|-------|-----------------|
| `0` | Identity — no change |
| `1–2` | Stream operators + delimiters (`\|name\|` → `⌈name⌉`, `->` → `⟶`, …) |
| `3–4` | + Keywords and modifiers (`::` → `§`, `:=` → `≔`, `$S` → `𝕊`, …) |
| `5–6` | + Identifiers scrambled (deterministic Unicode glyph sequences) |
| `7–8` | + String literals hex-encoded (`"hello"` → `0x68_65_6c_6c_6f`) |
| `9` | All of the above + all whitespace stripped |

---

## Examples

### Level 3

```stream
::header::
    <o-> "hello"

::body::
    |greeting| := "Hello, Stream!"
    |greeting| -> |print|
```

becomes:

```
§header§
    ⊙⟶ "hello"

§body§
    ⌈greeting⌉ ≔ "Hello, Stream!"
    ⌈greeting⌉ ⟶ ⌈print⌉
```

### Level 7

Strings are hex-encoded on top of the level-3 substitutions:

```
§body§
    ⌈greeting⌉ ≔ 0x48_65_6c_6c_6f_2c_20_53_74_72_65_61_6d_21
    ⌈greeting⌉ ⟶ ⌈print⌉
```

### Level 9

Whitespace is stripped entirely:

```
§header§⊙⟶0x68_65_6c_6c_6f§body§⌈⋮⋯⌉≔0x48_65_6c_6c_6f_2c_20_53_74_72_65_61_6d_21⌈⋮⋯⌉⟶⌈⋷⋸⌉
```

(identifiers are scrambled glyphs at level 9)

---

## Operator glyph table

| Human | Fucked |
|-------|--------|
| `->` | `⟶` |
| `=>` | `⟹` |
| `~>` | `≀⟶` |
| `-x>` | `⟶̸` |
| `-!->` | `↯` |
| `-!!->` | `↯↯` |
| `-?->` | `↯⃝` |
| `-*->` | `⊛⟶` |
| `-?*->` | `⊛⃝⟶` |
| `-#->` | `⊞⟶` |
| `-...->` | `⋯⟶` |
| `==>` | `⇶` |
| `<~` | `↫` |
| `&->` | `⊕⟶` |
| `-,->` | `⌛⟶` |
| `-+>` | `⟶₁` |
| `->>` | `⟹⟹` |

---

## Keyword / delimiter glyph table

| Human | Fucked |
|-------|--------|
| `<o->` | `⊙⟶` |
| `<o>` | `⊙` |
| `<o/` | `⊢` |
| `<o\` | `⊣` |
| `::` | `§` |
| `:=` | `≔` |
| `...` | `⋯` |
| `$S` | `𝕊` |
| `$C` | `℃` |
| `$@` | `⌚` |
| `$entropy` | `∿` |
| `\|name\|` | `⌈name⌉` |
| `><name><` | `≺name≻` |
| `[name]` | `⟦name⟧` |
| `<-- … -->` | `⟨⟨ … ⟩⟩` |

---

## Identifier scrambling (levels 5+)

At level 5 each identifier inside `⌈…⌉` delimiters is replaced with a deterministic sequence of characters from:

```
⋮⋯⋰⋱⋲⋳⋴⋵⋶⋷⋸⋹⋺⋻⋼⋽⋾⋿
```

The mapping is seeded by an integer (`seed=0` by default), making obfuscation reproducible.  The symbol table (a `dict[str, str]` mapping original→scrambled name) is returned alongside the obfuscated source and must be retained to deobfuscate.

---

## Python API

```python
from stream.obfuscator import obfuscate, deobfuscate, ObfuscatorResult

# Obfuscate
result: ObfuscatorResult = obfuscate(source, level=5, seed=42)
print(result.source)        # obfuscated text
print(result.symbol_table)  # {original: scrambled, ...}

# Deobfuscate (levels 1–4: no table needed)
plain = deobfuscate(result.source)

# Deobfuscate with symbol table (levels 5+)
plain = deobfuscate(result.source, symbol_table=result.symbol_table, seed=42)
```

### `ObfuscatorResult`

| Field | Type | Description |
|-------|------|-------------|
| `source` | `str` | Obfuscated source text |
| `level` | `int` | Level applied (0–9) |
| `symbol_table` | `dict[str, str]` | Original→scrambled name map (levels 5+, otherwise `{}`) |

---

## CLI

```bash
# Obfuscate at level 7
uv run python -m stream obfuscate hello.stream --level 7 --output hello.st

# Deobfuscate (levels 1–4)
uv run python -m stream deobfuscate hello.st

# Deobfuscate with symbol table (levels 5+)
uv run python -m stream deobfuscate hello.st --symbol-table symbols.json
```

---

## `.stream` vs `.st`

By convention:

| Extension | Form |
|-----------|------|
| `.stream` | Human-readable source |
| `.st` | Obfuscated / fucked form |

Both are valid input to `stream run` — the runtime always operates on human-readable form, so `.st` files are display/distribution artifacts rather than executable inputs.
