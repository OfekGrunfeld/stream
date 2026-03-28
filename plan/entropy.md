# Entropy

Entropy is Stream's central chaos variable. It is not a difficulty slider tacked onto an otherwise normal
runtime — it is the runtime's *nervous system*. Every stream, every gyge, every modifier, every parasite
is wired into entropy. The higher it climbs, the more the environment stops cooperating.

The programming model entropy implies: **you don't fight chaos — you design for it.**
Programs that treat entropy as an error condition die in Act III. Programs that treat it as a resource
survive into Act V and use it as fuel.

---

## Scale

Entropy is measured in **Churn (Ch)**, a floating-point value from **0.0 to 100.0**.

| Tier | Range (Ch) | Terminal Symbol | Character |
|------|-----------|----------------|-----------|
| Dormant | 0–9.9 | `~~~~~~~~~~~~~~~~~` (deep blue) | Frozen. Nothing moves. Streams do not flow. |
| Calm | 10–24.9 | `~~~~~~~~~~~~~~~~~` (cyan) | Clear water. Streams reliable. Parasites dormant. |
| Stirring | 25–39.9 | `≈≈≈≈~≈≈≈≈~≈≈≈≈` (green) | First misfires. Sliding rocks. Parasites waking. |
| Turbulent | 40–59.9 | `≈≈≈≋≈≋≈≈≈≋≈` (yellow) | Floods possible. Rockslides frequent. Parasites feeding. |
| Volatile | 60–74.9 | `≋≋≋≋≈≋≋≋≋` (orange) | Parasite blooms. Lightning. Error cascades. |
| Chaotic | 75–89.9 | `⁓⁓≋⁓⁓≋⁓⁓` (red) | Runtime fights back. All defenses degrading. |
| Apocalyptic | 90–100 | `⁓⁓⁓⁓⁓⁓⁓⁓` (crimson, blinking) | Barely cohesive. Parasites autonomous. |

**Default starting entropy**: 15.0 Ch (low Calm — enough to feel alive without punishing immediately).

**Hard cap** (SDK-configurable): 85.0 Ch by default. Raising to 100.0 enables Terminal Cascade.

**Practical minimum**: 5.0 Ch. True zero is a special **Glacial** state — streams do not flow at all.
Not the same as low entropy; it is heat death.

### Terminal Cascade

When entropy hits 100.0 Ch, the runtime enters Terminal Cascade:

```
╔════════════════════════════════════════════════════╗
║  TERMINAL CASCADE INITIATED  [E: 100.0 Ch]        ║
║  Runtime coherence failing. 5 ticks remaining.    ║
║  ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░░░░░░░░░░  ║
╚════════════════════════════════════════════════════╝
```

5 ticks to drop below 95.0 Ch or the runtime collapses. Outbound parasites are marked `AUTONOMOUS`
on collapse — they continue spreading indefinitely with no tether to the dead origin.

---

## Sources (What Raises Entropy)

### Continuous Stream Activity

Every active stream contributes baseline Churn simply by existing:

| Condition | Rate |
|----------|------|
| Any active stream | +0.05 Ch/tick |
| Stream under heavy data load | +0.05–0.15 Ch/tick (scaled by load) |
| Stream in backpressure (queued but not draining) | +0.3 Ch/tick |

### Stream Type Premiums

Some stream types are inherently entropic:

| Stream | Premium | Reason |
|--------|---------|--------|
| `~>` Lossy | +0.1 Ch/tick | Data loss is disorder |
| `-+>` Throttled | +0.05 Ch/tick | Artificial restriction creates pressure |
| `->>` Fast | +0.2 Ch/tick | Speed introduces turbulence |
| `-...->` Splitter | +0.08 Ch/tick per branch beyond first | Divergence multiplies entropy |
| `-*->` Signal | +0.15 Ch/tick per signal fired | Out-of-band messages are chaotic |
| `-!->` Error | +0.25 Ch/tick | Errors are inherently disorderly |
| `-!!->` Exit | +0.5 Ch flat on invocation | Hard exits spike entropy briefly |

### Parasite Activity

| Event | Amount |
|-------|--------|
| Active parasite feeding (mutating stream data) | +0.4 Ch/tick |
| Active parasite dormant (present, not feeding) | +0.1 Ch/tick |
| Parasite successfully escaping to another process | +2.0 Ch flat spike |

### Environmental Events

