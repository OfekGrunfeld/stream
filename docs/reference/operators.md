---
title: Stream Operators
description: All 20 stream edge types — syntax, semantics, and obfuscated glyph forms.
---

# Stream operators

Stream edges are written between two gyges.  The operator determines *how* packets travel.

```stream
|source| <operator> |destination|
```

---

## Basic transport

### `->` — Basic stream

The default edge.  Packets are delivered with entropy-aware reliability (very high at low entropy, still mostly reliable up to ~80 Ch).

```stream
|a| -> |b|
```

Obfuscated form: `⟶`

---

### `=>` — Priority stream

Packets on priority edges are delivered *before* all basic edges in Phase 3.  Useful for control messages that must arrive first.

```stream
|control| => |handler|
```

Obfuscated form: `⟹`

---

### `~>` — Lossy stream

Packets are dropped probabilistically.  Drop probability scales with entropy: near-zero at 0 Ch, approaching 100 % at 100 Ch.

```stream
|sensor| ~> |aggregator|
```

Obfuscated form: `≀⟶`

---

### `-x>` — Blocked stream

Packets are never delivered regardless of entropy.  Used to model a connection that has been administratively closed.

```stream
|a| -x> |b|
```

Obfuscated form: `⟶̸`

---

## Flow control

### `-+>` — Throttle stream

Limits delivery rate.  Each additional `+` adds one stage of throttling.  `-+>` is level 1, `-++>` is level 2, etc.

```stream
|producer| -+> |consumer|     <-- throttle level 1
|producer| -++> |consumer|    <-- throttle level 2
```

Obfuscated form: `⟶₁`, `⟶₂`, …

---

### `->>` — Fast stream

Accelerates delivery.  Each additional `>` increases the speed multiplier.  `->>` is ×2, `->->` is ×3, etc.

```stream
|critical| ->> |handler|
```

Obfuscated form: `⟹⟹` (repeated per level)

---

### `<~` — Feedback stream

Back-edge that feeds a destination's output back to a source.  Creates a cycle in the dataflow graph.  Evaluated after forward edges each tick.

```stream
|accumulator| -> |output|
|output| <~ |accumulator|
```

Obfuscated form: `↫`

---

### `==>` — Parasite stream

Attaches a *parasite gyge* to the edge between source and destination.  The parasite observes packets without consuming them and can inject side effects.

```stream
|data| ==> |logger|
```

Obfuscated form: `⇶`

---

## Filtering and routing

### `-/>` — Filter stream

Delivers only packets for which a predicate returns truthy.  The predicate is evaluated by the destination node's resolver.

```stream
|numbers| -/> |positive_sink|
```

Obfuscated form: `⊣⟶`

---

### `-/|cond|\->` — Conditional filter stream

Like `-/>` but carries an explicit condition gyge inline.

```stream
|values| -/|is_even|\-> |even_sink|
```

Obfuscated form: `⋈⟶`

---

### `-#->` — Batcher stream

Accumulates packets until a batch size threshold is reached, then delivers the batch as a single list packet.

```stream
|events| -#-> |batch_handler|
```

Obfuscated form: `⊞⟶`

---

### `-...->` — Splitter stream

The inverse of batcher.  Takes a single iterable packet and emits each element as an individual packet.

```stream
|list_value| -...-> |item_handler|
```

Obfuscated form: `⋯⟶`

---

### `-?*->` — Receive stream

Passive listener.  Waits for a matching signal from any source tagged with `@*` (broadcast) or a specific target.

```stream
|listener| -?*-> |dispatcher|
```

Obfuscated form: `⊛⃝⟶`

---

### `&->` — Compose stream

Fuses the output of two gyges into a tuple packet before forwarding.

```stream
|a| &-> |b|
```

Obfuscated form: `⊕⟶`

---

## Error handling

### `-!->` — Error stream

Routes packets that represent fault conditions.  The receiving gyge is expected to handle or log the error.

```stream
|computation| -!-> |error_handler|
```

Obfuscated form: `↯`

---

### `-!!->` — Exit stream

When a packet arrives on this edge the program terminates immediately.  The packet value becomes the exit code.

```stream
|result| -!!-> |done|
```

Obfuscated form: `↯↯`

---

### `-?->` — Catch stream

Intercepts error packets before they propagate further.  Acts as a recovery path from an upstream `-!->`.

```stream
|risky| -!-> |fallback|
|fallback| -?-> |output|
```

Obfuscated form: `↯⃝`

---

## Signals

### `-*->` — Signal stream

Broadcasts a packet to one or more target processes identified by a target sigil (`@pid:`, `@port:`, `@name:`, `@*`).

```stream
|event| -*-> @*
```

Obfuscated form: `⊛⟶`

---

## Waiting

### `-,->` — Wait stream

Suspends delivery until a condition is satisfied.  Multiple commas add wait stages: `-, ,->` waits through two stages before delivering.

```stream
|deferred| -,-> |processor|
```

Obfuscated form: `⌛⟶`

---

## Summary table

| Syntax | Kind | Obfuscated |
|--------|------|-----------|
| `->` | basic | `⟶` |
| `=>` | priority | `⟹` |
| `~>` | lossy | `≀⟶` |
| `-x>` | blocked | `⟶̸` |
| `-+>` | throttle | `⟶₁` |
| `->>` | fast | `⟹⟹` |
| `<~` | feedback | `↫` |
| `==>` | parasite | `⇶` |
| `-/>` | filter | `⊣⟶` |
| `-/\|c\|\->` | filter-cond | `⋈⟶` |
| `-#->` | batcher | `⊞⟶` |
| `-...->` | splitter | `⋯⟶` |
| `-?*->` | receive | `⊛⃝⟶` |
| `&->` | compose | `⊕⟶` |
| `-!->` | error | `↯` |
| `-!!->` | exit | `↯↯` |
| `-?->` | catch | `↯⃝` |
| `-*->` | signal | `⊛⟶` |
| `-,->` | wait | `⌛⟶` |
