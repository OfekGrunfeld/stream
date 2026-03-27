# Streams

Streams are the only primitive for moving data in Stream. There are no function calls, no return
values, no assignments that flow across scope boundaries — everything passes through typed stream edges.

A Stream program is literally a **graph**: gyge nodes connected by typed stream edges. The type of
the edge determines how data passes — whether it drops packets, prioritizes them, filters them,
waits for conditions, raises errors, or routes into other processes.

The same data flowing through a `->` edge, a `~>` edge, and a `->>` edge will arrive differently at
the destination. The edge is not just plumbing — it is computation.

---

## Stream Operator Reference

### `->` One-Way Stream

The standard stream. Data flows from source to destination in order, reliably (under low entropy).

```stream
|a| -> |b|
|a| -> |b| -> |c| -> |d|     <-- chains are shorthand for multiple edges -->
```

Under entropy: delays accumulate at Mid, packet reordering begins at High, spontaneous conversion
to `~>` (lossy) begins at Extreme (3% per tick).

---

### `=>` Priority Stream

Data on this edge is processed before any `->` edges in the same tick. The destination node receives
priority data before normal data, regardless of arrival order.

```stream
|critical| => |processor|
```

Multiple `=>` edges targeting the same node are ordered by the source node's declared priority rank
(optional annotation). Without a rank: FIFO within the priority class.

Under entropy: priority ordering remains reliable until High (10% inversion), breaks down at Extreme
(25% scramble; may behave as `->` for whole batches).

---

### `~>` Lossy Stream

Data may not arrive. The loss rate is programmer-defined (default: ~5%) but scales with entropy and
temperature. Lossy streams are appropriate for high-throughput data where occasional loss is acceptable —
sensor readings, telemetry, audio/video frames.

```stream
|sensor| ~> |aggregator|
```

Cold temperatures reduce loss rate (cold preserves). Hot temperatures increase it (heat degrades).
Under extreme entropy, a lossy stream can consume data from adjacent streams (overflow corruption).

---

### `-/>` Filter Stream

Data passes only if a condition is met. Items that fail the condition are dropped (not forwarded,
not buffered — gone).

```stream
|raw| -/> |valid|                          <-- filter with no condition: always passes (identity filter) -->
|raw| -/|len > 0|\-> |valid|              <-- conditional filter -->
```

Under entropy: filter accuracy degrades. At Extreme, the filter may **invert** — passing everything
it should block, for whole ticks.

---

### `-x>` Blocked Stream

No data passes. The stream is a wall. Data queues behind it indefinitely (building backpressure and
generating entropy). The block can be lifted by a signal on the unblock port.

```stream
|source| -x> |dest|
```

A blocked stream is not an error — it is a deliberate gate. Common use: holding data until a
condition is met, then releasing via signal.

Under entropy: the block may "leak" at High (5% per tick), and can be overrun entirely by a flood
disaster.

---

### `-+>` Throttled Stream

Data passes at a controlled rate, implemented as a token bucket. The number of `+` signs controls
the throttle level (more `+` = more throttle = slower).

```stream
|fast_source| -+> |slow_consumer|      <-- single throttle level -->
|fast_source| -++> |slow_consumer|     <-- double throttle -->
|fast_source| -+++> |slow_consumer|    <-- triple throttle -->
```

The token bucket refills at a rate configurable per edge. Entropy randomly consumes tokens
("entropy drain") and occasionally grants bonus tokens ("entropy surge"), creating unpredictable bursts.

Under extreme entropy: throttle may fail entirely, allowing unrestricted flow for 1–2 ticks.

---

### `->>` Fast Stream

Delivers data at maximum speed, bypassing normal tick-rate limitations. The number of `>` signs
controls how many extra delivery attempts are made per tick.

```stream
|urgent| ->> |consumer|      <-- fast -->
|urgent| ->>> |consumer|     <-- faster -->
```

Fast streams contribute +0.2 Ch/tick to entropy (speed creates turbulence). At High entropy,
they risk overheating (5% chance/tick of converting to `-!->` error stream). At Scorching temperature
+ Extreme entropy, overheating is nearly guaranteed within 10 ticks.

---

### `-/|\->` Switch Stream

Routes data to one of multiple downstream branches based on a selection condition. The `|` marks
the decision point in the operator.

```stream
|data| -/|\-> {
    |branch_a|
    |branch_b|
    |branch_c|
}
```

With a condition gyge:

