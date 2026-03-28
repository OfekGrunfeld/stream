"""RuntimeLoop — orchestrates the 9-phase tick loop until termination.

Termination conditions (in priority order):
1. Terminal Cascade: entropy reaches 100 Ch (if cap == 100.0)
2. Explicit exit: -!!-> stream fired (state.terminated == True)
3. Natural drain: no packets in flight and all VARIABLE/FUNCTION nodes quiescent
4. Tick limit: state.config.tick_limit reached (safety cap)

The loop uses dependency injection for all engines and phase objects.
No module-level mutable state.
"""

from __future__ import annotations

from collections import deque
from typing import Protocol, runtime_checkable

from stream.runtime.entropy import EntropyEngine
from stream.runtime.modifiers import ModifierEngine
from stream.runtime.phases import (
    Phase0Entropy,
    Phase1Modifiers,
    Phase2Parasites,
    Phase3Delivery,
    Phase4Activation,
    Phase5Events,
    Phase6Signals,
    Phase7Wait,
    Phase8Mutation,
    Phase9GC,
)
from stream.runtime.state import RuntimeState
from stream.runtime.types import ActivationState, EdgeState, GygShape

__all__ = ["RuntimeLoop", "TerminationReason"]

from enum import StrEnum


class TerminationReason(StrEnum):
    TERMINAL_CASCADE = "terminal_cascade"
    EXIT_STREAM = "exit_stream"
    NATURAL_DRAIN = "natural_drain"
    TICK_LIMIT = "tick_limit"


@runtime_checkable
class TickPhase(Protocol):
    def execute(self, state: RuntimeState) -> None: ...


class RuntimeLoop:
    """Runs a built RuntimeState through repeated tick cycles until termination.

    All phase objects and engines are injected — the loop itself is stateless
    between calls to ``run()``.
    """

    __slots__ = (
        "_entropy_engine",
        "_modifier_engine",
        "_phases",
        "_max_quiescent",
    )

    def __init__(
        self,
        entropy_engine: EntropyEngine | None = None,
        modifier_engine: ModifierEngine | None = None,
        phases: list[TickPhase] | None = None,
        max_quiescent: int = 3,
    ) -> None:
        """
        Args:
            entropy_engine: Injected entropy engine (defaults to fresh instance).
            modifier_engine: Injected modifier engine (defaults to fresh instance).
            phases: Override the full phase list (mainly for testing).
            max_quiescent: Consecutive quiescent ticks required to declare natural drain.
        """
        self._max_quiescent = max_quiescent

        if phases is not None:
            self._phases: list[TickPhase] = phases
        else:
            self._entropy_engine: EntropyEngine = entropy_engine or EntropyEngine()
            self._modifier_engine: ModifierEngine = modifier_engine or ModifierEngine()
            self._phases = [
                Phase0Entropy(self._entropy_engine),
                Phase1Modifiers(self._modifier_engine),
                Phase2Parasites(),
                Phase3Delivery(),
                Phase4Activation(),
                Phase5Events(),
                Phase6Signals(),
                Phase7Wait(),
                Phase8Mutation(),
                Phase9GC(),
            ]

    def run(self, state: RuntimeState) -> TerminationReason:
        """Execute tick loop until one of the four termination conditions fires.

        Mutates ``state`` in place.  Returns the reason for termination.
        """
        tick_limit = state.config.tick_limit
        quiescent_count = 0

        while state.tick < tick_limit:
            # ── run all 9 phases ──────────────────────────────────────────────
            for phase in self._phases:
                phase.execute(state)
                # Check exit after each phase so -!!-> stops immediately
                if state.terminated:
                    return TerminationReason.EXIT_STREAM

            state.tick += 1

            # ── Terminal Cascade ──────────────────────────────────────────────
            if state.entropy >= 100.0 and state.entropy_cap >= 100.0:
                _apply_terminal_cascade(state)
                return TerminationReason.TERMINAL_CASCADE

            # ── Natural drain ─────────────────────────────────────────────────
            if _is_quiescent(state):
                quiescent_count += 1
                if quiescent_count >= self._max_quiescent:
                    return TerminationReason.NATURAL_DRAIN
            else:
                quiescent_count = 0

        return TerminationReason.TICK_LIMIT


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────


def _is_quiescent(state: RuntimeState) -> bool:
    """True when no packets are in transit and no active nodes are pending output."""
    # Any edge still buffering packets?
    for scd in state.edges.values():
        if scd.buffer and scd.state not in (EdgeState.DRAINED, EdgeState.DISRUPTED):
            return False

    # Any output port on an active node holding packets?
    for gir in state.nodes.values():
        if gir.activation_state == ActivationState.DRAINED:
            continue
        if gir.shape in (GygShape.VOID, GygShape.GARBAGE):
            continue
        for port_queue in gir.output_ports.values():
            if port_queue:
                return False

    return True


def _apply_terminal_cascade(state: RuntimeState) -> None:
    """Corrupt all in-flight packets and mark the state terminated."""
    from stream.runtime.types import Packet

    state.terminated = True
    state.exit_code = 99  # special sentinel for cascade

    # Corrupt every buffered packet
    for scd in state.edges.values():
        corrupted: deque[Packet] = deque()
        while scd.buffer:
            pkt = scd.buffer.popleft()
            corrupted.append(
                Packet(
                    value=pkt.value,
                    origin_id=pkt.origin_id,
                    tick_born=pkt.tick_born,
                    corrupted=True,
                )
            )
        scd.buffer = corrupted
        scd.state = EdgeState.DISRUPTED

    # Drain all node output ports silently
    for gir in state.nodes.values():
        for port_queue in gir.output_ports.values():
            port_queue.clear()
