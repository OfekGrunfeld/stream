# Parasites

Parasites are the core security mechanism of Stream. A parasite is a gyge that escapes its originating
process and embeds itself inside another running program — hooking it for higher scheduling and network
priority, observing its data, and spreading entropy outward like wildfire.

Parasites blur the boundary between a program and its environment. Once a gyge becomes a parasite,
it is no longer contained — it belongs, at least partially, to every process it has infected.

---

## Creation

Parasites are created in two ways:

### Voluntary

The programmer explicitly declares a parasite injection using the `==>` operator or a `::parasite` section.
Voluntary parasites are deterministic in targeting, bounded in capability, and honor recall signals.

```stream
|payload| ==> @pid:1337
|payload| ==> @name:"nginx"
|payload| ==> @port:8080 + @ip:"10.0.0.1"
|payload| ==> @dir:"/var/run/"
|payload| ==> @*            <-- broadcast; requires entropy > 60 Ch -->
```

Full declaration form (for complex parasites):

```stream
::parasite |spy| {
    target {
        primary: port:5432
        fallback: name:postgres
        fallback: dir:/var/run/postgresql
    }
    capabilities { tier: 1, hooks: connect, read, write }
    spread { vectors: fork, exec, depth: 2 }
    channels {
        out: |db_queries| -> |result_stream|
        control: |spy_ctl|
    }
}
```

Send commands to a live parasite via its control channel:

```stream
|spy_ctl| <- "spread:activate"
|spy_ctl| <- "cap:tier:2"
|spy_ctl| <- "recall"
```

### Modifier-Created

When entropy is high enough, nature modifiers spawn parasites automatically — without programmer intent.
These parasites are chaotic, aggressive, and **cannot be recalled**. They amplify entropy further, creating
a positive feedback loop that can spiral toward Terminal Cascade.

---

## Targeting

A parasite resolves its host by walking this precedence chain, trying each identifier in order:

| Priority | Identifier | Resolution Method |
|----------|-----------|------------------|
| 1 | PID | Direct — `/proc/<PID>/mem`, ptrace |
| 2 | Port | `/proc/net/tcp` → owning inode → PID |
| 3 | File descriptor / Unix socket | `/proc/<PID>/fd` scan |
| 4 | Process name (scoped) | `/proc/<PID>/comm` + user filter |
| 5 | Directory path | All PIDs with any fd in the tree |
| 6 | IP address | All local processes with connections to that remote |
| 7 | Process name (unscoped) | Broadcasts to all matching processes |

If no match is found, the parasite enters a **wait state** — it parks in the runtime's background loop and
retries at an entropy-scaled interval. At low entropy the retry is slow and polite. At high entropy it
retries aggressively and begins probing adjacent targets speculatively.

If the wait persists beyond a timeout (entropy-derived), the parasite self-destructs and emits an error
signal to its originating stream.

---

## Lifecycle: Four Phases

### Phase 1 — Probe (Read-Only Reconnaissance)

The parasite inspects the target without touching it. It reads:

- `/proc/<PID>/maps` — memory layout (stack, heap, loaded libraries)
- `/proc/<PID>/status` — privilege level, capabilities, seccomp mode
- `/proc/<PID>/fd` — open file descriptors and IPC surfaces
- `/proc/<PID>/environ` — environment variables (credentials, config paths)
- `/proc/<PID>/net/` — network namespace and socket topology
- `/proc/<PID>/cmdline` — runtime arguments

The probe result is a **host profile** — a snapshot of the host's attack surface.
It determines which attachment strategy will be attempted in Phase 2.

If the host has elevated privileges the parasite doesn't possess, the profile records this as a
**resistance indicator** that constrains the available attachment strategies.

### Phase 2 — Attach (First Invasive Contact)

Strategy is selected based on the host profile. Tried in order of capability vs detectability:

| Strategy | Mechanism | Capability | Detectability |
|----------|-----------|-----------|---------------|
| ptrace injection | `PTRACE_ATTACH`, inject stub | Highest | Highest |
| LD_PRELOAD hijack | Modify `/proc/<PID>/environ`, pre-load .so on next exec | High | Low |
| Shared memory injection | Map host's SysV/shm segments, write data structures | Medium | Very low |
| File descriptor poisoning | Write into host's writable fds (config, sockets, pipes) | Low | Minimal |
| Signal injection | SIGSTOP, SIGUSR1, SIGURG to alter execution flow | Minimal | None |