```stream
|data| -/|condition|\-> {
    |on_true|
    |on_false|
}
```

The condition gyge evaluates the incoming item. Items satisfying the condition go to the first branch;
others go to the second. Discard a branch with `...`:

```stream
|data| -/|condition|\-> {
    |handler|
    ...             <-- discard items that don't match -->
}
```

Under entropy: switch logic misroutes at High (10%). At Extreme, the switch may lock to a single
branch for 5–10 ticks, routing everything to one destination regardless of the condition.

---

### `-#->` Batcher Stream

Accumulates incoming data into batches before forwarding. The batch is released when a size threshold
is met or a timeout elapses.

```stream
|events| -#-> |batch_processor|
|events| -#[size:100]-> |batch_processor|      <-- batch of 100 items -->
|events| -#[timeout:500]-> |batch_processor|   <-- or release after 500ms -->
```

Under entropy: batch boundaries shift (±1 item at Mid, ±20% at High). At Extreme, batch semantics
collapse entirely — data streams continuously, losing batch structure.

---

### `-...->` Splitter Stream

Fans data out to N downstream branches simultaneously, creating N copies of each item.

```stream
|data| -...-> {
    |copy_a|
    |copy_b|
    |copy_c|
}
```

Under entropy: distribution becomes uneven (wind compounds this — a Gale can cause 30% imbalance).
At Extreme, some branches may receive duplicates while others receive nothing for whole ticks.

---

### `-|->` Argument Filter Stream

Filters a specific positional argument out of a tuple-like stream. The position of `|` in the
operator indicates which argument is filtered.

```stream
|tuple_stream| -|-> |second_arg|       <-- keeps second argument -->
|tuple_stream| -|--> |first_of_three|  <-- keeps first of three args -->
|tuple_stream| --|--> |middle|         <-- keeps middle of three args -->
```

Works in "tuple-style" — if the stream carries `(a, b, c)`, `-|->` extracts a specific position.
Under entropy: argument pattern misread at Mid (3%), rising to 25% misread at Extreme.

---

### `-!->` Error Stream

Raises an error event when data flows through it. The data becomes the error payload. The error
is placed in the runtime's Error Event Queue and can be caught downstream by a `-?->` stream.
If uncaught, it increases local entropy on the offending edge and is logged.

```stream
|invalid| -!-> "validation failed"
|invalid| -!-> |error_gyge|
```

An uncaught error is not a program crash — it is more entropy. A buggy node that repeatedly raises
errors poisons its downstream neighbors over time.

Under entropy: at High, errors cascade to adjacent streams (15% chance per tick). At Extreme,
error-on-error chains are possible: an error stream itself errors.

---

### `-!!->` Exit Stream

Terminates the program immediately when data flows through it. The payload is the exit code.
All in-flight packets are abandoned. Parasites are sent kill signals (cooperative ones stop;
non-cooperative ones become orphaned).

```stream
|done| -!!-> 0       <-- exit code 0 -->
|fail| -!!-> 1       <-- exit code 1 -->
```

Under extreme entropy: the exit signal may require re-sending (each attempt costs +0.5 Ch flat).
During an active disaster, the runtime may refuse to exit until the disaster resolves.

---

### `-?->` Catch Stream

Monitors a source node or edge for error events. When a matching error event appears in the Error
Event Queue, the catch stream delivers the error payload to its destination. Consuming the error
prevents it from propagating further and drains **−0.3 Ch flat**.

```stream
|risky_gyge| -?-> |error_handler|
```

Multiple catch streams can watch the same source. First match (by priority order) consumes the error.
Uncaught errors in a tick are marked as uncaught and raise local entropy on the source edge.

Under entropy: catch streams miss errors at High (80% catch rate), may themselves error at Extreme
(10% per tick). An overloaded catch stream adds +0.1 Ch/tick.

---

### `-*->` Send Signal

Sends an out-of-band signal to a named recipient. Signals bypass normal data flow — they are
processed in a separate phase of the runtime loop (after normal delivery). Useful for:

- Unblocking a `-x>` stream
- Triggering a conditional action without streaming data
- Communicating between otherwise-unconnected parts of the graph

```stream
|trigger| -*-> |listener|
|trigger| -*-> @pid:1337      <-- send signal to another process -->
```

Under entropy: signals arrive late (Mid), may be duplicated or lost (High), and become probabilistic
at Extreme (70% delivery, 15% duplicate, 15% lost).

---

### `-?*->` Receive Signal

