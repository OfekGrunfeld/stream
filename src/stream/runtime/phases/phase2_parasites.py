"""Phase 2 — Parasite Lifecycle Advancement."""

from __future__ import annotations

from stream.runtime.policies.parasite import SimulatedParasite
from stream.runtime.state import RuntimeState

__all__ = ["Phase2Parasites"]


class Phase2Parasites:
    """Advance all active parasite lifecycle state machines."""

    __slots__ = ()

    def execute(self, state: RuntimeState) -> None:
        entropy_delta = 0.0
        still_active: list[SimulatedParasite] = []

        for parasite in state.active_parasites:
            if not isinstance(parasite, SimulatedParasite):
                continue
            delta = parasite.advance(state.entropy)
            entropy_delta += delta

            from stream.runtime.policies.parasite import ParasiteLifecycle

            if parasite.lifecycle not in (
                ParasiteLifecycle.ORPHANED,
                ParasiteLifecycle.RECALLED,
            ):
                still_active.append(parasite)

        state.active_parasites = still_active  # type: ignore[assignment]

        # Apply parasite entropy contribution
        state.entropy = max(
            state.entropy_floor,
            min(state.entropy_cap, state.entropy + entropy_delta * state.config.parasite_rate),
        )