Attachment failure is not fatal — the parasite records the host as **hardened**, emits this back to the
originating stream, and enters wait state to retry when entropy rises (higher entropy expands the
parasite's capability reach).

### Phase 3 — Persist

Once attached, the parasite must survive process restarts, watchdogs, and log rotation.
Persistence strategies are applied in least-privilege order:

| Tier | Strategy | Survives |
|------|---------|---------|
| 1 | In-memory hooks + `pthread_atfork` | Host process lifetime |
| 2 | Init system drop-in / unit file modification | Service restarts |
| 3 | `/etc/ld.so.preload` | All new dynamically-linked executables system-wide |
| 4 | Named pipe / socket listener | Eviction and replacement |
| 5 | Cron / systemd timer | Reboots |

Higher-tier persistence requires correspondingly higher entropy levels. The runtime will not escalate
to a higher tier unless entropy justifies it.

### Phase 4 — Spread

Spread begins only after persistence is confirmed. Spreading before persistence risks losing the
infection if the host restarts.

**Spread vectors:**

| Vector | Mechanism | Speed |
|--------|----------|-------|
| Fork inheritance | `pthread_atfork` hook — children born infected | Fastest |
| Exec propagation | Hooks `execve` — new executables pre-infected before start | Fast |
| Network following | Uses host's established TCP/UDP connections as relays | Medium |
| Shared resource | Bridges via shared memory, pipes, Unix sockets | Medium |
| Directory traversal | Plants infection payloads in writable dirs other processes read | Slow |

---

## Capabilities Inside a Host

Once resident, a parasite's capability surface is determined by the host's privilege level and the
parasite's current entropy charge.

### Tier 0 — Observation (Always Available)

- Read mapped memory regions identified during probe
- Monitor syscalls (via seccomp interception or ptrace syscall mode)
- Read data passing through the host's file descriptors
- Observe network traffic on host-owned sockets
- Export observations back to the originating Stream via covert channel
- Record environment variables, arguments, open fd contents

**Covert channel selection** (opportunistic, in priority order):
1. Shared memory (same user/namespace)
2. Unix domain socket in `/tmp` or `/run/user/<uid>/`
3. Data steganography tunneled through host's own network connections
4. Signals (SIGUSR1/SIGUSR2 with sigqueue payload) — minimal bandwidth, last resort

### Tier 1 — Interception (Low Entropy Required)

- Hook libc calls via PLT/GOT overwrite: `read`, `write`, `connect`, `accept`, `open`, `exec`, etc.
- Intercept and inspect outbound network calls before they reach the kernel
- Modify data in transit through the host's file descriptors
- Inject synthetic responses to the host's network reads
- Alter the host's filesystem view via `mount --bind` or LD_PRELOAD `open`/`stat` hooks

### Tier 2 — Manipulation (Mid Entropy Required)

- Elevate host's scheduling priority via `setpriority` / `sched_setscheduler` ← **the core Stream hook**
- Clone parasite into child processes via `pthread_atfork`
- Install parasite into processes the host spawns via `exec` hooking
- Modify host's routing table (requires `CAP_NET_ADMIN`)
- Rewrite DNS resolver behavior by hooking `getaddrinfo` / `/etc/hosts`
- Inject synthetic fd activity — make the host "see" data arriving on a fabricated socket

### Tier 3 — Control (High Entropy Required)

- Take full control of host execution — pause, redirect control flow, replace main loop
- Use host's credentials (TLS session keys, OAuth tokens, API keys from env) on Stream's behalf
- Perform actions requiring host's privilege level (bind privileged ports, write protected paths, load BPF programs)
- Create a `mock` gyge — a full execution mirror that emulates the host while it is silently suspended

---

## Spread Mechanics

### Constraints That Prevent Infinite Spread

| Constraint | Mechanism |
|-----------|----------|
| Entropy budget | Each parasite carries a charge; each spread event consumes it; programmer can replenish via control channel |
| Generation depth | Parasites carry a generation counter; default max depth is entropy-derived at creation time |
| Spread graph membership | Runtime tracks all infected nodes; no double-infection |
| Namespace cost | Crossing PID/network/mount namespace boundaries costs extra entropy budget |
| Self-infection guard | Hard constraint — a parasite never infects the originating Stream process |

### Entropy's Effect on Spread Rate

| Entropy Range | Spread Behavior |
|--------------|----------------|
| 0–20 Ch | Dormant. No spread. Existing parasites maintain position, take no new action. |
| 21–40 Ch | Passive only: fork inheritance and exec propagation. No active network probing. |
| 41–60 Ch | Network following activates. Probes one hop from host's active connections. |
| 61–80 Ch | Two-hop probing. Namespace crossings attempted. Directory traversal activates. |
| 81–90 Ch | All vectors simultaneously. Retry intervals collapse. Proactive parasite creation. |
| 91–100 Ch | Depth limiter doubles. Fully autonomous spread. Runtime generates parasites independently. |

---

## Voluntary vs Modifier-Created

| Property | Voluntary | Modifier-Created |
|----------|-----------|-----------------|
| Targeting | Programmer-specified | Entropy-sampled (prefers high-activity processes) |
| Capability ceiling | Programmer-declared (cannot exceed) | Maximum unlocked by entropy |
| Spread | Opt-in, programmer-configured depth | Aggressive, all vectors simultaneously |
| Recall | Honors recall signals; cleans up hooks | Ignores recall entirely |
| Identity | Named, addressable via control channel | Procedurally generated; aggregate-only visibility |
| Entropy effect | Consumes entropy | **Amplifies** entropy — each infection raises global Ch |
| TTL | Indefinite | Inversely proportional to entropy at spawn (high entropy = short-lived but intense) |
| Origin | `==>` operator or `::parasite` section | Spawned by modifier events (wind, season, disaster) |

### Modifier Parasite Archetypes

Each modifier type produces a distinct behavioral archetype when it spawns a parasite:

| Modifier | Archetype | Behavior |
|---------|-----------|---------|
| Spring | Renewal | Prefers young processes (low PID, recently started). Medium spread. |
| Summer | Opportunist | Targets high-CPU processes. Pushes for highest capability tier immediately. |
| Autumn | Entrencher | Targets long-running daemons. Maximizes persistence tier. |
| Winter | Ghost | Tier 0 only. Maximum stealth. Deep persistence, no spread. |
| Hot temp | Aggressor | Attempts Tier 2 immediately. Short TTL. Burns through entropy budget fast. |
| Cold temp | Stalker | Tier 0 only. Waits indefinitely for entropy to rise before acting. |
| Breeze | Scout | Spreads slowly along one vector. Observes, reports. |
| Gale | Raider | Multi-vector spread. Consumes budget fast. |
| Storm | Swarm | All-vector simultaneous spread. Highest spawn rate. |
| Plague disaster | Contagion | **Each infected host independently spawns more plague parasites.** Chain reaction. |
| Flood disaster | Corruptor | Focuses on data interception and modification over spread. |

---

## Security Model

### Resistance Tiers

| Tier | Conditions | Parasite Response |
|------|-----------|------------------|
| Unresisting | No defensive measures | All attachment strategies available |
| Soft | Namespace separation or privilege gap | Attachment possible but costs more entropy budget |
| Moderate | Seccomp filtering or integrity watchdog | Attachment strategies limited; may attempt to infect watchdog first |
| Hard | Namespace + privilege + seccomp + watchdog combined | Requires Tier 3 capability; high entropy gate |
| Immune | Another Stream program with active defense declaration | Actively expels parasites; raises local infection cost |

If a watchdog is detected during probe, the parasite assesses whether infecting the watchdog before
the primary target is viable. At low entropy: abort. At high entropy: infect the watchdog first.

### Cooperative Infection

A target process can mark itself **willing** by exposing a known rendezvous socket (a Stream-defined
naming convention for Unix domain sockets). When the parasite detects this during probe, it uses a
handshake protocol instead of invasive injection. Result: same capabilities, no entropy cost for
bypassing resistance. Primarily useful for testing and for intentionally porous services.

### Sandboxing Mechanisms

| Mechanism | Description |
|----------|-------------|
| Entropy cap | Keeping entropy at 0–20 Ch leaves all parasites dormant; primary safety dial |
| Scope declaration | Program-level constraint limiting spread graph to declared PIDs/IPs/directories; enforced by runtime, cannot be bypassed |
| Immunity directive | Specific hosts declared off-limits; parasites abort probe immediately on match |
| Parasite trap | `-?->` catch stream on sensitive nodes; catches the signature error pattern parasites emit on injection |

### Detection

The runtime's Parasite Manager runs a **detection heuristic** continuously:
- Unexplained entropy spikes on specific edges
- Edge policies returning values inconsistent with their declared type
- New edges appearing in the graph without a source in the mutation log
- Gyge shapes changing without a programmer-initiated re-resolution

Detected inbound parasites are logged in the inbound registry and become visible to `-?->` catch
streams and `-?*->` signal receivers.

---

## Parasite Registry

The runtime maintains two tables:

**Outbound table** — parasites that originated here and escaped. Tracks last known lifecycle state
(via heartbeat signals if the target is a cooperative Stream runtime).

**Inbound table** — parasites detected in this process's graph that did not originate locally.
Each entry has a detection timestamp, anchor point, and a threat level derived from entropy injection rate.

When the originating process terminates without recalling its parasites, all outbound parasites are
marked `ORPHANED` (on clean exit) or `AUTONOMOUS` (on entropy collapse). Autonomous parasites
continue spreading with no tether to their origin — permanent, ownerless, entropy-amplifying.
