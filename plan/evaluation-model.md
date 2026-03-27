# Evaluation Model

Stream uses a **reactive dataflow graph** with actor-like node isolation. The program is not a sequence
of instructions — it is a graph that the runtime loop continuously activates, tick by tick, until
termination. Data moves along typed edges. Computations happen at gyge nodes when their inputs are
satisfied. The background entropy loop mutates edge behavior as a first-class runtime operation.

This is not pure CSP (Communicating Sequential Processes — streams are not cooperative, they can be
hijacked mid-flight), and not a pure actor model (topology is structural, not a consequence of runtime
decisions). It is a hybrid: a live, mutable dataflow graph where nodes are actor-isolated and edges
carry typed behavioral policies.

---

## Core Abstractions

### Gyge Instance Record (GIR) — The Node

Every gyge in the source maps to a **Gyge Instance Record** at runtime. A GIR contains:

| Field | Description |
|-------|-------------|
| Node ID | Globally unique UUID (parasites must be addressable across process boundaries) |
| Shape | Resolved gyge shape: variable / function / class / program / mock / bytes / garbage / void |
| Input port map | Named slots where incoming edge data accumulates |
| Output port map | Named slots from which the node emits data |
| Local entropy budget | Per-node entropy charge (parasites consume this) |
| Modifier affinity | Which nature modifiers affect this node and how |
| Parasite vulnerability | Rating derived from shape and local entropy (higher = easier to reclassify) |
| Activation state | IDLE / PENDING / RUNNING / DRAINED |

Nodes are **passive** — they do not own threads. The runtime loop activates them when input data is
available. In the reference interpreter, this is single-threaded cooperative scheduling. A production
runtime could assign each node a goroutine, Erlang process, or asyncio coroutine.

### Stream Channel Descriptor (SCD) — The Edge

Every stream operator creates a **Stream Channel Descriptor**. An SCD contains:

| Field | Description |
|-------|-------------|
| Source node ID + output port | Where data originates |
| Destination node ID + input port | Where data is delivered |
| Stream type | The operator token (`->`, `~>`, `=>`, etc.) |
| Policy object | Behavioral hooks: `should_deliver`, `transform`, `on_blocked` |
| Parameters | Type-specific config (throttle rate, filter predicate, batch size, split count) |
| Channel buffer | Ordered queue of in-flight packets |
| Edge state flags | ACTIVE / BLOCKED / DISRUPTED / INFECTED / DRAINED |
| Local entropy modifier | ±0.2 deviation from global entropy (per-edge chaos) |
| Disruption timer | Countdown to next entropy event on this edge |

### Stream Policy Objects

Each stream type is not just a label — it is a **behavioral policy** with three hooks:

```
should_deliver(packet, edge_state, entropy) → bool
    Decides whether this tick should attempt delivery.
    ~> rolls a loss probability scaled by entropy.
    -x> always returns false unless an unblock signal arrived.
    -+> consults a token bucket.

transform(packet, entropy) → packet
    Optionally mutates the packet in transit.
    ~> may corrupt surviving packets at high entropy.
    ->> passes through unchanged (speed is in the scheduling, not the data).
    -!-> converts the packet into an error event.

on_blocked(edge_state, entropy) → void
    Handles the case where the destination port is saturated.
    -!-> triggers error propagation.
    -x> accumulates data in the edge buffer.
    => re-queues for next tick with elevated priority.
```

---

## The Tick

A **tick** is the atomic unit of runtime progress. The tick duration is configurable:
- Reference interpreter: logical ticks (runs as fast as the host allows)
- Production runtime: wall-clock anchored (default: 10ms per tick, SDK-configurable)

### Nine Tick Phases

Each tick executes these phases in strict order. No phase modifies the graph while another is iterating.

#### Phase 0 — Entropy Recalculation

The Entropy Engine runs first. It reads the current graph state through a read-only view (it cannot
modify the graph directly) and computes:
- Delta for global entropy (sources − sinks)
- Delta updates for all per-edge local entropy modifiers
- Entropy events to be applied later (Phase 5)

The entropy engine uses a PRNG seeded from the program's entropy seed. **The same seed always produces
the same sequence of events given the same graph evolution** — runs are reproducible for debugging.

#### Phase 1 — Modifier Application

Active nature modifiers (season, temperature, wind) are evaluated for this tick. They publish **delta
vectors** to affected nodes and edges. These are applied immediately:
- A Storm modifier increases loss probability on all `~>` edges
- A Cold temperature reduces throughput on all edges by 30%
- Winter season pulls entropy toward 15 Ch

