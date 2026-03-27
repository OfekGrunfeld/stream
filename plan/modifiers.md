# Modifiers

Modifiers are the environmental layer of Stream's runtime. They are not cosmetic — they mechanically alter
how streams behave, which gyges are vulnerable, and how entropy evolves. The programmer is not writing
for a neutral machine. They are writing for a *climate*.

Four modifier categories exist: **Seasons**, **Temperature**, **Wind**, and **Environmental Disasters**.
Each feeds into the others. Each feeds into entropy.

---

## Seasons

A season defines the runtime's entropy attractor — the Ch level entropy drifts toward passively each tick,
regardless of what the program is doing. Think of seasons as the "expected temperature" of the system.

The default season cycles automatically. Duration is 1000 ticks per season by default (SDK-configurable).
Forcing a season change mid-run costs **+4.0 Ch flat**.

### Spring

```
$S := spring
```

**Entropy attractor**: 30 Ch. Drift rate: 0.05 Ch/tick.

Spring is growth and renewal — the runtime is waking up, becoming unpredictable. Parasites are stirring
from winter dormancy. New connections form unexpectedly. Things that were frozen begin to thaw, sometimes
violently.

| Property | Value |
|---------|-------|
| Parasite spawn rate | +20% baseline |
| Rain/flood events | 1.5× baseline frequency |
| Season transition from Winter | +3.0 Ch spike (thaw turbulence) |
| Season transition from Summer | −1.0 Ch shift (cooling relief) |

**Programmer feel**: Optimistic but unstable. The environment is becoming active. Establish monitoring before
parasites reach feeding state.

### Summer

```
$S := summer
```

**Entropy attractor**: 50 Ch. Drift rate: 0.08 Ch/tick (strongest pull of any season — summer wants intensity).

Summer is peak activity. Everything is running hot. Streams strain under load. Parasites are maximally
active. Drought conditions become possible. Fast streams contribute 1.5× their normal entropy at this tier.

| Property | Value |
|---------|-------|
| Fast stream entropy contribution | 1.5× |
| Temperature modifier baseline | 65 Fx (hot baseline) |
| Drought events | Possible (summer only, or scorching temp) |
| Season transition from Spring | +5.0 Ch spike (heat onset) |
| Season transition from Autumn | +2.0 Ch (Indian summer) |

**Programmer feel**: Everything is alive and fighting. This is the hardest season to sustain long runs in.
Defense must be in place before Summer's attractor pulls entropy into Turbulent.

### Autumn

```
$S := autumn
```

**Entropy attractor**: 35 Ch. Drift rate: 0.06 Ch/tick.

Autumn is wind down. Streams are completing more frequently. Parasites are preparing to hibernate.
The environment is releasing rather than accumulating. But things are loosening — rockslides become
more frequent as the system settles.

| Property | Value |
|---------|-------|
| Clean stream completion sink | 1.5× effective |
| Rockslide frequency | 2× baseline |
| Parasite spawn rate | −30% baseline |
| Season transition from Summer | −3.0 Ch shift (relief) |
| Season transition from Winter | +2.0 Ch spike (unexpected warming) |

**Programmer feel**: A reprieve. The window to catch up on entropy management, reinforce defenses, and
let parasites return to dormancy before the freeze.

### Winter

```
$S := winter
```

**Entropy attractor**: 15 Ch. Drift rate: 0.1 Ch/tick (strongest attractor — winter aggressively suppresses chaos).

Winter is cold, slow, and brittle. Streams move sluggishly. Parasites are nearly dormant. The environment
is peaceful but fragile: frozen streams can crack suddenly, causing avalanches.

| Property | Value |
|---------|-------|
| All stream throughput | −20% (cold viscosity) |
| Fast streams | May spontaneously throttle to `-+>` speed |
| Parasite spawn rate | −70% baseline |
| Ambient entropy drain | −0.2 Ch/tick |
| Deep Winter drain (below 20 Ch) | −0.5 Ch/tick |
| Avalanche event | Unique to winter; see Disasters |
| Season transition from Autumn | −4.0 Ch shift (sudden freeze) |
| Forced transition from Summer (SDK) | +6.0 Ch spike then rapid cooling (violent cold snap) |

**Programmer feel**: The calm before the next Spring. A good season to restructure stream graphs,
recall parasites, and reduce entropy before cycling begins again. Don't get comfortable — glaciers crack.

### Season Transition Mechanics

Seasons do not snap. They transition over a configurable window (default: 100 ticks). During transition,
the entropy attractor linearly interpolates between the two season targets. Transition spikes fire at
the **midpoint** of the transition period.

A program can lock a season permanently via the SDK, but forcing any season change mid-run always costs
the spike for the transition being skipped.

---

## Temperature

Temperature is a **derived modifier** — it cannot be set directly. It is computed from season, stream
activity, and entropy:

```
Temperature (Flux, Fx) = SeasonBaseline + (StreamLoad × 0.5) + (Entropy × 0.3)
```

**Season baselines:**

