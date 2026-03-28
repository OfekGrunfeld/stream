# Gyge

A gyge is the only type in Stream. There are no integers, strings, booleans, functions, or classes —
there is only `gyge`. A gyge can be any of these things simultaneously or none of them. Its shape
is determined at runtime by how it is used, not by how it is declared.

This is not duck typing. It is something stranger: a type that exists in superposition until the
moment of first use collapses it into a specific shape. And even then, a parasite or an entropy event
can re-collapse it into something else.

The name comes from Gyges' Ring — the mythological ring that granted invisibility. A gyge is
invisible to the type system. It hides what it is until the last possible moment.

---

## Shapes

A gyge can resolve into any of these shapes at runtime:

| Shape | Behavior |
|-------|---------|
| **Variable** | Stateful store. Input overwrites value; output emits current value on demand. |
| **Function** | Activated by input; applies a transformation; emits output. Stateless between calls unless explicitly maintaining local state. |
| **Class** | Structured internal state with named sub-ports. Streams can target specific method ports. |
| **Program** | Spawns a child sub-graph (or child process). Enables true recursion and self-similar structures. |
| **Mock** | Emulates another gyge's interface but returns synthetic data. Used for testing and parasite impersonation. |
| **Bytes** | Opaque binary blob. Can be forwarded, split, batched, sliced — but not activated as a computation. |
| **Garbage** | Corrupted shape. Emits malformed data. Spreads corruption to downstream gyges. Contagious. |
| **Void** | Unactivated state. Has no incoming edges, no data, no shape. Not an error — a dormant potential. |

### Garbage Shape

Garbage deserves special attention. It is the only shape that is not declared by the programmer —
it is imposed by the runtime. A gyge becomes garbage when:

- It is downstream of another garbage gyge and receives corrupted data
- Entropy spikes above 90 Ch during its shape resolution (10% chance of garbage regardless of correct type)
- A modifier-created parasite forcibly reclassifies it
- It processes a corrupted packet from a `-!->` error stream without a `-?->` catch

Garbage gyges are not silently ignored. They emit data on their output ports — malformed data that may
cause downstream gyges to also become garbage. A garbage cascade is a valid runtime event.

**The only way to recover from a garbage gyge** is to deallocate it (`<o\ |name|`) and reallocate.
You cannot patch a garbage gyge. You replace it.

---

## Syntax

### Declaration

Naming a gyge brings it into existence as an uninitialized void gyge:

```stream
|name|
```

The identifier goes between the pipes. The gyge exists but has no shape until first activation.

### Assignment

The `:=` operator binds a value to a gyge. The right-hand side determines the initial shape:

```stream
|buf|    := <o/           <-- allocate raw bytes gyge -->
|n|      := 42            <-- resolves to variable (numeric) -->
|msg|    := "hello"       <-- resolves to variable (string-like) -->
|null|   := ...           <-- explicitly void -->
|flag|   := 0
```

### Calling as a Function

There is no call syntax. Streaming into a gyge IS calling it. Arguments flow in via the stream;
results flow out on the gyge's output port.

```stream
|args| -> |fn| -> |result|
```

If the gyge has an internal body (a `::gyge::` section — see Sections), it behaves as a function
when data streams in. If it has no body, it behaves as a variable (stores the last received value).

The shape distinction between function and variable is entirely emergent from whether the gyge has a body.

### Byte Access

Wrap the gyge in `[` `]` to address its raw byte representation, regardless of its current shape:

```stream
[|buf|]           <-- treat gyge as raw bytes -->
[|buf|+4]         <-- byte at offset 4 -->
[|buf|+4..12]     <-- byte slice from offset 4 to 12 -->
```

Byte access works on any gyge shape, including ones that resolved as functions or classes. At high
entropy, the bytes returned may be corrupted even if the gyge itself is not garbage.

### Composition

Two gyges can be fused or chained:

```stream
|ab| := |a| & |b|       <-- fuse into a single compound gyge -->
|ab| := |a| &-> |b|     <-- compose as ordered pipeline gyge -->
```

`&` creates a gyge whose behavior combines both inputs (like a merged namespace).
`&->` creates a gyge that, when streamed into, pipes data through `|a|` then `|b|` in sequence.

The composed gyge `|ab|` can then be used as a single unit:

```stream
|input| -> |ab| -> |output|     <-- equivalent to |input| -> |a| -> |b| -> |output| -->
```

### Loop (Self-Reference)

A gyge can feed back into itself:

```stream
|counter| <~ |counter|               <-- infinite loop -->
|counter| -> |body| <~ |counter|     <-- loop with body -->
```

The `<~` operator creates a back-edge in the stream graph. The runtime loop detects cycles and
ensures they don't starve non-cyclic streams of processing time.

---

