"""Error stream policies: -!-> (raise), -!!-> (exit), -?-> (catch)."""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from stream.runtime.types import Ch, NodeId, Packet, SCD, StreamKind
from stream.runtime.policies.base import POLICY_REGISTRY

__all__ = ["ErrorPolicy", "ExitPolicy", "CatchPolicy", "ErrorEvent"]

_rng = random.Random()


def _rand() -> float:
    return _rng.random()


# ──────────────────────────────────────────────────────────────────────────────
# Error event (placed in RuntimeState.error_queue by -!-> edges)
# ──────────────────────────────────────────────────────────────────────────────


@dataclass(slots=True)
class ErrorEvent:
    payload: Packet
    source_edge_id: str
    source_node_id: NodeId
    entropy_at_raise: Ch
    tick: int
    caught: bool = False


# ──────────────────────────────────────────────────────────────────────────────
# -!-> Error stream
# ──────────────────────────────────────────────────────────────────────────────


class ErrorPolicy:
    """-!-> Error stream — converts data into an ErrorEvent in the error queue.

    At High entropy (60–80 Ch): 15% cascade to adjacent streams.
    At Extreme (80+ Ch): error-on-error chains possible.
    """

    __slots__ = ()

    def should_deliver(self, packet: Packet, scd: SCD, entropy: Ch) -> bool:
        # Error streams always "deliver" — the delivery IS raising the error
        return True

    def transform(self, packet: Packet, scd: SCD, entropy: Ch) -> Packet:
        # The error payload is the packet itself
        return Packet(
            value=packet.value,
            origin_id=packet.origin_id,
            tick_born=packet.tick_born,
            corrupted=True,
        )

    def on_blocked(self, scd: SCD, entropy: Ch) -> float:
        # +0.25 Ch/tick — errors are inherently disorderly
        return 0.25


# ──────────────────────────────────────────────────────────────────────────────
# -!!-> Exit stream
# ──────────────────────────────────────────────────────────────────────────────


class ExitPolicy:
    """-!!-> Exit stream — terminates the program when data flows through.

    At Extreme entropy: exit signal may require re-sending (+0.5 Ch each retry).
    During active disaster: runtime may refuse to exit.
    """

    __slots__ = ()

    def should_deliver(self, packet: Packet, scd: SCD, entropy: Ch) -> bool:
        if entropy >= 80.0 and _rand() < 0.20:
            # Exit signal may fail to route at extreme entropy
            return False
        return True

    def transform(self, packet: Packet, scd: SCD, entropy: Ch) -> Packet:
        # Exit code is the packet value (normalised to int)
        val = packet.value
        code = int(val) if isinstance(val, (int, float)) else 0
        return Packet(value=code, origin_id=packet.origin_id, tick_born=packet.tick_born)

    def on_blocked(self, scd: SCD, entropy: Ch) -> float:
        return 0.50  # +0.5 Ch flat on invocation


# ──────────────────────────────────────────────────────────────────────────────
# -?-> Catch stream
# ──────────────────────────────────────────────────────────────────────────────


class CatchPolicy:
    """-?-> Catch stream — intercepts ErrorEvents from the error queue.

    100% catch rate at Calm; 80% at High; 60% at Extreme.
    Consuming an error drains −0.3 Ch flat.
    """

    __slots__ = ()

    def should_deliver(self, packet: Packet, scd: SCD, entropy: Ch) -> bool:
        # Catch streams filter against the error queue, not the buffer
        # should_deliver is called for normal packet passthrough
        if entropy >= 80.0:
            return _rand() > 0.40  # 60% catch
        if entropy >= 60.0:
            return _rand() > 0.20  # 80% catch
        if entropy >= 25.0:
            return _rand() > 0.05  # 95% catch
        return True  # 100% catch

    def transform(self, packet: Packet, scd: SCD, entropy: Ch) -> Packet:
        # Deliver the error payload to the catch destination
        return packet

    def on_blocked(self, scd: SCD, entropy: Ch) -> float:
        if entropy >= 60.0:
            return 0.10  # overloaded catch: +0.1 Ch/tick
        return -0.30  # clean catch: −0.3 Ch flat


# ──────────────────────────────────────────────────────────────────────────────
# Registration
# ──────────────────────────────────────────────────────────────────────────────

POLICY_REGISTRY.register(StreamKind.ERROR, ErrorPolicy())
POLICY_REGISTRY.register(StreamKind.EXIT, ExitPolicy())
POLICY_REGISTRY.register(StreamKind.CATCH, CatchPolicy())
