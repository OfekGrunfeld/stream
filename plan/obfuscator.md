# Obfuscator

Stream has two syntax forms: **human-readable** and **fucked**. Both are valid input to a conforming
runtime. The obfuscator converts losslessly between them in both directions.

The fucked form is not just aesthetic hostility — it is a design statement. Stream programs that
operate at high entropy *should be hard to read*. The obfuscator makes that literalness concrete:
a program running at `$entropy := 9` can auto-obfuscate its own source as it runs.

---

## Design Principles

**Lossless round-trip**: human-readable → fucked → human-readable must produce identical semantics.
The obfuscator is not a minifier; it is a bijective encoding.

**Entropy-sensitive**: the obfuscation depth scales with the program's entropy level. At `$entropy := 0`,
the fucked form is mildly hostile. At `$entropy := 9`, it is intentionally unreadable.

**Structural preservation**: the fucked form retains the same graph structure. Two programs that
look completely different in fucked form may be structurally identical. This is the point.

**Two-way**: both directions are first-class. You should be able to write directly in fucked syntax
without ever touching the human-readable form. Tooling supports both.

---

## Operator Mapping

Every human-readable operator maps to a Unicode replacement. The fucked form uses combining
characters, mathematical symbols, and control-plane glyphs chosen for maximum visual hostility.

| Human-Readable | Fucked | Character Name |
|----------------|--------|----------------|
| `->` | `⟶` | Rightwards long arrow |
| `=>` | `⟹` | Double rightwards arrow |
| `~>` | `≀⟶` | Wreath product + long arrow |
| `-/>` | `⟿` | Rightwards wave arrow |
| `-x>` | `⟶̸` | Long arrow with combining stroke |
| `-+>` | `⟶₊` | Long arrow with subscript plus |
| `->>` | `⟹⟹` | Double arrow repeated |
| `-/|\->` | `⋈⟶` | Bowtie (switch/join symbol) + arrow |
| `-#->` | `⊞⟶` | Squared plus (batch) + arrow |
| `-...->` | `⋯⟶` | Midline ellipsis + arrow |
| `-\|->` | `⊣⟶` | Reverse turnstile (argument filter) + arrow |
| `-!->` | `↯` | Downwards zigzag arrow (lightning) |
| `-!!->` | `↯↯` | Double lightning |
| `-?->` | `↯⃝` | Lightning with combining circle (catch) |
| `-*->` | `⊛⟶` | Circled asterisk + arrow (signal) |
| `-?*->` | `⊛⃝⟶` | Circled asterisk + circle + arrow |
| `-,->` | `⌛⟶` | Hourglass + arrow (wait) |
| `==>` | `⇶` | Triple rightwards arrow (parasite) |
| `<~` | `↫` | Leftwards arrow with loop |
| `&->` | `⊕⟶` | Circled plus (composition) + arrow |

### Gyge and Program Delimiters

| Human-Readable | Fucked | Notes |
|----------------|--------|-------|
| `\|name\|` | `⌈name⌉` | Ceiling brackets (gyge) |
| `[name]` | `⟦name⟧` | Double brackets (byte access) |
| `<o>` | `⊙` | Circled dot (this program) |
| `<o->` | `⊙⟶` | Entry point |
| `<o/` | `⊢` | Turnstile (allocate) |
| `<o\` | `⊣` | Reverse turnstile (deallocate) |
| `><name><` | `≺name≻` | Angle (import) |
| `<-- ... -->` | `⟨⟨ ... ⟩⟩` | Double angle brackets (comment) |

### Keywords and Modifiers

| Human-Readable | Fucked | Notes |
|----------------|--------|-------|
| `:=` | `≔` | Definition equals |
| `::` | `§` | Section sigil |
| `...` | `⋯` | Void / ellipsis |
| `$S` | `𝕊` | Season (double-struck S) |
| `$C` | `℃` | Temperature |
| `$@` | `⌚` | Time (clock) |
| `$entropy` | `∿` | Entropy (sine wave — chaotic) |
| `@pid:` | `℗` | PID target sigil |
| `@name:` | `ℕ` | Name target |
| `@port:` | `℘` | Port target (Weierstrass p) |
| `@ip:` | `℩` | IP target (turned iota) |
| `@dir:` | `⌂` | Directory target (house symbol) |
| `@*` | `※` | Broadcast (reference mark) |

---

## Obfuscation Levels

The obfuscator has 10 levels (0–9), controlled by the entropy setting.

### Level 0 — Identity

No transformation. Human-readable output is preserved exactly.

### Level 1–2 — Operator Substitution

Only operators and delimiters are replaced with their Unicode equivalents.
Identifiers, strings, and numbers remain human-readable.

```stream
⌈input⌉ ⟶ ⌈output⌉
```

### Level 3–4 — Full Symbol Replacement

Operators, delimiters, keywords, and modifier sigils are all replaced.
Identifiers and string literals remain readable.

```stream
§body§
    ⌈input⌉ ⟶ ⌈clean⌉ ⟿⌈len > 0⌉⟶ {
        ⌈process⌉
        ↯ "bad input"
    } ⟶ ⌈output⌉