| Event | Amount |
|-------|--------|
| Flood trigger | +5.0 Ch flat, then +0.5 Ch/tick while active |
| Rockslide trigger | +2.0 Ch flat |
| Lightning strike | +3.0 Ch flat |
| Parasite bloom: each spawned parasite | +1.0 Ch flat |
| Drought (complex) | −0.2 Ch/tick ambient, but stream damage generates +0.3 Ch/tick |

### Programmer-Caused Spikes

| Action | Cost |
|--------|------|
| Manually spawning a parasite | +3.0 Ch flat |
| Forcing a season change mid-run | +4.0 Ch flat |
| Sending a broadcast signal to unknown receivers | +1.0 Ch flat |
| Using `-!!->` exit stream | +0.5 Ch flat |

### Passive Time

+0.01 Ch/tick always, regardless of any other activity. The universe tends toward disorder.
A truly idle program will still drift upward over time.

---

## Sinks (What Lowers Entropy)

### Stream Completion

| Completion Type | Drain |
|----------------|-------|
| Clean completion (all data consumed, no errors) | −0.5 Ch flat |
| Clean completion + all downstream also clean | −0.8 Ch flat (cascade calm) |

### Active Stream States

| State | Rate |
|-------|------|
| `-x>` Blocked stream successfully containing data | −0.1 Ch/tick |
| `-,->` Wait stream in active wait (intentional stillness) | −0.15 Ch/tick |
| `-/>` Filter stream handling load without overflow | −0.05 Ch/tick |

### Error Handling

| Event | Drain |
|-------|-------|
| `-?->` catch successfully intercepts error | −0.3 Ch flat |
| Catch intercepts error that partially propagated | −0.1 Ch flat |

### Season Effects

Winter ambient: −0.2 Ch/tick. Deep Winter (already below 20 Ch during Winter): −0.5 Ch/tick.

### SDK Vent

| Property | Value |
|----------|-------|
| Max per call | −10.0 Ch |
| Default application | −0.5 Ch/tick over 20 ticks |
| Cooldown | 50 ticks between calls |
| During active disaster | Half effective (vent rate halved) |

---

## Per-Edge Entropy

In addition to global entropy, every edge maintains a **local entropy modifier** in the range [−0.2, +0.2].
The effective entropy seen by an edge's delivery policy is:

```
E_effective = clamp(E_global + E_local, 0.0, 100.0)
```

Per-edge entropy is raised by:
- Parasite attachment on or near the edge
- Being downstream of a `garbage`-shape gyge
- Being adjacent to a `-!->` error stream that is actively firing

Per-edge entropy is lowered by:
- Being a `=>` priority edge (small negative local modifier — partially protected)
- Being inside a season-guarded section that matches the current season

This dual-layer model allows a globally Calm runtime to have localized Chaotic pockets
(a parasitized subgraph), and a globally Chaotic runtime to have protected priority corridors.

---

## Stream Effects by Entropy Tier

How each stream type degrades as entropy climbs. "Low" = below 25 Ch, "Mid" = 25–60 Ch,
"High" = 60–80 Ch, "Extreme" = 80+ Ch.

| Stream | Low | Mid | High | Extreme |
|--------|-----|-----|------|---------|
| `->` Standard | Fully reliable | 2% tick-level delay | 8% delay, 2% reorder | 15% delay, 5% reorder, 3% spontaneous `~>` conversion/tick |
| `=>` Priority | Fully respected | Minor arrival jitter | 10% priority inversion per batch | 25% priority scramble; may behave as `->` |
| `~>` Lossy | Baseline loss rate | 1.5× baseline | 3× baseline | 5× baseline; may consume data from adjacent streams |
| `-/>` Filter | Fully accurate | 5% misfire | 15% misfire | 30% misfire; may invert completely for whole ticks |
| `-x>` Blocked | Block solid | Block holds | 5% leak per tick | 15% leak; floods can override entirely |
| `-+>` Throttle | Precise | ±10% rate variance | 10% burst chance (full speed for 1–2 ticks) | 25% burst chance; hot temp may cause permanent failure |
| `->>` Fast | Full speed | +0.2 Ch/tick | 5% overheating → `-!->` conversion/tick | 15% overheating; scorching temp = guaranteed failure within 10 ticks |
| `-/|\->` Switch | Deterministic | Wind 5+ adds 5% misrouting | 10% misrouting; may toggle randomly for 1 tick | 25% misrouting; may lock to one branch for 5–10 ticks |
| `-#->` Batcher | Correct batch size | ±1 item bleed | ±20% size variance; item duplication | Batch boundaries collapse; continuous stream |
| `-...->` Splitter | Even distribution | ±5% variance | ±20% variance; branches may starve | Chaotic; some branches get duplicates, others get nothing |
| `-!->` Error | Errors contained | +0.25 Ch/tick | 15% cascade to adjacent streams | 35% cascade; error-on-error chains possible |
| `-!!->` Exit | Executes cleanly | 1–2 tick delay | Signal may require re-sending (+0.5 Ch each) | Runtime may refuse to exit during active disaster |
| `-?->` Catch | Catches 100% | Catches 95% | Catches 80%; catch overload adds +0.1 Ch/tick | Catches 60%; catch itself may error at 10%/tick |
| `-*->` Signal | Delivered reliably | 1–3 tick delay | 5% duplicate, 5% lost | 70% delivery, 15% duplicate, 15% lost |
| `-?*->` Receive | No false positives | 2% phantom signal | 8% phantom, 5% miss | 20% phantom; may receive signals from parasites in other programs |
| `-,->` Wait | Precise | ±10% duration variance | 10% early wake (condition not met) | Floods actively drag wait streams out of waiting |