| Season | Baseline Fx |
|--------|------------|
| Winter | 10 Fx |
| Spring | 35 Fx |
| Autumn | 40 Fx |
| Summer | 65 Fx |

**Stream load contribution**: Each active stream adds up to 0.5 Fx based on its data throughput.
A program with 20 heavily-loaded streams can add +10 Fx on top of the season baseline.

**Entropy contribution**: 0.3 Fx per 1.0 Ch of entropy. At 80 Ch, entropy alone contributes +24 Fx.

### Temperature Ranges and Effects

**Cold (0–20 Fx)**

The runtime is sluggish. Data moves slowly. Waiting takes longer. But some structures are better
preserved in the cold.

| Effect | Detail |
|--------|--------|
| All stream throughput | −30% |
| `-,->` wait duration | 2× longer (slower waking) |
| `~>` lossy loss rate | Reduced — cold preserves data (ice storage) |
| `->` standard | May freeze for 1–3 ticks intermittently |

**Warm (21–50 Fx)**

Baseline. No modifications to stream behavior.

**Hot (51–75 Fx)**

The system is running hot. Speed increases, but reliability degrades.

| Effect | Detail |
|--------|--------|
| `->>` fast throughput | +20% speed bonus |
| `~>` lossy loss rate | 1.5× |
| `-+>` throttle | May briefly fail, bursting at full speed |
| `-/>` filter accuracy | −10% (heat warps the filter mesh) |

**Scorching (76–100 Fx)**

At this temperature, the runtime is on fire. Normally stable streams begin degrading spontaneously.

| Effect | Detail |
|--------|--------|
| `->` standard | 15% chance/tick of converting to `~>` (stream vaporizes) |
| `->>` fast | 10% chance/tick of converting to `-!->` (overheating causes error) |
| `~>` lossy loss rate | 3× normal |
| `-!->` error | Cascades to adjacent streams at 20% chance per tick |
| All filters | Half effectiveness |

**Note**: Temperature is not directly controllable by the programmer. The only levers are:
- Choose a cooler season (`$S := winter`)
- Reduce active stream count (fewer streams = less StreamLoad contribution)
- Lower entropy (lower entropy = less entropy Fx contribution)
- Use wait streams (they drain entropy, which lowers temp indirectly)

---

## Wind

Wind affects stream **direction** and **throughput** rather than data integrity. It is generated
by entropy and season effects.

```
Wind Strength = (Entropy × 0.08) + SeasonBonus
```

**Season bonuses:**

| Season | Wind Bonus |
|--------|-----------|
| Spring | +1.0 |
| Summer | +0.5 |
| Autumn | +2.0 (most volatile — things are loosening) |
| Winter | −1.0 (still air) |

Wind strength follows the **Beaufort scale** (0–10).

### Wind Effects by Strength

**Beaufort 0–2 (Calm)**
No effect on any stream.

**Beaufort 3–4 (Breeze)**

| Stream | Effect |
|--------|--------|
| `-...->` Splitter | Branch distribution imbalance up to 10% |
| `-*->` Signal | Delivery delay of 1–2 ticks |

**Beaufort 5–6 (Gale)**

| Stream | Effect |
|--------|--------|
| `->` Standard | 5% chance/tick of packet reordering (out of sequence arrival) |
| `-/|\->` Switch | 5% chance of incorrect branch selection |
| `-...->` Splitter | Branch imbalance up to 30% |
| `-*->` Signal | 10% loss chance |

**Beaufort 7–8 (Storm)**

| Stream | Effect |
|--------|--------|
| All streams | 15% chance/tick of delivering to wrong downstream node |
| `=>` Priority | Priority ordering may be scrambled |
| Wind entropy contribution | +0.1 Ch/tick |

**Beaufort 9–10 (Hurricane)**

| Stream | Effect |
|--------|--------|
| All streams | 30% chance/tick of misdirection |
| `->` Standard | May briefly reverse flow for 1–2 ticks |
| New connections | 20% failure rate to route at all |
| Wind entropy contribution | +0.3 Ch/tick |

---

## Environmental Disasters

Disasters are probabilistic events triggered by entropy thresholds. They both **result from** high entropy
and **generate additional entropy** — this is the core positive feedback loop.

Each disaster has:
- A **threshold** below which it cannot occur
- A **probability per tick** that scales with entropy (from threshold to maximum)
- A **duration** or instantaneous effect
- Unique season multipliers

### Rockslide

**Threshold**: 35 Ch | **Probability at threshold**: 1.0%/tick | **At 100 Ch**: 12%/tick

An instantaneous event. Randomly selects 1–3 active streams and inserts a temporary blockage lasting
5–15 ticks. These blockages behave like involuntary `-x>` streams — they cannot be removed by the
programmer; they must expire naturally.

Data continues to queue behind the blockage, building backpressure. The backpressure itself generates
entropy, making rockslides self-reinforcing at high entropy.

**Autumn multiplier**: 2× frequency.

Entropy effect: +2.0 Ch flat on trigger.

### Sliding Rocks (Minor Rockslide Precursor)

