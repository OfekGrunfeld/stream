---
title: Overview
description: Core concepts of the Stream language — gyges, edges, sections, entropy, and termination.
---

# Overview

## Program structure

Every Stream program is divided into named *sections* using the `::name::` sigil.

```stream
::header::
    <o-> "my_program"
    $S := spring

::body::
    |x| := 42
    |x| -> |print|
```

Two sections are recognised by the runtime:

| Section | Purpose |
|---------|---------|
| `::header::` | Metadata and modifiers (name, season, initial entropy) |
| `::body::` | Graph topology — gyge declarations and stream edges |

---

## Gyges

A *gyge* is the single unit of computation in Stream.  Its shape is resolved lazily on first activation:

| Shape | Description | Example |
|-------|-------------|---------|
| `VARIABLE` | Stores and forwards a scalar value | `\|x\| := 42` |
| `FUNCTION` | Transforms input, emits output | `\|str\|` (built-in) |
| `BYTES` | Raw byte buffer | `\|buf\| := b"..."` |
| `PROGRAM` | Reference to a running process | `\|self\| := <o>` |
| `VOID` | Explicit sink; discards all input | `\|sink\| := ...` |

Gyge syntax: `|name|` — the name is surrounded by pipe characters.

### Hint prefixes

A hint character after the opening `|` signals an intended shape to the type registry:

| Prefix | Hint |
|--------|------|
| `%` | function |
| `@` | program/process target |
| `~` | lossy |
| `?` | conditional |
| `!` | error path |
| `#` | batch |

```stream
|%transform| := ...   <-- hinted as function
```

---

## Stream edges

Stream edges are the arrows between gyges.  The full catalogue is in the [operators reference](../reference/operators.md); a summary of the most common:

```stream
|a| -> |b|        <-- basic: unconditional, entropy-aware delivery
|a| => |b|        <-- priority: delivered before basic edges
|a| ~> |b|        <-- lossy: packets dropped proportionally to entropy
|a| -!-> |b|      <-- error: signals a fault condition
|a| -!!-> |b|     <-- exit: terminates the program
|a| <~ |b|        <-- feedback: back-edge, creates a cycle
```

---

## Entropy

Entropy (`Ch`, Chaos) is a first-class runtime value ranging from **0** (perfectly ordered) to **100** (full chaos).

- Starts at `entropy_initial` (default **15 Ch**).
- Fluctuates every tick based on graph activity.
- Capped at `entropy_cap` (default **85 Ch**).
- Raising the cap to **100** enables *Terminal Cascade* — when entropy hits 100 all buffered packets are corrupted and the program terminates.

Set initial entropy in the header:

```stream
::header::
    $entropy := 30
```

### Entropy tiers

| Range | Tier | Effect |
|-------|------|--------|
| 0–20 | DORMANT | Near-perfect delivery |
| 21–40 | CALM | Slight jitter |
| 41–60 | ACTIVE | Occasional packet corruption |
| 61–80 | TURBULENT | Notable loss on lossy edges |
| 81–99 | CRITICAL | High corruption, frequent drops |
| 100 | CASCADE | Terminal Cascade fires (cap must equal 100) |

---

## Seasons

A *season* sets the atmospheric modifier that shapes entropy physics.

```stream
::header::
    $S := spring    <-- or summer, autumn, winter
```

| Season | Entropy bias |
|--------|-------------|
| `spring` | Moderate, stable |
| `summer` | High baseline, volatile |
| `autumn` | Decreasing over time |
| `winter` | Low, cold, predictable |

Seasons can be locked (`$S := spring`) or drift freely (omit `$S`).

---

## Termination

The runtime loop ends for one of four reasons:

| Reason | Trigger |
|--------|---------|
| `NATURAL_DRAIN` | All edges empty and no pending output for 3 consecutive ticks |
| `EXIT_STREAM` | A packet reaches a `-!!->` edge |
| `TERMINAL_CASCADE` | Entropy reaches 100 while `entropy_cap == 100` |
| `TICK_LIMIT` | Safety cap reached (default 100 000 ticks) |

---

## Comments

```stream
<-- This is a comment (single or multiline) -->

<-- Everything between the arrow pairs
    is stripped before lexing. -->
```

---

## The 9-phase tick loop

Every tick executes these phases in order:

| Phase | Name | What it does |
|-------|------|--------------|
| 0 | Entropy Recalculation | Compute entropy delta, emit entropy events |
| 1 | Modifier Application | Apply season / temperature / wind effects |
| 2 | Parasite Lifecycle | Advance `==>` parasite gyges |
| 3 | Edge Delivery | Move packets from source output ports to destination input ports |
| 4 | Node Activation | Call fn bodies, store variable values, resolve lazy shapes |
| 5 | Entropy Event Resolution | Apply queued entropy events (highest impact first) |
| 6 | Signal Processing | Handle `-*->` / `-?*->` signal/receive edges |
| 7 | Wait Resolution | Resolve `-,->` wait-stream conditions |
| 8 | Graph Mutation | Execute queued structural graph changes |
| 9 | Garbage Collection | Remove drained edges and orphaned nodes |