---

## The Five-Act Difficulty Curve

A Stream program run is a story shaped by entropy. Each act has a distinct feel, a dominant challenge,
and a key question that separates programmers who designed for this phase from those who didn't.

### Act I — The Calm (0–25 Ch)

The runtime cooperates. Streams are reliable. Filters are accurate. Parasites are dormant. Wind is a
gentle breeze. The programmer has full control and time to build deliberately.

This feels like the opening of a survival game: time to construct infrastructure, plan defensive
architecture, and establish clean stream pipelines before pressure arrives. But the entropy clock is
already ticking — stream activity itself generates slow upward drift. No one stays in Act I forever.

**The key question:** How efficiently can you build before the environment starts pushing back?

**The wrong instinct:** Assuming Act I is the normal state. It isn't. Design for Act III from the start.

### Act II — First Signs (25–40 Ch)

Small things go wrong. A standard stream occasionally delays a packet. A filter misfires on an edge case.
The first sliding rocks appear — a 5-tick blockage on a stream you thought was stable. Wind picks up.
A single parasite stirs from dormancy and begins probing for opportunities.

Each failure is individually manageable. But they compound. A delayed packet triggers downstream
backpressure. A filter misfire sends bad data to a gyge that wasn't expecting it. The programmer learns:
these streams are not independent. The system has emergent fragility.

**The key question:** Which streams are load-bearing enough to defend? What can you afford to let be lossy?

**The right move:** Begin installing catch streams, signal monitors, and priority guards on the critical path.

### Act III — The Pressure (40–60 Ch)

The runtime is now actively hostile. Floods are possible. Rockslides happen with noticeable frequency.
Temperature is climbing. Parasites are feeding. Fast streams are becoming dangerous — they contribute
heavily to entropy while growing unreliable.

Every defensive action has a cost. A catch stream that correctly intercepts errors drains entropy — but
an overloaded catch stream generates it. Filtering everything slows throughput, which builds backpressure,
which raises entropy. Wait streams calm the system but delay processing.

Act III is where architectures that weren't designed for entropy begin to collapse in cascades. Programs
with layered defenses hold — barely.

**The key question:** Can your architecture hold, or will you need to sacrifice parts of the program to save the whole?

**The right instinct:** Stop expanding. Consolidate. Triage. Let non-critical streams go lossy to preserve the critical path.

### Act IV — The Crisis (60–80 Ch)

The runtime is fighting you. Parasite blooms are spawning aggressive parasites. Lightning is corrupting
streams that were functioning correctly. The switch logic you rely on is misrouting. Error cascades are
spreading. The tools for fighting entropy are themselves degrading — catch streams miss 20% of errors;
wait streams wake early.

The programmer is now reactive. Every tick brings a new problem. The only path through Act IV is a
program that was designed from the beginning to degrade gracefully — to shed non-critical load when
the environment demands it.

**The key question:** Do you have enough defensive depth to survive until entropy peaks and begins to recede?

**The right instinct:** Pattern recognition. Identify which problems are entropy-caused (will self-resolve as entropy falls) vs. structural (require intervention). Don't fight both at once.

### Act V — The Edge (80–100 Ch)

If a program reaches this state, something has gone seriously wrong — or the programmer drove entropy
here deliberately. At this tier, parasites become maximally powerful and maximally uncontrollable.
Signals arrive from foreign parasites in other programs. The runtime is barely coherent.

Few legitimate programs operate here. This is the domain of chaos engineering, stress testing, and
programs that weaponize their own entropy: spawning parasite armies, using the runtime's instability
as a source of entropy for cryptographic purposes, or running controlled Terminal Cascade experiments.

