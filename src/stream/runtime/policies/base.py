"""StreamPolicy Protocol and policy factory registry."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from stream.runtime.types import Ch, EdgeState, Packet, SCD, StreamKind

__all__ = ["StreamPolicy", "PolicyRegistry", "POLICY_REGISTRY"]


@runtime_checkable
class StreamPolicy(Protocol):
    """Behavioural interface for a typed stream edge.

    All three hooks are called by Phase 3 (Edge Delivery) on every tick.
    """

    def should_deliver(self, packet: Packet, scd: SCD, entropy: Ch) -> bool:
        """Return True if this packet should be delivered this tick."""
        ...

    def transform(self, packet: Packet, scd: SCD, entropy: Ch) -> Packet:
        """Optionally mutate the packet in transit.  Return unchanged or new packet."""
        ...

    def on_blocked(self, scd: SCD, entropy: Ch) -> float:
        """Called when destination is saturated.  Returns entropy delta contribution."""
        ...


class PolicyRegistry:
    """Maps StreamKind → StreamPolicy instance (Strategy pattern)."""

    __slots__ = ("_registry",)

    def __init__(self) -> None:
        self._registry: dict[StreamKind, StreamPolicy] = {}

    def register(self, kind: StreamKind, policy: StreamPolicy) -> None:
        self._registry[kind] = policy

    def get(self, kind: StreamKind) -> StreamPolicy:
        policy = self._registry.get(kind)
        if policy is None:
            # Fallback to basic stream policy
            return self._registry[StreamKind.BASIC]
        return policy

    def __contains__(self, kind: StreamKind) -> bool:
        return kind in self._registry


# Module-level singleton — populated by each policy module at import
POLICY_REGISTRY: PolicyRegistry = PolicyRegistry()
