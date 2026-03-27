"""Parasite injection policy: ==> (outward priority stream into another process).

Parasite injection is SIMULATED within the interpreter.  No actual OS-level
process injection is performed.  The policy creates a SimulatedParasite object
that tracks the lifecycle state machine and contributes entropy accordingly.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import StrEnum

from stream.runtime.types import Ch, NodeId, Packet, SCD, StreamKind
from stream.runtime.policies.base import POLICY_REGISTRY

__all__ = ["ParasitePolicy", "SimulatedParasite", "ParasiteLifecycle"]

_rng = random.Random()


def _rand() -> float:
    return _rng.random()


class ParasiteLifecycle(StrEnum):
    DORMANT = "dormant"
    PROBING = "probing"
    ATTACHED = "attached"
    PERSISTENT = "persistent"
    SPREADING = "spreading"
    ORPHANED = "orphaned"
    RECALLED = "recalled"


@dataclass(slots=True)
class SimulatedParasite:
    """In-interpreter simulation of a parasite gyge."""

    name: str
    target_kind: str  # "pid" | "name" | "port" | "broadcast"
    target_value: str
    origin_node_id: NodeId
    lifecycle: ParasiteLifecycle = ParasiteLifecycle.DORMANT
    ticks_alive: int = 0
    entropy_budget: float = 20.0
    tier: int = 0  # capability tier 0–3
    is_voluntary: bool = True

    def advance(self, entropy: Ch) -> float:
        """Advance lifecycle, return entropy delta contributed this tick."""
        self.ticks_alive += 1
        delta = 0.0

        match self.lifecycle:
            case ParasiteLifecycle.DORMANT:
                if entropy > 20.0:
                    self.lifecycle = ParasiteLifecycle.PROBING
                delta = 0.1  # dormant: +0.1 Ch/tick
            case ParasiteLifecycle.PROBING:
                if entropy > 30.0 and _rand() < 0.3:
                    self.lifecycle = ParasiteLifecycle.ATTACHED
                delta = 0.2
            case ParasiteLifecycle.ATTACHED:
                self.entropy_budget -= 0.5
                if self.entropy_budget <= 0:
                    self.lifecycle = ParasiteLifecycle.ORPHANED
                delta = 0.4  # feeding: +0.4 Ch/tick
            case ParasiteLifecycle.SPREADING:
                delta = 0.6
            case _:
                delta = 0.0

        return delta


class ParasitePolicy:
    """==> Parasite injection stream.

    Requires entropy > 60 Ch for @* broadcast.
    Contributes +3.0 Ch flat on spawn, +0.4 Ch/tick while active.
    """

    __slots__ = ()

    def should_deliver(self, packet: Packet, scd: SCD, entropy: Ch) -> bool:
        # Broadcast requires entropy > 60
        if scd.condition == "broadcast" and entropy <= 60.0:
            return False
        return True

    def transform(self, packet: Packet, scd: SCD, entropy: Ch) -> Packet:
        return packet

    def on_blocked(self, scd: SCD, entropy: Ch) -> float:
        return 3.0  # +3.0 Ch flat on spawning a parasite


# ──────────────────────────────────────────────────────────────────────────────
# Registration
# ──────────────────────────────────────────────────────────────────────────────

POLICY_REGISTRY.register(StreamKind.PARASITE, ParasitePolicy())
