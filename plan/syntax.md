# Keywords

$@ - Time
$C - Temperature
$S - Season
$entropy - Current entropy level (0.0–100.0 Ch)

---

# Gyge

The only type in Stream. Declared by wrapping a name in pipes.

```
|name|
```

### Declaration & Assignment

```
|buf|    := <o/          <-- allocate raw bytes gyge -->
|n|      := 42           <-- numeric gyge -->
|msg|    := "hello"      <-- string-like gyge -->
|null|   := ...          <-- void gyge (ellipsis = nothing) -->
```

### Calling as a Function

Streaming IS calling. Arguments flow in; result flows out.

```
|args| -> |fn| -> |result|
```

### Byte Access

```
[|buf|]           <-- treat gyge as raw bytes -->
[|buf|+4]         <-- 4-byte offset -->
[|buf|+4..12]     <-- byte slice, bytes 4 through 12 -->
```

### Composition

```
|ab| := |a| & |b|         <-- fuse two gyges into one -->
|ab| := |a| &-> |b|       <-- compose as ordered pipeline gyge -->
```

### Optional Type Hints (ignored at runtime, useful for tooling)

```
|%fn|       <-- hint: function -->
|@cls|      <-- hint: class/object -->
|~bytes|    <-- hint: raw bytes -->
|?mock|     <-- hint: mock/fake program -->
|!parasite| <-- hint: parasite -->
```

---

# Streams

```
->       := One-way stream
=>       := Priority stream
~>       := Lossy
-/>      := Filter
-x>      := Blocked
-+>      := Throttle (more + = more throttle; uses token bucket)
->>      := Fast (more > = faster)
-/|\->   := Switch statement stream
-#->     := Batcher (join)
-...->   := Splitter
-|->     := Filter argument at position of "|" (e.g. -|--> filters first of 3+ args)
-!->     := Raise error
-!!->    := Exit (with code)
-?->     := Catch error
-*->     := Send signal
-?*->    := Receive signal
-,->     := Wait (see below)
==>      := Parasite injection (outward priority stream into another process)
<~       := Feedback loop (loop a stream back to its source)
```

### Inline Filter Condition

```
|data| -/|len > 0|\-> {
    |on_true|
    |on_false|
}
```

---

# Wait Stream (`-,->`)

A wait stream holds data until a condition is satisfied. Nothing downstream receives data until the condition resolves.

```
|src| -,CONDITION-> |dst|
```

More commas = harder/longer wait:

```
|src| -,,->  |dst|    <-- two-stage wait -->
|src| -,,,-> |dst|    <-- three-stage wait -->
|src| -,->   |dst|    <-- no condition: intentional deadlock (park instruction) -->
```

### Condition Types

```
-,t:500->             <-- wait 500ms -->
-,t:$@->              <-- wait until time modifier says go -->
-,sig:SIGTERM->       <-- wait for a signal -->
-,|flag|->            <-- wait until gyge |flag| is non-zero/non-empty -->
-,@pid:1337->         <-- wait until PID 1337 exists -->
-,!|err|->            <-- wait until error gyge |err| clears -->
-,stream:|other|->    <-- wait until another stream closes -->
```

---

# Parasite Injection (`==>`)

Voluntarily inject a gyge as a parasite into another program. Uses `==>` (outward priority stream).

### By PID

```
|payload| ==> @pid:1337
```

### By Name, Port, IP, or Directory

```
|payload| ==> @name:"firefox"
|payload| ==> @port:8080
|payload| ==> @ip:"192.168.1.5":port:22
|payload| ==> @dir:"/tmp/targets/"
```

### Multiple selectors (chained with `+`)

```
|payload| ==> @ip:"10.0.0.1" + @port:4444
```

### Broadcast (inject into every reachable process)

```
|payload| ==> @*
```
Only legal at entropy > 60 Ch. Runtime may refuse at low entropy.

### Parasite section declaration

For complex parasites with full lifecycle control:

```
::parasite |spy| {
    target {
        primary: port:5432
        fallback: name:postgres
    }
    capabilities {
        tier: 1
        hooks: connect, read, write
    }
    spread {
        vectors: fork, exec
        depth: 2
    }
    channels {
        out: |db_queries| -> |result_stream|
        control: |spy_ctl|
    }
}
```

Send commands to a live parasite via its control channel:

```
|spy_ctl| <- "spread:activate"
|spy_ctl| <- "cap:tier:2"
```

---

# Control Flow

### Loop (feedback)

```
|counter| <~ |counter|                             <-- infinite loop -->
|counter| -> |body| <~ |counter|                   <-- loop with body -->
|counter| -> |body| -/|counter < 10|\-> <~ |counter|  <-- bounded loop -->
```

### Conditional (if/else via switch)

```
|value| -/|condition|\-> {
    |on_true|
    |on_false|
}

<-- discard one branch: -->
|value| -/|condition|\-> {
    |handler|
    ...
}
```

### Early Termination

```
|src| -> |check| -x> |dst|        <-- dst never receives anything -->
|src| -!!-> 0                      <-- exit with code 0 -->
|src| -!!-> 1                      <-- exit with code 1 -->
```

---

# Modifier Interaction

### Reading Modifiers