A lower-severity, higher-frequency version of a full rockslide. These are the texture of high-entropy
environments — not catastrophic, just constant small friction.

**Frequency by entropy:**

| Entropy | Probability/tick |
|---------|-----------------|
| Below 20 Ch | < 0.1% (rare nuisance) |
| 30 Ch | 0.5% |
| 50 Ch | 2% |
| 70 Ch | 5% |
| Above 80 Ch | 8% (near-constant small disruptions) |

Effect: Single random stream gets 50% throughput reduction for 3–8 ticks (partial blockage, not full block).

### Flood

**Threshold**: 40 Ch | **Probability at threshold**: 0.5%/tick | **At 100 Ch**: 8%/tick | **Duration**: 10–30 ticks

A sustained event affecting all heavily-loaded streams simultaneously:

- All streams carrying high data volume: 2× loss rate
- `-,->` wait streams: dragged out of wait state (flood breaks concentration)
- `-/>` filter streams: 30% bypass rate (water pushes through the filter)
- Newly-placed `-x>` blocks: 50% chance of being overrun

Entropy effect: +5.0 Ch flat on trigger, then +0.5 Ch/tick while active.
After resolution: −0.5 Ch/tick for 5 ticks (cleanup calm — the post-flood stillness).

### Drought

**Threshold**: 50 Ch (Summer season only, or Scorching temperature regardless of season)
**Probability at threshold**: 0.3%/tick | **At 100 Ch in Summer**: 6%/tick | **Duration**: 20–50 ticks

A sustained low-throughput event:

- All stream throughput: −40% (streams run dry)
- `->` standard: may pause entirely for 1–3 ticks
- `-,->` wait: may wait indefinitely if no data flows
- Data accumulates in queues, building backpressure, generating entropy

Entropy effect: −0.2 Ch/tick ambient cooling (still air), but the damage causes +0.3 Ch/tick through
stream degradation — net slightly positive. A slow, grinding entropy generator.

### Lightning Strike

**Threshold**: 55 Ch | **Probability at threshold**: 0.2%/tick | **At 100 Ch**: 5%/tick

Instantaneous. One random stream is immediately converted to `-!->` (error stream) for 1–5 ticks.
Any data in that stream at the moment of strike is corrupted. A downstream `-?->` catch stream can
recover the data if positioned correctly; otherwise data is lost.

Entropy effect: +3.0 Ch flat.

### Parasite Bloom

**Threshold**: 60 Ch | **Probability at threshold**: 0.4%/tick | **At 100 Ch**: 10%/tick | **Duration**: 5–15 ticks

During the bloom period, 1–5 new modifier-created parasites are spawned. These parasites are aggressive —
they begin feeding immediately rather than entering dormancy, and they do not honor recall signals.

Each spawned parasite adds +1.0 Ch flat. At maximum bloom size (5 parasites), a bloom can spike entropy
by +5.0 Ch in a single event.

The positive feedback loop: high entropy → bloom → parasites → entropy rises → more blooms.

### Glacier / Avalanche (Winter Exclusive)

**Threshold**: 15 Ch (only during Winter when entropy drops this low)
**Probability**: 0.8%/tick when entropy is below 15 Ch in Winter

Winter's unique disaster. Triggered not by high entropy but by *too low* entropy — the system has frozen
so completely that the ice cracks.

Effect: ALL streams simultaneously frozen for 3–8 ticks. No data moves anywhere. Complete silence.

After the freeze lifts, 50% chance of a **thaw event**: entropy spikes +4.0 Ch (the sudden release of
pressure from the frozen state). This can jolt a peaceful Winter program directly into Stirring or
Turbulent before Winter's attractor can pull it back down.

**The irony of the Glacier**: Perfect entropy management in Winter can paradoxically trigger the most
disruptive Winter event. Sometimes a little controlled chaos is safer than none at all.

---

## Modifier Interaction in Code

### Reading Modifiers

```stream
$S          <-- spring | summer | autumn | winter -->
$C          <-- current temperature in Flux (derived, read-only) -->
$@          <-- current time (unix timestamp) -->
$entropy    <-- current entropy level (0.0–100.0 Ch) -->
```

### Setting Season and Entropy

```stream
$S       := winter          <-- costs +4.0 Ch flat if changing mid-run -->
$entropy := 7               <-- explicit entropy set -->
$entropy := ...             <-- let runtime decide (random seed) -->
```

### Modifier Guards on Streams

```stream
|data| -/|$S == winter|\-> {
    |cold_handler|
    |warm_handler|
}

|data| -/|$C > 70|\-> {
    |overheat_handler|
    |normal_handler|
}
```

### Subscribing to Modifier Changes

```stream
-?*-> $S :: |on_season_change|    <-- fires when season changes -->
-?*-> $C :: |on_temp_spike|       <-- fires when temperature crosses a threshold -->
```

### Section Guards (conditional activation by modifier)

```stream
::body[$S:winter]::          <-- section only active in winter -->
::fallback[$entropy > 7]::   <-- section only active at high entropy -->
::debug[!$entropy]::         <-- section only active when entropy is zero -->
```
