# Stream — Language Overview

> "Code that infects. The runtime is alive. So is your program."

Stream is an esoteric programming language inspired by brainfuck and maze — ultra minimal but
somehow sophisticated. It is designed as a security language: programs *stream into* other running
programs on the computer while executing. The runtime is adversarial. The environment is a climate.
Process injection is syntax.

---

## Mechanism Files

Each core mechanism of the language has its own dedicated file:

| File | Mechanism | Summary |
|------|-----------|---------|
| [parasites.md](parasites.md) | **Parasites** | Gyges that escape into other processes — targeting, lifecycle, capabilities, spread |
| [entropy.md](entropy.md) | **Entropy** | The chaos seed (0–100 Ch) — sources, sinks, stream effects, difficulty curve |
| [modifiers.md](modifiers.md) | **Modifiers** | Seasons, temperature, wind, environmental disasters |
| [streams.md](streams.md) | **Streams** | All stream operators — semantics, behavior, entropy effects |
| [gyge.md](gyge.md) | **Gyge** | The only type — shapes, syntax, resolution, composition |
| [evaluation-model.md](evaluation-model.md) | **Evaluation Model** | Reactive dataflow graph, tick phases, runtime architecture |
| [obfuscator.md](obfuscator.md) | **Obfuscator** | Two-way human-readable ↔ fucked syntax conversion |
| [vision.md](vision.md) | **Vision** | Positioning, taglines, personas, community, identity |
| [syntax.md](syntax.md) | **Syntax Reference** | All operators and syntax in one place |

---

## Core Concepts (Summary)

### Parasites

Core parts of the language — variables, functions — that escape into other running programs.
They hook the host for higher scheduling and network priority, observe and intercept its data,
and spread entropy. Can be created voluntarily (`==>`) or spawned automatically by modifiers.
Parasites amplify entropy; modifier-created parasites are aggressive and cannot be recalled.

→ See [parasites.md](parasites.md)

### Entropy

Measured in Churn (Ch), range 0–100. The runtime's chaos seed. Higher entropy = more disasters,
more parasites, more stream degradation, higher wind. It makes the runtime feel like a survival game.
Entropy is a resource to budget and spend — not an error condition to suppress.

At 100 Ch: Terminal Cascade. 5 ticks to recover or the runtime collapses.

→ See [entropy.md](entropy.md)

### Modifiers

Nature-themed conditions that mechanically alter stream behavior in real time:
- **Seasons** — entropy attractors that define the runtime's ambient chaos level
- **Temperature** — derived from season + stream load + entropy; affects throughput and reliability
- **Wind** — affects stream routing direction and distribution
- **Disasters** — floods, rockslides, lightning, parasite blooms, droughts, glaciers

→ See [modifiers.md](modifiers.md)

### Streams

The only data-movement primitive. Programs are graphs of typed stream edges connecting gyge nodes.
16 stream types ranging from reliable (`->`) to parasitic (`==>`), each with distinct behavior
that degrades under entropy in defined ways.

→ See [streams.md](streams.md)

### Gyge

The only type. Can be a variable, function, class, program, mock, bytes, or garbage. Shape is
determined lazily at first activation — never at parse time. Named with pipe delimiters: `|name|`.

→ See [gyge.md](gyge.md)

### Evaluation Model

Reactive dataflow graph with actor-isolated gyge nodes. A background runtime loop advances through
9 tick phases: entropy recalculation, modifier application, parasite lifecycle, edge delivery, node
activation, entropy event resolution, signal processing, wait resolution, graph mutation, and garbage
collection. The same entropy seed always produces the same execution trace.

→ See [evaluation-model.md](evaluation-model.md)

### Obfuscator

Two-way lossless converter between human-readable and "fucked" syntax. 10 obfuscation levels (0–9)
controlled by entropy setting. At Level 9: all whitespace stripped, identifiers scrambled, strings
hex-encoded, a continuous glyph stream indistinguishable from noise.

→ See [obfuscator.md](obfuscator.md)

---

## Status

Language is in active design/planning phase. Implementation has not begun.
A human-readable POC interpreter exists in `~/projects/stream`.

Next steps per mechanism file are tracked individually. Use each file as the briefing document when
running agents to expand that mechanism further.
