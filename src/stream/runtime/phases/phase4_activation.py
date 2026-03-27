"""Phase 4 — Node Activation.

Every node with unprocessed input data is activated.
Shape is resolved lazily on first activation (Gyge Resolver).
Output produced here is available for delivery in the NEXT tick's Phase 3.
"""

from __future__ import annotations

from collections import deque

from stream.runtime.state import RuntimeState
from stream.runtime.types import ActivationState, GIR, GygShape, Packet

__all__ = ["Phase4Activation"]


def _resolve_shape(gir: GIR, packet: Packet, entropy: float) -> GygShape:
    """Lazily determine gyge shape on first activation.

    Order of precedence (from gyge.md):
      1. Packet structure
      2. Declared type hint
      3. Entropy: >90 Ch → 10% chance of garbage
      4. Record in TypeRegistry (done by caller)
    """
    import random
    rng = random.Random()

    # Entropy garbage risk
    if entropy > 90.0 and rng.random() < 0.10:
        return GygShape.GARBAGE

    # Hint-based resolution
    match gir.hint:
        case "%" | "function":
            return GygShape.FUNCTION
        case "@" | "class":
            return GygShape.CLASS
        case "~" | "bytes":
            return GygShape.BYTES
        case "?" | "mock":
            return GygShape.MOCK
        case "!" | "parasite" | "program":
            return GygShape.PROGRAM
        case "pipeline":
            return GygShape.FUNCTION

    # Value-based resolution
    val = packet.value
    if packet.corrupted:
        return GygShape.GARBAGE
    if val is None:
        return GygShape.VOID
    if callable(val):
        return GygShape.FUNCTION
    if isinstance(val, bytes):
        return GygShape.BYTES
    if isinstance(val, dict):
        return GygShape.CLASS
    # Default: variable (stores value)
    return GygShape.VARIABLE


class Phase4Activation:
    """Activate nodes that have input data."""

    __slots__ = ()

    def execute(self, state: RuntimeState) -> None:
        # Collect nodes to activate (priority-fed first, then topological)
        to_activate = [
            gir for gir in state.nodes.values()
            if gir.has_input() and gir.activation_state != ActivationState.DRAINED
        ]

        for gir in to_activate:
            self._activate(gir, state)

    def _activate(self, gir: GIR, state: RuntimeState) -> None:
        in_q = gir.input_ports.get("default")
        if not in_q:
            return

        packet = in_q.popleft()

        # Lazy shape resolution on first activation
        if gir.shape == GygShape.VOID:
            gir.shape = _resolve_shape(gir, packet, state.entropy)
            state.type_registry.register(gir.node_id, gir.shape)

        gir.activation_state = ActivationState.RUNNING

        # Execute based on shape
        output: Packet | None = None
        match gir.shape:
            case GygShape.VARIABLE:
                gir.stored_value = packet.value
                output = packet  # variables re-emit on demand

            case GygShape.FUNCTION:
                if callable(gir.fn_body):
                    try:
                        result = gir.fn_body(packet.value)  # type: ignore[operator]
                        output = Packet(
                            value=result,
                            origin_id=gir.node_id,
                            tick_born=state.tick,
                        )
                    except Exception:
                        output = Packet(
                            value=None,
                            origin_id=gir.node_id,
                            tick_born=state.tick,
                            corrupted=True,
                        )
                else:
                    # No body = variable behaviour
                    gir.stored_value = packet.value
                    output = packet

            case GygShape.BYTES:
                val = packet.value
                if not isinstance(val, bytes):
                    try:
                        val = str(val).encode()
                    except Exception:
                        val = b""
                gir.stored_value = val
                output = Packet(value=val, origin_id=gir.node_id, tick_born=state.tick)

            case GygShape.GARBAGE:
                # Garbage gyge emits corrupted data
                output = Packet(
                    value=packet.value,
                    origin_id=gir.node_id,
                    tick_born=state.tick,
                    corrupted=True,
                )

            case GygShape.VOID:
                # Void gyge is a passthrough / discard
                output = None

            case _:
                # CLASS, PROGRAM, MOCK: pass through for now
                gir.stored_value = packet.value
                output = packet

        if output is not None:
            out_q = gir.output_ports.setdefault("default", deque())
            out_q.append(output)

        gir.activation_state = ActivationState.IDLE

        # If queue is empty and no out-edges → mark DRAINED
        if not gir.has_input() and not state.out_edges(gir.node_id):
            gir.activation_state = ActivationState.DRAINED
