"""Basic stream policies: -> (standard), => (priority), ~> (lossy).

Entropy degradation from entropy.md Stream Effects table.
"""

from __future__ import annotations

import random

from stream.runtime.types import Ch, Packet, SCD, StreamKind
from stream.runtime.policies.base import POLICY_REGISTRY, StreamPolicy

__all__ = ["BasicPolicy", "PriorityPolicy", "LossyPolicy"]

_rng = random.Random()  # module-local RNG; seeded from RuntimeState.rng in loop


def _rand() -> float:
    return _rng.random()


def _set_seed(seed: int | None) -> None:
    _rng.seed(seed)


# ──────────────────────────────────────────────────────────────────────────────
# -> Standard stream
# ──────────────────────────────────────────────────────────────────────────────


class BasicPolicy:
    """One-way stream (->).

    Fully reliable below 25 Ch.  Delays accumulate at Mid; reordering at High;
    spontaneous ~> conversion at Extreme (3% per tick).
    """

    __slots__ = ()

    def should_deliver(self, packet: Packet, scd: SCD, entropy: Ch) -> bool:
        if entropy < 25.0:
            return True
        if entropy < 60.0:
            # 2% tick-level delay at Mid
            return _rand() > 0.02
        if entropy < 80.0:
            # 8% delay at High
            return _rand() > 0.08
        # Extreme: 15% delay
        return _rand() > 0.15

    def transform(self, packet: Packet, scd: SCD, entropy: Ch) -> Packet:
        if entropy >= 80.0 and _rand() < 0.03:
            # 3% chance per tick: spontaneous conversion to lossy behaviour
            # (mark packet as potentially lossy — actual loss handled by ~> policy)
            return Packet(
                value=packet.value,
                origin_id=packet.origin_id,
                tick_born=packet.tick_born,
                corrupted=entropy >= 90.0,
            )
        return packet

    def on_blocked(self, scd: SCD, entropy: Ch) -> float:
        # Backpressure: +0.3 Ch/tick if buffer is building
        return 0.30 if len(scd.buffer) > 3 else 0.0


# ──────────────────────────────────────────────────────────────────────────────
# => Priority stream
# ──────────────────────────────────────────────────────────────────────────────


class PriorityPolicy:
    """Priority stream (=>).

    Processed before all -> edges in Phase 3 Pass A.
    Reliable until High (10% inversion), breaks at Extreme (25% scramble).
    """

    __slots__ = ()

    def should_deliver(self, packet: Packet, scd: SCD, entropy: Ch) -> bool:
        if entropy < 25.0:
            return True
        if entropy < 60.0:
            # Minor jitter but still delivers
            return True
        if entropy < 80.0:
            # 10% priority inversion (may behave as ->)
            return _rand() > 0.10
        # Extreme: 25% scramble
        return _rand() > 0.25

    def transform(self, packet: Packet, scd: SCD, entropy: Ch) -> Packet:
        return packet  # priority streams don't corrupt data

    def on_blocked(self, scd: SCD, entropy: Ch) -> float:
        # Re-queues for next tick — no additional entropy
        return 0.0


# ──────────────────────────────────────────────────────────────────────────────
# ~> Lossy stream
# ──────────────────────────────────────────────────────────────────────────────

_LOSSY_BASE_LOSS_RATE = 0.05  # 5% default


class LossyPolicy:
    """Lossy stream (~>).

    Data may not arrive.  Loss rate scales with entropy and temperature.
    At extreme entropy can consume data from adjacent streams.
    """

    __slots__ = ()

    def should_deliver(self, packet: Packet, scd: SCD, entropy: Ch) -> bool:
        # Effective loss rate scaled by entropy tier
        base = _LOSSY_BASE_LOSS_RATE
        if entropy < 25.0:
            multiplier = 1.0
        elif entropy < 60.0:
            multiplier = 1.5
        elif entropy < 80.0:
            multiplier = 3.0
        else:
            multiplier = 5.0
        loss_rate = min(0.95, base * multiplier)
        return _rand() > loss_rate

    def transform(self, packet: Packet, scd: SCD, entropy: Ch) -> Packet:
        # At extreme entropy, corrupt surviving packets
        if entropy >= 80.0 and _rand() < 0.15:
            return Packet(
                value=packet.value,
                origin_id=packet.origin_id,
                tick_born=packet.tick_born,
                corrupted=True,
            )
        return packet

    def on_blocked(self, scd: SCD, entropy: Ch) -> float:
        return 0.0  # lossy streams drop data rather than building backpressure


# ──────────────────────────────────────────────────────────────────────────────
# Registration
# ──────────────────────────────────────────────────────────────────────────────

POLICY_REGISTRY.register(StreamKind.BASIC, BasicPolicy())
POLICY_REGISTRY.register(StreamKind.PRIORITY, PriorityPolicy())
POLICY_REGISTRY.register(StreamKind.LOSSY, LossyPolicy())
