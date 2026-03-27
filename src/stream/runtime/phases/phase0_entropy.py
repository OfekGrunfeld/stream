"""Phase 0 — Entropy Recalculation.

Computes the delta for global entropy (sources − sinks) and schedules entropy
events.  Read-only view of graph state; no direct mutations.  Mutations are
applied here after computation (entropy is the exception — it updates immediately
so later phases see the correct tier).
"""

from __future__ import annotations

from typing import Protocol

from stream.runtime.entropy import EntropyEngine
from stream.runtime.state import RuntimeState
from stream.runtime.types import Ch

__all__ = ["Phase0Entropy"]


class Phase0Entropy:
    """Compute and apply entropy delta for this tick."""

    __slots__ = ("_engine",)

    def __init__(self, engine: EntropyEngine) -> None:
        self._engine = engine

    def execute(self, state: RuntimeState) -> None:
        delta, events = self._engine.tick(state)

        # Apply delta (clamped to [floor, cap])
        new_entropy: Ch = state.entropy + delta
        new_entropy = max(state.entropy_floor, min(state.entropy_cap, new_entropy))
        state.entropy = new_entropy

        # Schedule events for Phase 5
        state.pending_entropy_events.extend(events)
