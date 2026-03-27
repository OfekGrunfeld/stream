"""Wait stream policy: -,-> (wait for condition before releasing data)."""

from __future__ import annotations

import random
import time

from stream.runtime.types import Ch, EdgeState, Packet, SCD, StreamKind
from stream.runtime.policies.base import POLICY_REGISTRY

__all__ = ["WaitPolicy"]

_rng = random.Random()


def _rand() -> float:
    return _rng.random()


class WaitPolicy:
    """-,-> Wait stream — holds data until a condition is satisfied.

    Drains −0.15 Ch/tick while in waiting state (intentional stillness is
    anti-entropic).  More commas = harder/longer wait.

    Condition types supported (parsed from SCD.condition):
        t:500        → wait N ticks
        sig:NAME     → wait for named OS signal (checked via signal queue)
        |flag|       → wait until gyge is non-zero/non-empty
        @pid:N       → wait until PID N exists
        !|err|       → wait until error gyge clears
        stream:|x|   → wait until stream x is drained

    No condition (-,->) → intentional deadlock (park).
    """

    __slots__ = ()

    def _is_condition_met(self, scd: SCD, entropy: Ch) -> bool:
        """Check if the wait condition is satisfied this tick."""
        cond = (scd.condition or "").strip()

        if not cond:
            return False  # intentional deadlock

        # Time-based wait: t:N  (N ticks; tracked via disruption_ticks_remaining)
        if cond.startswith("t:"):
            try:
                limit = int(cond[2:])
                # Using disruption_ticks_remaining as a countdown
                if scd.disruption_ticks_remaining <= 0:
                    scd.disruption_ticks_remaining = limit * scd.level
                scd.disruption_ticks_remaining -= 1
                return scd.disruption_ticks_remaining <= 0
            except ValueError:
                return False

        # Everything else: assume not met (requires runtime integration)
        # The runtime loop injects a "condition resolved" signal
        return False

    def should_deliver(self, packet: Packet, scd: SCD, entropy: Ch) -> bool:
        # Early wake at high entropy
        if entropy >= 80.0 and _rand() < 0.20:
            return True  # flood wakes wait stream
        if entropy >= 60.0 and _rand() < 0.10:
            return True  # early wake

        # Duration variance at High entropy
        return self._is_condition_met(scd, entropy)

    def transform(self, packet: Packet, scd: SCD, entropy: Ch) -> Packet:
        return packet

    def on_blocked(self, scd: SCD, entropy: Ch) -> float:
        # −0.15 Ch/tick while intentionally waiting (anti-entropic)
        return -0.15


# ──────────────────────────────────────────────────────────────────────────────
# Registration
# ──────────────────────────────────────────────────────────────────────────────

POLICY_REGISTRY.register(StreamKind.WAIT, WaitPolicy())
