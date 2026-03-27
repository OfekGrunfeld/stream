"""Phase 5 — Entropy Event Resolution.

Applies events queued in Phase 0, in impact-descending order.
"""

from __future__ import annotations

from stream.runtime.entropy import (
    GarbageCascadeEvent,
    ModifierShiftEvent,
    NodeDisasterEvent,
    ParasiteInjectionEvent,
    StreamDisruptionEvent,
)
from stream.runtime.state import RuntimeState
from stream.runtime.types import EdgeState, GygShape

__all__ = ["Phase5Events"]


class Phase5Events:
    __slots__ = ()

    def execute(self, state: RuntimeState) -> None:
        events = sorted(
            state.pending_entropy_events,
            key=lambda e: e.impact,
            reverse=True,
        )
        state.pending_entropy_events.clear()

        for event in events:
            match event:
                case StreamDisruptionEvent(edge_id=eid, duration_ticks=dur):
                    scd = state.get_edge(eid)
                    if scd is not None:
                        scd.state = EdgeState.DISRUPTED
                        scd.disruption_ticks_remaining = dur

                case NodeDisasterEvent(node_id=nid):
                    node = state.get_node(nid)
                    if node is not None:
                        node.input_ports.clear()
                        node.output_ports.clear()

                case GarbageCascadeEvent(source_node_id=nid):
                    node = state.get_node(nid)
                    if node is not None:
                        node.shape = GygShape.GARBAGE
                        state.type_registry.reclassify(nid, GygShape.GARBAGE)

                case ModifierShiftEvent(modifier=mod, new_value=val):
                    if mod == "season":
                        from stream.runtime.types import Season
                        try:
                            state.season = Season(str(val))
                        except ValueError:
                            pass

                case _:
                    pass  # unknown event types are ignored