```
$S          <-- current season: spring | summer | autumn | winter -->
$C          <-- current temperature in Flux (derived, not directly set) -->
$@          <-- current time (unix timestamp) -->
$entropy    <-- current entropy level (0.0–100.0 Ch) -->
```

Modifiers can be streamed like any value:

```
$S       -> |season_gyge|
$entropy -> |chaos_level|
```

### Setting Modifiers

```
$S       := winter
$entropy := 7
$entropy := ...     <-- let runtime decide (random) -->
```

### Modifier Guards (in stream conditions)

```
|data| -/|$S == winter|\-> {
    |cold_handler|
    |warm_handler|
}

|data| -/|$entropy > 5|\-> {
    |chaos_handler|
    |normal_handler|
}
```

### Modifier Change Subscription

```
-?*-> $S :: |on_season_change|
-?*-> $C :: |on_temp_change|
```

---

# Sections (`::`)

Sections divide the program into named zones. Order matters; high entropy may reorder them.

### Built-in Sections

```
::header::
    <o-> "program_name"
    $entropy := 3
    $S       := winter

::imports::
    ><libname><
    ><libname+myns><

::alloc::
    |buf|  := <o/
    |flag| := 0

::body::
    <-- main logic -->

::traps::
    -?->  |err| -> |err_handler|
    -?*-> |sig| -> |sig_handler|

::cleanup::
    <o\ |buf|

::end::
    ... -> -!!-> 0
```

### User-Defined Sections

```
::validate::
    |input| -/|input == ...|\-> {
        -!-> "empty input"
        |clean|
    }
```

Stream into a section by name:

```
|data| -> ::validate:: -> ::process:: -> |result|
```

### Section Guards (conditional activation)

```
::body[$S:winter]::          <-- only active in winter -->
::fallback[$entropy > 7]::   <-- only active at high entropy -->
::debug[!$entropy]::         <-- only active when entropy is zero -->
```

---

# Other Syntax

```
<o>            := this program (pid, imports, root)
<o->           := entry point
<-- -->        := comment
<o/            := allocate
<o\            := deallocate
><o><          := import into this program
><o+offset><   := import to another namespace/pid
::             := section delimiter
...            := void / buffer / nothing value
```

---

# Obfuscated ("Fucked") Syntax

Two-way lossless conversion between human-readable and obfuscated forms.

| Human-Readable | Obfuscated | Notes |
|---|---|---|
| `->` | `⟶` | Rightwards long arrow |
| `=>` | `⟹` | Double rightwards arrow |
| `~>` | `≀⟶` | Lossy (wreath prefix) |
| `-x>` | `⟶̸` | Arrow with combining stroke |
| `==>` | `⇶` | Triple rightwards (parasite) |
| `-!->` | `↯` | Lightning (raise error) |
| `-!!->` | `↯↯` | Double lightning (exit) |
| `<~` | `↫` | Loop-back |
| `&->` | `⊕⟶` | Gyge composition |
| `::` | `§` | Section sigil |
| `:=` | `≔` | Definition |
| `...` | `⋯` | Void / ellipsis |
| `<o/` | `⊢` | Allocate (turnstile) |
| `<o\` | `⊣` | Deallocate (reverse turnstile) |
| `\|name\|` | `⌈name⌉` | Gyge delimiters |
| `@pid:` | `℗` | PID target sigil |
| `$S` | `𝕊` | Season modifier |
| `$C` | `℃` | Temperature modifier |
| `$@` | `⌚` | Time modifier |
| `$entropy` | `∿` | Entropy (sine wave, chaotic) |

At maximum obfuscation (`$entropy := 9`): all string literals become hex byte sequences,
all whitespace is stripped, and the result is intentionally unreadable.

### Before / After Example

Human-readable:
```stream
::body::
    |input| -> |clean| -/|len > 0|\-> {
        |process|
        -!-> "bad"
    } -> |output|
```

Obfuscated:
```
§body§
    ⌈input⌉ ⟶ ⌈clean⌉ ⟿⌈len > 0⌉⟶ {
        ⌈process⌉
        ↯ "bad"
    } ⟶ ⌈output⌉
```

---

# Full Example Program

```stream
::header::
    <o-> "intake_watcher"
    $entropy := 2
    $S       := $S          <-- use real system season -->

::alloc::
    |sock|   := <o/
    |buf|    := <o/
    |err|    := ...
    |result| := ...

::imports::
    ><netlib+io><

::body::
    <-- receive data on port 9090 -->
    -?*-> @port:9090 :: |buf|

    <-- in winter, apply lossy stream (nature-themed packet loss) -->
    |buf| -/|$S == winter|\-> {
        |buf| ~> |clean|
        |buf| -> |clean|
    }

    <-- filter out empty payloads -->
    |clean| -/|len > 0|\-> {
        |clean|
        ...
    }

    <-- process; catch errors -->
    |clean| -> |process| -?-> |err|

    <-- at high entropy, propagate error instead of logging -->
    |err| -/|$entropy > 5|\-> {
        |err| -!-> "entropy too high"
        |err| -> |log|
    }

    |process| -> |result| -> @port:9090

::cleanup::
    <o\ |sock|
    <o\ |buf|

::end::
    |result| -> -!!-> 0
```
