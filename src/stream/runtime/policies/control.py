"""Control stream policies: -x> (blocked), -+> (throttle), ->> (fast)."""

from __future__ import annotations

import random

from stream.runtime.policies.base import POLICY_REGISTRY
from stream.runtime.types import SCD, Ch, EdgeState, Packet, StreamKind

__all__ = ["BlockedPolicy", "ThrottlePolicy", "FastPolicy"]

_rng = random.Random()


def _rand() -> float:
    return _rng.random()


# ──────────────────────────────────────────────────────────────────────────────
# -x> Blocked stream
# ──────────────────────────────────────────────────────────────────────────────


class BlockedPolicy:
    """-x> Blocked stream — no data passes until unblocked by a signal.

    Data queues behind the block, building backpressure (+entropy).
    At High entropy: 5% leak per tick.  Floods can override entirely.
    """

    __slots__ = ()

    def should_deliver(self, packet: Packet, scd: SCD, entropy: Ch) -> bool:
        if scd.state == EdgeState.ACTIVE:
            # Normally blocked — but check entropy leak
            if entropy >= 60.0 and _rand() < 0.05:
                return True  # entropy leak
            if entropy >= 80.0 and _rand() < 0.15:
                return True  # heavy leak
            return False
        # Unblocked (signal received → state changed to ACTIVE by signal phase)
        return True

    def transform(self, packet: Packet, scd: SCD, entropy: Ch) -> Packet:
        return packet

    def on_blocked(self, scd: SCD, entropy: Ch) -> float:
        # Buffer builds → entropy
        return 0.30 * min(1.0, len(scd.buffer) / 10.0)


# ──────────────────────────────────────────────────────────────────────────────
# -+> Throttle stream  (token bucket)
# ──────────────────────────────────────────────────────────────────────────────


class ThrottlePolicy:
    """-+> Throttled stream (token bucket).

    Each + adds throttle depth.  Tokens refill at rate R per tick.
    Entropy randomly drains tokens ("entropy drain") and grants bonus tokens.
    """

    __slots__ = ()

    def should_deliver(self, packet: Packet, scd: SCD, entropy: Ch) -> bool:
        # Entropy burst: at extreme, throttle may fail briefly
        if entropy >= 80.0 and _rand() < 0.25:
            return True  # burst through

        if entropy >= 40.0 and _rand() < 0.10:
            return True  # mid-entropy burst

        if scd.token_bucket >= 1.0:
            scd.token_bucket -= 1.0
            return True
        return False

    def transform(self, packet: Packet, scd: SCD, entropy: Ch) -> Packet:
        return packet

    def on_blocked(self, scd: SCD, entropy: Ch) -> float:
        # Refill tokens (called each tick regardless)
        refill = scd.token_refill_rate

        # Entropy drain: randomly consume tokens
        if entropy >= 25.0:
            drain = _rand() * 0.5 * (entropy / 100.0)
            scd.token_bucket = max(0.0, scd.token_bucket - drain)

        # Entropy surge: occasionally grant bonus
        if entropy >= 40.0 and _rand() < 0.05:
            scd.token_bucket = min(scd.token_bucket_capacity, scd.token_bucket + 3.0)

        scd.token_bucket = min(scd.token_bucket_capacity, scd.token_bucket + refill)
        return 0.05  # +0.05 Ch/tick premium


# ──────────────────────────────────────────────────────────────────────────────
# ->> Fast stream
# ──────────────────────────────────────────────────────────────────────────────


class FastPolicy:
    """->> Fast stream — extra delivery attempts per tick.

    level = count of extra >.  Contributes +0.2 Ch/tick to entropy.
    At High entropy: 5% chance/tick of converting to error stream behaviour.
    At Scorching temp + Extreme entropy: near-guaranteed failure within 10 ticks.
    """

    __slots__ = ()

    def should_deliver(self, packet: Packet, scd: SCD, entropy: Ch) -> bool:
        if entropy >= 80.0:
            # 15% overheating → error stream conversion
            if _rand() < 0.15:
                scd.state = EdgeState.DISRUPTED
                return False
            return True
        if entropy >= 60.0:
            # 5% overheating
            if _rand() < 0.05:
                scd.state = EdgeState.DISRUPTED
                return False
        return True

    def transform(self, packet: Packet, scd: SCD, entropy: Ch) -> Packet:
        return packet  # fast doesn't corrupt data

    def on_blocked(self, scd: SCD, entropy: Ch) -> float:
        # +0.2 Ch/tick premium for fast streams
        return 0.20


# ──────────────────────────────────────────────────────────────────────────────
# Registration
# ──────────────────────────────────────────────────────────────────────────────

POLICY_REGISTRY.register(StreamKind.BLOCKED, BlockedPolicy())
POLICY_REGISTRY.register(StreamKind.THROTTLE, ThrottlePolicy())
POLICY_REGISTRY.register(StreamKind.FAST, FastPolicy())