## Optional Type Hints

Hints are visible to tooling and documentation but **ignored at runtime**. The runtime always resolves
shape lazily from actual usage. Hints are a courtesy to humans, not the evaluator.

```stream
|%fn|       <-- hint: function -->
|@cls|      <-- hint: class/object -->
|~bytes|    <-- hint: raw bytes -->
|?mock|     <-- hint: mock / test double -->
|!parasite| <-- hint: this gyge is intended to become a parasite -->
|#prog|     <-- hint: program (spawns sub-graph) -->
```

---

## Shape Resolution

Shape resolution is **lazy** — it happens on first activation, not at parse or compile time.
This is a deliberate design decision that enables several idioms:

- A gyge declared as a potential function behaves as a variable if it never receives callable input
- A gyge can be passed between streams, reshaped by a parasite, and continue operating under its new shape
- A gyge that receives foreign bytes from a parasite may reshape into a `bytes` gyge dynamically

### Resolution Algorithm

When a gyge node is first activated in the runtime loop:

1. Inspect the data arriving on input ports — what is the structure of the first packet?
2. Check any declared type hints on the gyge declaration
3. Consult the **Type Registry** — if a gyge with the same name was previously resolved, use that as a template
4. Check current entropy: at >90 Ch, 10% chance of resolving to `garbage` regardless of correct type
5. Resolve and record the shape in the Type Registry

### The Type Registry

A global runtime table mapping gyge node IDs to their resolved shapes. The registry is:

- **Mutable**: a parasite can forcibly re-register a node under a different shape (a reclassification attack)
- **Historical**: tracks shape history per node (used by the entropy engine to compute how much chaos a node has experienced)
- **Queryable**: available to the Gyge Resolver, the Parasite Manager, and garbage detection heuristics

When a gyge's shape changes (either through reclassification or garbage corruption), all edges connected
to it are re-evaluated for compatibility with the new shape. Incompatible edges may generate error events.

### The Void State

A gyge with no incoming edges and no activation history is in the **void** state. This is not an error.
The runtime ignores void gyges entirely. They are inert potential.

Void gyges can be brought to life at any point by:
- The programmer adding an edge via normal stream syntax
- A parasite injecting a connection to the void node at runtime
- A modifier event that spontaneously connects two previously-unrelated gyges (rare, high-entropy event)

The void state is what the design document means by "fill the void with streams interconnecting."
A Stream program is not static — its graph can grow during execution as parasites add edges and
entropy events connect previously isolated nodes.

---

## Gyge as a Parasite

Any gyge can become a parasite. When a gyge is injected into another process via `==>`, its current
shape and state are serialized into a **Parasite Payload** and transmitted to the target.

The gyge continues to exist in both places — locally as a normal node in the stream graph, and remotely
as a parasite operating in the target process. The local gyge receives observations from the remote
parasite via the control channel.

```stream
|spy| := ...             <-- void gyge -->
|spy| ==> @pid:1337      <-- spy becomes a parasite in PID 1337 -->
                         <-- observations flow back into |spy| -->
|spy| -> |log|           <-- read what the parasite sees -->
```

If the originating process terminates while the parasite is still active, the parasite becomes
**orphaned** — it continues operating in the target indefinitely, with no tether back.

---

## Gyge Sub-Bodies (Internal Sections)

A gyge can have an internal body defined using `::gyge::` sections. This is how you make a gyge
behave as a function with deterministic logic:

```stream
<o/ |process|

::gyge |process|::
    |input| -/|input == ...|\-> {
        -!-> "empty input"
        |clean|
    }
    |clean| -> |transform| -> |output|
::end |process|::
```

When data streams into `|process|`, the internal section body executes with `|input|` bound to the
incoming data. The result flows out on `|output|`.

A gyge with a sub-body resolves as `function` shape on first activation.

---

## Examples

### Simple variable gyge

```stream
::alloc::
    |n| := 0

::body::
    42 -> |n|               <-- n now holds 42 -->
    |n| -> |output|         <-- stream n's value to output -->
```

### Gyge used as a filter function

```stream
<o/ |is_valid|

::gyge |is_valid|::
    |input| -/|len > 0|\-> {
        true  -> |result|
        false -> |result|
    }
::end |is_valid|::

::body::
    |data| -> |is_valid| -> |downstream|
```

### Composing two gyges into a pipeline

```stream
|pipeline| := |validate| &-> |transform|
|raw_input| -> |pipeline| -> |output|
```

### Gyge that becomes a parasite

```stream
::alloc::
    |hook| := ...

::body::
    |hook| ==> @name:"sshd"             <-- inject into sshd -->
    -,@pid:-1->                         <-- wait until injection confirmed -->
    |hook| -> |observations| -> |log|   <-- stream what the parasite sees -->
```