Listens for signals from a source. When a matching signal arrives, the gyge on the right receives it
as a stream item. Used for signal-driven reactive patterns.

```stream
-?*-> |sender| :: |receiver|
-?*-> $S :: |on_season_change|      <-- subscribe to modifier changes -->
-?*-> @port:9090 :: |incoming|      <-- receive signals from a port -->
```

Under entropy: phantom signals appear at Mid (2%), rising to 20% at Extreme. At 90+ Ch, may receive
signals from parasites operating in other programs (cross-process phantom signals).

---

### `-,->` Wait Stream

Holds data until a condition is satisfied. Nothing downstream receives data while the stream is
waiting. The wait stream itself drains entropy (−0.15 Ch/tick) while in the waiting state —
intentional stillness is anti-entropic.

```stream
|src| -,CONDITION-> |dst|
|src| -,-> |dst|             <-- no condition: intentional deadlock (park) -->
```

More commas = harder/longer wait:

```stream
|src| -,,->  |dst|           <-- two-stage wait -->
|src| -,,,-> |dst|           <-- three-stage wait -->
```

**Condition types:**

```stream
-,t:500->                    <-- wait 500ms -->
-,t:$@->                     <-- wait until time modifier threshold -->
-,sig:SIGTERM->              <-- wait for OS signal -->
-,|flag|->                   <-- wait until gyge |flag| is non-zero -->
-,@pid:1337->                <-- wait until PID 1337 exists -->
-,!|err|->                   <-- wait until error gyge |err| clears -->
-,stream:|other|->           <-- wait until stream |other| closes -->
```

Under entropy: early wake begins at High (10% per tick the condition fires early). Floods actively
drag wait streams out of their waiting state.

---

### `==>` Parasite Injection

A special outward stream that injects a gyge into another process as a parasite. See `parasites.md`
for full lifecycle documentation.

```stream
|payload| ==> @pid:1337
|payload| ==> @name:"firefox"
|payload| ==> @port:8080
|payload| ==> @*                 <-- broadcast; requires entropy > 60 Ch -->
```

---

### `<~` Feedback Loop

Creates a back-edge in the stream graph, routing a gyge's output back to its own input (or another
earlier node in the graph). Enables loops.

```stream
|counter| <~ |counter|                               <-- infinite loop -->
|counter| -> |body| <~ |counter|                     <-- loop with body -->
|counter| -> |body| -/|counter < 10|\-> <~ |counter| <-- bounded loop -->
```

---

## Stream Chains and Fan-Outs

### Chaining

Any number of streams can be chained. Each `->` in a chain creates a separate SCD (Stream Channel
Descriptor) in the runtime graph:

```stream
|a| -> |b| -> |c| -> |d|
```

This is syntactic sugar for three separate edges `(a, b)`, `(b, c)`, `(c, d)`.

### Mixed-Type Chains

Different stream types can be mixed in a chain:

```stream
|input| -> |validate| -/> |clean| ~> |processor| => |output|
```

### Fan-Out

Multiple streams from the same source:

```stream
|data| -> |path_a|
|data| -> |path_b|
|data| -> |path_c|
```

This is not a splitter — each destination receives all data independently (implicit copy).
For explicit fan-out with equal distribution, use `-...->` (Splitter).

---

## Stream as Computation

In Stream, the edge itself contains the computation, not just the transport. Stream type policies
define three hooks the runtime loop calls on every tick:

| Hook | Description |
|------|-------------|
| `should_deliver(packet, edge_state, entropy)` | Returns whether delivery should happen this tick |
| `transform(packet, entropy)` | Optionally mutates the packet in transit |
| `on_blocked(edge_state, entropy)` | What happens when the destination is saturated |

This means a `~>` (Lossy) stream doesn't just transport data — its `should_deliver` function makes
a probabilistic decision on every packet, and its `transform` function may corrupt surviving packets
at high entropy. The stream edge is a live computation on every tick.

---

## Priority and Delivery Order

Within a single tick, streams are processed in two passes:

**Pass A** — all `=>` priority edges. Their destinations are guaranteed to have populated input ports
before any normal-priority node is activated.

**Pass B** — all other stream types, in topological order where possible, arbitrary otherwise.

Signal streams (`-*->`, `-?*->`) are processed in a separate phase after normal delivery — they are
out-of-band by design.

Wait streams (`-,->`) are resolved last — they check their conditions after all delivery and signal
phases have run for the tick.