Modifiers shift their values autonomously (season cycles over ticks) or are driven by stream data
(a gyge consuming external weather data and publishing temperature values to the Modifier Engine).

#### Phase 2 — Parasite Lifecycle

All active parasites advance their lifecycle state machines:
- Spreading parasites check spread conditions and queue new edge injections
- Feeding parasites intercept edge data (applied to the channel buffer directly)
- Dormant parasites check if their entropy charge has been replenished
- Expired parasites are marked for garbage collection

The Parasite Manager also runs the **detection heuristic** this phase — looking for unexplained entropy
spikes, edges with policies inconsistent with their declared type, or new edges appearing without a
logged mutation source.

#### Phase 3 — Edge Delivery

The core phase. Every edge in the graph attempts delivery, in two passes:

**Pass A** — all `=>` priority edges. Guarantees destination nodes have priority data in their input
ports before any non-priority activation.

**Pass B** — all remaining edge types, in topological order where the graph is acyclic, arbitrary
otherwise. For each edge:

1. Check if the source node has data on its output port
2. Call `edge.policy.should_deliver(packet, edge_state, entropy)`
3. If delivery permitted: call `edge.policy.transform(packet, entropy)` and enqueue result in destination input port
4. If delivery blocked: call `edge.policy.on_blocked(edge_state, entropy)`

Back-edges (`<~` feedback loops) are processed last within Pass B to prevent infinite in-tick loops.

#### Phase 4 — Node Activation

Every node whose input ports contain unprocessed data is activated:

1. Resolve gyge shape if this is the first activation (call Gyge Resolver)
2. Execute the node's computation against available input data
3. Produce output data on output ports (available for delivery in the **next** tick)
4. If the node has side effects (I/O, OS calls), they are issued here

Output produced in Phase 4 is not delivered until the next tick's Phase 3. This ensures causal
consistency: a node cannot affect its own inputs within the same tick.

**Activation order within Phase 4:**
- `=>` priority-fed nodes activate before normally-fed nodes
- Within the same priority class: topological order where possible
- Cycles break at the feedback edge (`<~`) — the cycle's "start" node is chosen arbitrarily

#### Phase 5 — Entropy Event Resolution

Entropy events queued in Phase 0 are applied against the current graph state:

| Event Type | Effect |
|-----------|--------|
| Stream disruption | Edge flips to DISRUPTED for N ticks; `should_deliver` returns false |
| Node disaster | Node drops all buffered input data (simulates a crash) |
| Parasite injection | New parasite created; injected into target edge or node |
| Modifier shift | Nature modifier value changes suddenly (e.g., lightning spike in temperature) |
| Garbage cascade | A garbage-shape gyge's downstream edges are flagged for potential corruption |

Events are applied in entropy order (higher-impact events first) to prevent lower-impact events from
masking cascade effects.

#### Phase 6 — Signal Processing

`-*->` (Send signal) and `-?*->` (Receive signal) edges are processed. Signals are out-of-band —
they bypass the normal channel buffers and are delivered directly to the recipient's signal port.

Processing signals after normal delivery prevents signals from affecting the same tick they were sent
(causal consistency for signal-driven patterns).

Modifier change subscriptions (`-?*-> $S :: |handler|`) are also resolved this phase.

#### Phase 7 — Wait Resolution

`-,->` (Wait) edges check their wait conditions. A wait condition is satisfied when:
- Its timer has elapsed
- A signal has been received on the designated signal port
- A referenced gyge has changed to a non-void/non-zero state
- A referenced stream has closed (DRAINED state)
- An entropy threshold has been crossed

Wait conditions that resolve this tick release their held packets into normal delivery buffers for
Phase 3 of the next tick.

Under high entropy: early wake (10% per tick at High entropy, 20% at Extreme).

#### Phase 8 — Graph Mutation

All queued structural changes are applied atomically at end-of-tick:
- New edges added by parasite injection
- Edge policy modifications (capability escalation)
- `-!!->` exit severances (edges cut from the graph)
- Section activation changes (guarded sections becoming active/inactive)

Mutations are deferred to this phase to prevent structural modification during iteration.
The runtime loop is the only component permitted to modify the graph structure.

#### Phase 9 — Garbage Collection

Fully drained edges and nodes are marked. Orphaned nodes (no path to any output) are collected.
Parasite records for completed parasites are released. Shape history entries older than the
configurable retention window are pruned from the Type Registry.

---

## Gyge Resolution (Lazy Shape Determination)

Gyge shape is determined lazily on first activation — not at parse time. The **Gyge Resolver** is
called once per node, on the first invocation of Phase 4 for that node.

### Resolution Algorithm

