"""Feedback loop policy: <~ (loop back-edge)."""

from __future__ import annotations

from stream.runtime.types import Ch, Packet, SCD, StreamKind
from stream.runtime.policies.base import POLICY_REGISTRY

__all__ = ["FeedbackPolicy"]


class FeedbackPolicy:
    """<~ Feedback loop — back-edge creating a cycle in the stream graph.

    Processed last within Phase 3 Pass B to prevent infinite in-tick loops.
    The back-edge delivers to the *start* of the cycle, not its downstream.
    """

    __slots__ = ()

    def should_deliver(self, packet: Packet, scd: SCD, entropy: Ch) -> bool:
        # Feedback always attempts delivery; the cycle is the programmer's intent
        return True

    def transform(self, packet: Packet, scd: SCD, entropy: Ch) -> Packet:
        return packet

    def on_blocked(self, scd: SCD, entropy: Ch) -> float:
        return 0.0  # cycles themselves don't add entropy beyond normal stream cost


# ──────────────────────────────────────────────────────────────────────────────
# Registration
# ──────────────────────────────────────────────────────────────────────────────

POLICY_REGISTRY.register(StreamKind.FEEDBACK, FeedbackPolicy())
