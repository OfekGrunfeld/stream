"""Phase 1 — Modifier Application (seasons, temperature, wind)."""

from __future__ import annotations

from stream.runtime.modifiers import ModifierEngine
from stream.runtime.state import RuntimeState

__all__ = ["Phase1Modifiers"]


class Phase1Modifiers:
    __slots__ = ("_engine",)

    def __init__(self, engine: ModifierEngine) -> None:
        self._engine = engine

    def execute(self, state: RuntimeState) -> None:
        # Modifier engine updates season/temp/wind in-place and returns attractor delta
        attractor_delta = self._engine.tick(state)
        # Apply attractor nudge on top of Phase 0 entropy
        state.entropy = max(
            state.entropy_floor,
            min(state.entropy_cap, state.entropy + attractor_delta),
        )
