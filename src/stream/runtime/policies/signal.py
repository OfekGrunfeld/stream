"""Signal stream policies: -*-> (send signal), -?*-> (receive signal)."""

from __future__ import annotations

import random
from dataclasses import dataclass

from stream.runtime.types import Ch, NodeId, Packet, SCD, StreamKind
from stream.runtime.policies.base import POLICY_REGISTRY

__all__ = ["SignalPolicy", "ReceivePolicy", "SignalEvent"]

_rng = random.Random()


def _rand() -> float:
    return _rng.random()


@dataclass(slots=True)
class SignalEvent:
    payload: Packet
    source_id: NodeId
    dest_id: str  # NodeId or target string
    tick: int


# ──────────────────────────────────────────────────────────────────────────────
# -*-> Send signal
# ──────────────────────────────────────────────────────────────────────────────


class SignalPolicy:
    """Signal stream (*->).

    Out-of-band — processed in Phase 6 after normal delivery.
    Reliable at Calm; 5% duplicate/loss at High; 70%/15%/15% at Extreme.
    +0.15 Ch/tick per signal fired.
    """

    __slots__ = ()

    def should_deliver(self, packet: Packet, scd: SCD, entropy: Ch) -> bool:
        if entropy >= 80.0:
            r = _rand()
            if r < 0.15:
                return False  # lost
            # 15% duplicate: deliver but also leave in queue for next tick
        elif entropy >= 60.0:
            if _rand() < 0.05:
                return False  # lost
        return True

    def transform(self, packet: Packet, scd: SCD, entropy: Ch) -> Packet:
        return packet

    def on_blocked(self, scd: SCD, entropy: Ch) -> float:
        return 0.15  # +0.15 Ch/tick per signal fired


# ──────────────────────────────────────────────────────────────────────────────
# -?*-> Receive signal
# ──────────────────────────────────────────────────────────────────────────────


class ReceivePolicy:
    """-?*-> Receive signal.

    Listens for signals.  Phantom signals at Mid (2%), 20% at Extreme.
    At 90+ Ch: may receive signals from parasites in other programs.
    """

    __slots__ = ()

    def should_deliver(self, packet: Packet, scd: SCD, entropy: Ch) -> bool:
        return True  # always deliver received signals

    def transform(self, packet: Packet, scd: SCD, entropy: Ch) -> Packet:
        # Phantom signals: inject synthetic data
        if entropy >= 80.0 and _rand() < 0.20:
            return Packet(
                value="[phantom]",
                origin_id="phantom",
                tick_born=packet.tick_born,
                corrupted=True,
            )
        elif entropy >= 25.0 and _rand() < 0.02:
            return Packet(
                value="[phantom]",
                origin_id="phantom",
                tick_born=packet.tick_born,
                corrupted=True,
            )
        return packet

    def on_blocked(self, scd: SCD, entropy: Ch) -> float:
        return 0.0


# ──────────────────────────────────────────────────────────────────────────────
# Registration
# ──────────────────────────────────────────────────────────────────────────────

POLICY_REGISTRY.register(StreamKind.SIGNAL, SignalPolicy())
POLICY_REGISTRY.register(StreamKind.RECEIVE, ReceivePolicy())
