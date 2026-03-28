---
title: Header Configuration
description: All statements valid inside the ::header:: section.
---

# Header configuration

The `::header::` section sets program-level metadata and runtime knobs.  All statements are optional.

---

## `<o->` — Program name

Declares the entry-point name for this program.

```stream
::header::
    <o-> "my_program"
```

The string is informational; it appears in the HUD title.

---

## `$S` — Season

Sets the season modifier that shapes entropy physics.

```stream
::header::
    $S := spring
```

| Value | Entropy bias |
|-------|-------------|
| `spring` | Moderate, stable — good default |
| `summer` | High baseline, volatile |
| `autumn` | Entropy trends downward |
| `winter` | Low, cold, predictable |

Omitting `$S` lets the season drift naturally (currently defaults to winter physics).

---

## `$entropy` — Initial entropy

Sets the starting entropy value in Ch (Chaos units, 0–100).

```stream
::header::
    $entropy := 30
```

Default: **15.0 Ch**.

Higher starting entropy means more packet loss and corruption from the first tick.

---

## `$C` — Temperature modifier

Sets an explicit temperature offset in Fx (Flux units).

```stream
::header::
    $C := 72
```

Temperature influences the entropy delta computation each tick.  Positive temperature adds upward pressure on entropy; negative temperature cools the system.

---

## `$@` — Time modifier

Sets the time-of-day modifier.

```stream
::header::
    $@ := 14
```

Time affects how entropy events are weighted during Phase 5.

---

## `<o/>` / `<o\>` — Alloc / Dealloc

Pre-allocate or pre-deallocate named resources.

```stream
::header::
    <o/> "buffer_pool"
    <o\> "stale_cache"
```

---

## Full example

```stream
::header::
    <o-> "chaos_demo"
    $S := summer
    $entropy := 50
    $C := 80
```

This starts the program at 50 Ch entropy, with summer physics (high volatility) and an elevated temperature, resulting in rapid entropy growth toward the cap.
