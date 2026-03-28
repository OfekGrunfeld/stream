---
title: Stream
description: A reactive dataflow esolang where programs are pipelines and entropy is a runtime primitive.
---

# Stream

**Stream** is a reactive dataflow esoteric language where the only unit of computation is a *gyge* — a named node that holds a value, transforms it, or sinks it — and programs are described entirely as flow graphs.

```stream
::header::
    <o-> "hello"

::body::
    |greeting| := "Hello, Stream!"
    |greeting| -> |print|
```

**Expected output**

```
Hello, Stream!
```

---

## What makes Stream different

| Concept | Description |
|---------|-------------|
| **Single type** | Everything is a *gyge* — variable, function, or sink |
| **Left-to-right flow** | `\|a\| -> \|b\| -> \|c\|` is the core expression form |
| **20 stream operators** | `->` `=>` `~>` `-!->` `-!!->` `<~` and 14 more |
| **Entropy** | A runtime value (0–100 Ch) that influences delivery, corruption, and termination |
| **Seasons** | Program-level modifiers (`spring`, `summer`, `autumn`, `winter`) that shift entropy physics |
| **Obfuscation** | Source can be mechanically transformed into a glyph-dense *fucked form* at levels 0–9 |

---

## Quick links

<div class="grid cards" markdown>

- **[Install →](guide/install.md)**
  Get Stream running with `uv`.

- **[Overview →](guide/overview.md)**
  Core concepts: gyges, edges, entropy.

- **[Usage →](guide/usage.md)**
  Run, lex, parse, obfuscate from the CLI.

- **[Stream operators →](reference/operators.md)**
  All 20 edge types with syntax and semantics.

- **[Built-in gyges →](reference/builtins.md)**
  `print`, `upper`, `str`, `len`, and friends.

- **[Obfuscator →](reference/obfuscator.md)**
  Levels 0–9, symbol tables, round-trip deobfuscation.

</div>