```
1. Inspect structure of first arriving packet on input ports
2. Check declared type hints on the gyge declaration (if any)
3. Consult Type Registry — if a gyge with same name was previously resolved, use as template
4. Apply entropy: at >90 Ch global entropy, 10% chance of resolving to garbage regardless of correct type
5. Record resolved shape in Type Registry
6. Initialize node's internal state for that shape
```

### Shape Change After Resolution

A gyge's shape can change post-resolution only via:
- Parasite reclassification (a parasite forcibly re-registers the node's shape in the Type Registry)
- Garbage cascade (the node receives corrupted data that overwrites its shape)
- Programmer-initiated deallocate + reallocate (`<o\ |name|` then `<o/ |name|`)

When a shape change occurs, all connected edges are re-evaluated for compatibility. Incompatible
edges generate error events.

---

## Concurrency Model

### Reference Interpreter: Cooperative Single-Thread

The reference interpreter is logically single-threaded with tick-based interleaving. "Concurrent"
means all active edges are processed within the same tick. This matches Node.js's event loop model.

### Production Runtime: Lightweight Thread per Node

A production implementation assigns each gyge node a lightweight thread (goroutine, green thread,
or asyncio coroutine). Edges become typed channels between threads. The entropy and modifier engines
run as separate background goroutines publishing delta vectors to a shared modifier state.

### Priority Enforcement

Priority is enforced within Phase 3 (Pass A before Pass B) and Phase 4 (priority-fed nodes first).
Priority does **not** preempt in-progress computation — a node currently executing in Phase 4 is not
interrupted by a priority delivery. Priority only determines scheduling order within a tick.

### Throttle Implementation

`-+>` (Throttle) edges maintain a **token bucket** per SCD:
- Bucket capacity: N (configurable per edge, default: 10 tokens)
- Refill rate: R tokens per tick (configurable, default: 1 per tick)
- Delivery: requires 1 token; packet held if no token available
- Entropy effect: randomly drains tokens without delivering ("entropy drain") and occasionally grants
  bonus tokens ("entropy surge")

Result: throttled streams under high entropy deliver in unpredictable bursts rather than smooth flow.

---

## Parasite Runtime Integration

### Parasite Registry

Two tables maintained by the Parasite Manager:

**Outbound table** — parasites that originated here and escaped. Tracks last known lifecycle state
via heartbeat signals (if target is a cooperative Stream runtime).

**Inbound table** — parasites detected in this process's graph that did not originate locally.
Each entry: detection timestamp, anchor point (edge or node ID), threat level (derived from
entropy injection rate), lifecycle state.

### Escape Mechanism

A parasite escapes when a `program`-shape gyge encounters:
- Its entropy budget exceeding an escape threshold while it has external process handles in scope
- A `-*->` signal stream carrying a parasite payload to an inter-process channel
- An explicit `==>` operator in the source

The gyge's current state is serialized into a **Parasite Payload** (portable binary format) and
transmitted to the target via the Parasite Manager's IPC channel.

### Cross-Process Entropy Tracking

When a parasite successfully feeds in a foreign process, it reports via its covert channel back
to the Parasite Manager, which updates the parasite's local entropy contribution. The Entropy
Engine factors all active outbound parasites into the global entropy delta.

A parasite that has escaped and is feeding contributes +0.4 Ch/tick to the originating process's
entropy even though it is operating in a different process. Entropy is not bounded by process walls.

---

## Entropy Integration

### Computation

On each tick (Phase 0), global entropy is recalculated:

```
E(t+1) = clamp(E(t) + delta(t), E_min, E_max)
```

Where `delta(t)` aggregates:

**Sources (positive)**: active stream count, backpressure count, parasite activity, active disasters,
stream type premiums, time elapsed, programmer-triggered spikes

**Sinks (negative)**: clean stream completions, active blocks and waits, catch stream interceptions,
winter season ambient, SDK vents

### Per-Edge Entropy

```
E_effective = clamp(E_global + E_local, 0.0, 100.0)
```

Where `E_local` is the edge's local modifier (±0.2), affected by parasite attachment, proximity to
garbage gyges, and priority status (priority edges get a small negative local modifier).

This dual-layer model allows globally Calm environments with localized Chaotic pockets, and globally
Chaotic environments with protected priority corridors.

---

## Termination Semantics

Four distinct termination modes:

| Mode | Trigger | Behavior |
|------|---------|----------|
| **Natural Drain** | All edges DRAINED, no pending computation | Clean exit; runtime logs final entropy |
| **Explicit Exit** | `-!!->` stream fires | All in-flight packets abandoned; cooperative parasites killed; non-cooperative become ORPHANED |
| **Entropy Catastrophe** | Entropy reaches 100 Ch (opt-in via `entropy.cap = 100`) | Outbound parasites marked AUTONOMOUS; runtime collapses; final graph state logged |
| **Infinite Runtime** | Cyclic graph with live source (stdin, socket, etc.) | Runs forever; intended for "living program" use cases |

### Natural Drain Condition

Natural drain requires:
1. No edge has data in its channel buffer
2. No node has pending input in its port map
3. No entropy event is scheduled that would inject data
4. No parasite is expected to deliver data via its covert channel

Cyclic subgraphs under nonzero entropy always have data in flight (the cycle keeps generating entropy
events). A program with cycles cannot naturally drain unless all its cycles are explicitly broken
(by a `-x>` block or a `-,->` wait that is never resolved).

---

## Error Handling in the Graph

### Error Event Queue

`-!->` (Raise error) does not throw an exception. It places an **Error Event** in the Error Event
Queue, processed after Phase 4 (node activation) but before Phase 5 (entropy events). This ordering:
- Ensures errors can affect entropy (Phase 5)
- Ensures errors are not caused by entropy events (cannot be circular)

An Error Event contains:
- Error payload (the packet that triggered the error)
- Source edge ID
- Current entropy value
- Tick activation history (ordered list of nodes activated this tick — a lightweight call stack)

### Catch Consumption

A `-?->` (Catch) stream monitors for error events matching a source pattern. First matching catch
(by priority order) consumes the event. Consuming:
- Delivers the error payload to the catch destination node
- Removes the event from the queue (prevents further propagation)
- Drains −0.3 Ch flat from global entropy

An uncaught error marks the source edge as DISRUPTED for a configurable number of ticks and increases
its local entropy modifier.

### Error Cascades

At High entropy (60–80 Ch), uncaught errors on a `-!->` edge cascade to adjacent edges (15% chance
per adjacent edge per tick). At Extreme entropy (80+ Ch), error-on-error chains are possible — a
catch stream that itself errors creates a secondary error event. This is the entropy-driven failure
spiral: the more errors, the more entropy; the more entropy, the more cascade.

---

## Reference Interpreter Component Map

```
Source Text
    │
    ▼
┌─────────┐
│  Lexer  │  Tokenizes stream operators, gyge delimiters, modifiers, section markers
└────┬────┘
     │ Token stream
     ▼
┌──────────┐
│  Parser  │  Produces Abstract Syntax Graph (not tree — cycles are legal)
└────┬─────┘
     │ ASG
     ▼
┌───────────────┐
│ Graph Builder │  ASG → GIRs (nodes) + SCDs (edges) with policy objects
└──────┬────────┘
       │ Runtime graph
       ▼
┌──────────────────────────────────────────────────┐
│              Runtime Loop                        │
│                                                  │
│  Phase 0 ◄──── Entropy Engine                   │
│  Phase 1 ◄──── Modifier Engine                  │
│  Phase 2 ◄──── Parasite Manager                 │
│  Phase 3        Edge Delivery                    │
│  Phase 4 ◄──── Gyge Resolver (first activation) │
│  Phase 5        Entropy Event Resolution         │
│  Phase 6        Signal Processing               │
│  Phase 7        Wait Resolution                 │
│  Phase 8        Graph Mutation                  │
│  Phase 9        Garbage Collection              │
└──────────────────────────────────────────────────┘
       │
       ▼
  Termination (drain / exit / collapse / infinite)
```

**Communication rule**: No component talks to another component except through the Runtime Loop.
All components read graph state via a read-only view interface. Only the Loop applies mutations.
This strict topology makes the reference interpreter debuggable — pause at any tick boundary and
inspect the complete state of all components.

---

## Open Design Questions

These are deferred to the language specification process but must be resolved before a full
reference implementation:

1. **Gyge identity across shape changes** — When a parasite reclassifies a gyge from `function` to
   `garbage`, do connected edges inherit the new semantics immediately or enter a disruption state?

2. **Entropy floor** — Should programs configure a minimum entropy floor above 0.0 to guarantee
   some base level of chaotic behavior? Useful for programs that require parasite activity.

3. **Parasite cooperation protocol** — When two parasites from different originating programs attach
   to the same edge, are they competitive (one evicts the other) or cooperative (both coexist and
   potentially merge their covert channels)?

4. **Modifier DSL** — The modifier system is abstract. Are modifiers built-in constants only, or can
   programs define custom modifiers with custom effect functions?

5. **Stream graph hot-reload** — Can a running Stream program receive new source and hot-reload its
   graph while the background loop continues? Natural fit for the "living program" aesthetic but
   requires significant graph builder and loop complexity.