```

### Level 5–6 — Identifier Scrambling

Identifiers are replaced with entropy-seeded Unicode sequences. The mapping is deterministic and
reversible (the obfuscator maintains a symbol table for deobfuscation), but the output is hostile.

```stream
§⌛§
    ⌈⋮⋮⌉ ⟶ ⌈⋱⋰⌉ ⟿⌈⋰⋮ > 0⌉⟶ {
        ⌈⋱⋮⌉
        ↯ "bad input"
    } ⟶ ⌈⋰⋱⌉
```

### Level 7–8 — String Encoding

String literals are encoded as hex byte sequences. Numbers are encoded in alternate bases.
Combined with Level 5–6 identifier scrambling.

```stream
§⌛§
    ⌈⋮⋮⌉ ⟶ ⌈⋱⋰⌉ ⟿⌈⋰⋮ > 0x00⌉⟶ {
        ⌈⋱⋮⌉
        ↯ 0x62_61_64_20_69_6e_70_75_74
    } ⟶ ⌈⋰⋱⌉
```

### Level 9 — Full Entropy Mode

All whitespace is stripped. All literals encoded. Identifiers scrambled. Section boundaries
collapsed into inline sigils. The result is a continuous glyph stream with no visual separation.

```
§⌛§⌈⋮⋮⌉⟶⌈⋱⋰⌉⟿⌈⋰⋮>0x00⌉⟶{⌈⋱⋮⌉↯0x62_61_64}⟶⌈⋰⋱⌉
```

At Level 9, the program reads identically to noise. This is intentional.

---

## Before / After Examples

### Example 1 — Simple Stream

Human-readable:
```stream
::body::
    |input| -> |output|
```

Fucked (Level 3):
```
§body§
    ⌈input⌉ ⟶ ⌈output⌉
```

Fucked (Level 9):
```
§⋮§⌈⋮⌉⟶⌈⋱⌉
```

---

### Example 2 — Error Handling

Human-readable:
```stream
::body::
    |input| -> |process| -!-> "error"
    |process| -?-> |handler|
```

Fucked (Level 4):
```
§body§
    ⌈input⌉ ⟶ ⌈process⌉ ↯ "error"
    ⌈process⌉ ↯⃝ ⌈handler⌉
```

Fucked (Level 9):
```
§⋮§⌈⋮⌉⟶⌈⋱⌉↯0x65_72_72_6f_72⌈⋱⌉↯⃝⌈⋰⌉
```

---

### Example 3 — Parasite Injection

Human-readable:
```stream
::body::
    |payload| ==> @pid:1337
    |payload| -> |log|
```

Fucked (Level 4):
```
§body§
    ⌈payload⌉ ⇶ ℗1337
    ⌈payload⌉ ⟶ ⌈log⌉
```

---

### Example 4 — Full Program

Human-readable:
```stream
::header::
    <o-> "watcher"
    $entropy := 5
    $S       := winter

::alloc::
    |buf| := <o/
    |err| := ...

::body::
    -?*-> @port:9090 :: |buf|
    |buf| ~> |clean|
    |clean| -> |process| -?-> |err|
    |err| -> |log|

::cleanup::
    <o\ |buf|
```

Fucked (Level 5):
```
§⋮§
    ⊙⟶ "watcher"
    ∿ ≔ 5
    𝕊 ≔ winter

§⋮§
    ⌈⋮⌉ ≔ ⊢
    ⌈⋱⌉ ≔ ⋯

§⋮§
    ⊛⃝⟶ ℘9090 ∷ ⌈⋮⌉
    ⌈⋮⌉ ≀⟶ ⌈⋰⌉
    ⌈⋰⌉ ⟶ ⌈⋱⋮⌉ ↯⃝ ⌈⋱⌉
    ⌈⋱⌉ ⟶ ⌈⋱⋰⌉

§⋮§
    ⊣ ⌈⋮⌉
```

---

## Self-Obfuscation at Runtime

At `$entropy := 9` (maximum entropy), a Stream program can request that the runtime obfuscate its
own bytecode representation in memory — making it harder for an attached debugger or parasite to
reverse-engineer the program's logic from its in-memory representation.

This is not a security guarantee — a sufficiently privileged observer can still reconstruct the
original. It is entropy-appropriate behavior: a program operating at maximum chaos should look like
maximum chaos.

```stream
$entropy := 9
<o> ->> |self_obfuscate|    <-- trigger self-obfuscation of in-memory representation -->
```

---

## Tooling

### CLI

```sh
stream obfuscate --level 9 program.stream           # human-readable → fucked
stream deobfuscate program.stream.fucked            # fucked → human-readable
stream obfuscate --level 4 --output out.stream in.stream
```

The deobfuscator requires the **symbol table** produced during obfuscation to reverse identifier
scrambling. Without the symbol table, only Levels 1–4 (which don't scramble identifiers) can be
fully reversed automatically. Levels 5–9 require the symbol table.

### IDE Support

IDEs can display programs in either form at all times. A toggle switches the view; the underlying
file is stored in whichever form it was written. The IDE maintains a live mapping between human-readable
line numbers and fucked glyph positions for breakpoint support.

At high entropy levels, the IDE can animate the operator glyphs — they flicker between their
human-readable and fucked forms, reflecting the runtime's current instability. Pure flavor, but
on-brand.