**The key question:** Are you here by accident or by design? If by design — what did you come here to do before the runtime collapses?

**The philosophy of Act V:** The roguelike equivalent of a suicide run. You know you won't survive.
The question is how much you can accomplish before the end.

---

## SDK Control Surface

```
entropy.initial          = 15.0    // starting value; max 50.0 at init
entropy.cap              = 85.0    // hard ceiling (30.0–100.0); 100.0 enables Terminal Cascade
entropy.decay_rate       = 1.0     // multiplier on all sources (0.5 = easier, 2.0 = hard mode)
entropy.sink_rate        = 1.0     // multiplier on all sinks (1.5 = easier to cool down)
entropy.disaster_freq    = 1.0     // disaster probability multiplier; 0.0 = no disasters (debug mode)
entropy.parasite_rate    = 1.0     // parasite spawn multiplier; 0.0 = no parasites
entropy.wind_enabled     = true    // false removes wind effects (useful for routing logic testing)
entropy.season           = null    // lock a season, or null for natural cycling
entropy.season_duration  = 1000   // ticks per season (0 = season locked permanently)

entropy.vent(amount, duration)            // explicit entropy dump; max -10 Ch per call; 50-tick cooldown
entropy.on_threshold(level, callback)     // fire callback when entropy crosses a threshold
entropy.get()                             // read current Ch value
entropy.get_modifier_state()              // read season, temperature (Fx), wind, active disasters, active parasites
```

---

## Terminal Display (HUD)

Entropy has a persistent status bar in the terminal output — the runtime's HUD.

**Calm tier (15 Ch):**
```
STREAM RUNTIME  [E: 15.2 Ch] [CALM]  ~~~~~~~~~~~~~~~~~  Season: Winter  Wind: 2  Temp: 18 Fx
```

**Turbulent tier (48 Ch):**
```
STREAM RUNTIME  [E: 48.7 Ch] [TURBULENT]  ≈≈≈≈≈~≈≈≈~≈≈  Season: Summer  Wind: 5  Temp: 62 Fx
```

**Volatile tier (68 Ch):**
```
STREAM RUNTIME  [E: 68.3 Ch] [VOLATILE]  ≋≋≈≋≋≈≋≋  Season: Summer  Wind: 7  Temp: 79 Fx
PARASITE ACTIVE: |spy| feeding on stream_7
```

**Chaotic tier (83 Ch):**
```
STREAM RUNTIME  [E: 83.1 Ch] [CHAOTIC !!!]  ⁓⁓≋⁓⁓≋⁓  Season: Summer  Wind: 9  Temp: 91 Fx
DISASTER: FLOOD (tick 12/25 remaining)
PARASITE ACTIVE: |spy| feeding on stream_7
PARASITE ACTIVE: |bloom_4| escaped to external process
ERROR CASCADE: stream_9 -> stream_11 -> stream_14
```

**Terminal Cascade:**
```
╔════════════════════════════════════════════════════╗
║  TERMINAL CASCADE INITIATED  [E: 100.0 Ch]        ║
║  Runtime coherence failing. 5 ticks remaining.    ║
╚════════════════════════════════════════════════════╝
```

### Entropy Gauge (right-side vertical thermometer)

```
100 | █  ← Terminal Cascade
 90 | █
 80 | █
 70 |    ← Current (68 Ch)
 60 |
 50 |
 40 |
 30 |
 20 |
 10 |
  0 |
    Entropy (Ch)
```

Fill character by tier: `░` Calm, `▒` Turbulent, `▓` Volatile, `█` Chaotic/Apocalyptic.

---

## Design Principles

**Legibility**: The programmer always knows approximately why entropy is at its current level. The HUD
and event log provide enough signal to understand cause and effect. Entropy is never opaque.

**Controllability**: The programmer is never fully helpless. There are always tools (venting, catch
streams, wait streams, blocks) that can influence entropy. The system punishes laziness, not effort.

**Momentum**: Entropy should feel heavy. Easier to gain than to lose — especially at high tiers.
This creates the survival game's core tension: inaction compounds.

**Fairness**: Disasters are probabilistic, not arbitrary. A programmer who understands the system can
significantly reduce exposure to any given disaster. Knowledge and preparation are rewarded.

**Narrativity**: A program run should feel like a story. The entropy curve maps to rising tension,
crisis, and resolution — or collapse. Programs that survive feel earned. Programs that collapse feel
like tragedy, not random failure.
