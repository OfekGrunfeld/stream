"""Entropy engine — computes entropy deltas and generates entropy events.

All exact Ch values come from entropy.md.
The engine reads state via a read-only view and returns deltas + events.
State mutation happens only in Phase 0 of the tick loop.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from stream.runtime.types import (
    Ch,
    DisasterKind,
    EdgeId,
    EntropyTier,
    NodeId,
    StreamKind,
    entropy_tier,
)

if TYPE_CHECKING:
    from stream.runtime.state import RuntimeState

__all__ = [
    "EntropyEvent",
    "StreamDisruptionEvent",
    "NodeDisasterEvent",
    "ParasiteInjectionEvent",
    "ModifierShiftEvent",
    "GarbageCascadeEvent",
    "EntropyEngine",
    "compute_delta",
    "STREAM_TYPE_PREMIUMS",
]

# ──────────────────────────────────────────────────────────────────────────────
# Entropy event hierarchy (Observer pattern)
# ──────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class EntropyEvent:
    """Base class for all entropy-driven events."""

    tick: int
    entropy_at_creation: Ch
    impact: float  # relative impact weight (higher = applied first in Phase 5)


@dataclass(frozen=True, slots=True)
class StreamDisruptionEvent(EntropyEvent):
    edge_id: EdgeId = ""
    duration_ticks: int = 5


@dataclass(frozen=True, slots=True)
class NodeDisasterEvent(EntropyEvent):
    node_id: NodeId = ""


@dataclass(frozen=True, slots=True)
class ParasiteInjectionEvent(EntropyEvent):
    target_edge_id: EdgeId = ""


@dataclass(frozen=True, slots=True)
class ModifierShiftEvent(EntropyEvent):
    modifier: str = ""  # "season" | "temp" | "wind"
    new_value: float = 0.0


@dataclass(frozen=True, slots=True)
class GarbageCascadeEvent(EntropyEvent):
    source_node_id: NodeId = ""


# ──────────────────────────────────────────────────────────────────────────────
# Per-stream-type entropy premiums  (from entropy.md)
# ──────────────────────────────────────────────────────────────────────────────

STREAM_TYPE_PREMIUMS: dict[StreamKind, float] = {
    StreamKind.LOSSY: 0.10,  # +0.1 Ch/tick
    StreamKind.THROTTLE: 0.05,  # +0.05 Ch/tick
    StreamKind.FAST: 0.20,  # +0.2 Ch/tick
    StreamKind.SPLITTER: 0.08,  # +0.08 Ch/tick per branch beyond first
    StreamKind.SIGNAL: 0.15,  # +0.15 Ch/tick per signal fired
    StreamKind.ERROR: 0.25,  # +0.25 Ch/tick
    StreamKind.EXIT: 0.50,  # +0.5 Ch flat on invocation
}

# ──────────────────────────────────────────────────────────────────────────────
# Sink contributions (from entropy.md)
# ──────────────────────────────────────────────────────────────────────────────

CLEAN_COMPLETION_DRAIN = -0.5  # Ch flat on clean stream completion
CATCH_INTERCEPT_DRAIN = -0.3  # Ch flat on successful error catch
BLOCK_STREAM_DRAIN = -0.10  # Ch/tick while -x> holds data
WAIT_STREAM_DRAIN = -0.15  # Ch/tick while -,-> is in waiting state
FILTER_STREAM_DRAIN = -0.05  # Ch/tick on active filter without overflow
WINTER_AMBIENT_DRAIN = -0.20  # Ch/tick during winter
WINTER_DEEP_DRAIN = -0.50  # Ch/tick in deep winter (below 20 Ch)

# ──────────────────────────────────────────────────────────────────────────────
# Passive time source
# ──────────────────────────────────────────────────────────────────────────────

PASSIVE_TIME_SOURCE = 0.01  # +0.01 Ch/tick always


# ──────────────────────────────────────────────────────────────────────────────
# Disaster probability tables  (from modifiers.md)
# ──────────────────────────────────────────────────────────────────────────────

# (threshold_ch, prob_at_threshold, prob_at_100, flat_spike)
DISASTER_PARAMS: dict[DisasterKind, tuple[float, float, float, float]] = {
    DisasterKind.ROCKSLIDE: (35.0, 0.010, 0.120, 2.0),
    DisasterKind.FLOOD: (40.0, 0.005, 0.080, 5.0),
    DisasterKind.DROUGHT: (50.0, 0.003, 0.060, 0.0),
    DisasterKind.LIGHTNING: (55.0, 0.002, 0.050, 3.0),
    DisasterKind.PARASITE_BLOOM: (60.0, 0.004, 0.100, 1.0),
    DisasterKind.GLACIER: (15.0, 0.008, 0.008, 0.0),  # winter-only, low-entropy trigger
}


def _disaster_prob(kind: DisasterKind, entropy: Ch, season: str) -> float:
    """Interpolated per-tick probability for a disaster at current entropy."""
    threshold, p_low, p_high, _ = DISASTER_PARAMS[kind]

    if kind == DisasterKind.GLACIER:
        # Only fires when entropy is BELOW threshold during winter
        if season != "winter" or entropy > threshold:
            return 0.0
        return p_low

    if kind == DisasterKind.DROUGHT and season not in ("summer",):
        return 0.0  # drought only in summer (or scorching temp, handled separately)

    if entropy < threshold:
        return 0.0

    # Linear interpolation between threshold and 100
    t = (entropy - threshold) / (100.0 - threshold)
    prob = p_low + t * (p_high - p_low)

    # Season multipliers
    if kind == DisasterKind.ROCKSLIDE and season == "autumn":
        prob *= 2.0
    elif kind == DisasterKind.FLOOD and season == "spring":
        prob *= 1.5

    return prob


# ──────────────────────────────────────────────────────────────────────────────
# Delta computation (Phase 0)
# ──────────────────────────────────────────────────────────────────────────────


def compute_delta(state: RuntimeState) -> tuple[Ch, list[EntropyEvent]]:
    """Compute entropy delta for this tick (Phase 0 computation, read-only).

    Returns:
        (delta_ch, list_of_events_to_schedule)
    """
    delta: Ch = 0.0
    events: list[EntropyEvent] = []
    rng = state.rng

    # ── Sources ──────────────────────────────────────────────────────────

    # Passive time
    delta += PASSIVE_TIME_SOURCE * state.config.entropy_decay_rate

    # Per-edge contributions
    for scd in state.edges.values():
        if scd.state in ("drained",):
            continue

        # Base: any active stream
        base = 0.05
        if len(scd.buffer) > 5:  # heavy load approximation
            base += min(0.15, len(scd.buffer) * 0.01)

        # Backpressure
        dest = state.get_node(scd.dest_id)
        if dest and dest.activation_state == "running":
            base += 0.30  # queued but not draining

        delta += base * state.config.entropy_decay_rate

        # Stream type premiums
        if scd.stream_kind in STREAM_TYPE_PREMIUMS:
            premium = STREAM_TYPE_PREMIUMS[scd.stream_kind]
            delta += premium * state.config.entropy_decay_rate

    # Parasite activity
    for _parasite in state.active_parasites:
        # Each active parasite contributes based on its state
        # (simplified: +0.4 Ch/tick feeding, +0.1 Ch/tick dormant)
        delta += 0.20 * state.config.parasite_rate  # average

    # Active disasters
    for disaster_kind, ticks_remaining in state.active_disasters.items():
        if ticks_remaining > 0:
            if disaster_kind == "flood":
                delta += 0.5
            elif disaster_kind == "drought":
                delta += 0.3

    # ── Sinks ────────────────────────────────────────────────────────────

    # Winter ambient
    if state.season == "winter":
        drain_rate = WINTER_DEEP_DRAIN if state.entropy < 20.0 else WINTER_AMBIENT_DRAIN
        delta += drain_rate * state.config.entropy_sink_rate

    # Blocked streams holding data (anti-entropic)
    for scd in state.edges.values():
        if scd.stream_kind == StreamKind.BLOCKED and len(scd.buffer) > 0:
            delta += BLOCK_STREAM_DRAIN * state.config.entropy_sink_rate
        elif scd.stream_kind == StreamKind.WAIT and scd.state == "blocked":
            delta += WAIT_STREAM_DRAIN * state.config.entropy_sink_rate
        elif scd.stream_kind == StreamKind.FILTER and len(scd.buffer) == 0:
            delta += FILTER_STREAM_DRAIN * state.config.entropy_sink_rate

    # ── Disaster events ───────────────────────────────────────────────────

    for kind in DisasterKind:
        if str(kind) in state.active_disasters:
            continue  # already active
        prob = _disaster_prob(kind, state.entropy, state.season)
        if prob > 0 and rng.random() < prob * state.config.disaster_freq:
            flat_spike = DISASTER_PARAMS[kind][3]
            delta += flat_spike
            # Schedule the event
            events.append(
                StreamDisruptionEvent(
                    tick=state.tick,
                    entropy_at_creation=state.entropy,
                    impact=flat_spike,
                    duration_ticks=15,
                )
            )

    return delta, events


# ──────────────────────────────────────────────────────────────────────────────
# EntropyEngine class
# ──────────────────────────────────────────────────────────────────────────────


class EntropyEngine:
    """Computes entropy state transitions.  No direct state mutation — returns deltas."""

    __slots__ = ("_decay_rate", "_sink_rate")

    def __init__(self, decay_rate: float = 1.0, sink_rate: float = 1.0) -> None:
        self._decay_rate = decay_rate
        self._sink_rate = sink_rate

    def tick(self, state: RuntimeState) -> tuple[Ch, list[EntropyEvent]]:
        return compute_delta(state)

    def apply_vent(self, state: RuntimeState, amount: Ch) -> Ch:
        """SDK vent: drain up to 10 Ch, returns actual drained."""
        actual = min(10.0, amount)
        return actual * self._sink_rate

    @staticmethod
    def tier(ch: Ch) -> EntropyTier:
        return entropy_tier(ch)
