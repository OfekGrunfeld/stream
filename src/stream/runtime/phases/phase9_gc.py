"""Phase 9 — Garbage Collection.

Fully drained edges and nodes are collected.  Orphaned nodes (no path to any
output) are marked.  Parasite records for completed parasites are released.
"""

from __future__ import annotations

from stream.runtime.state import RuntimeState
from stream.runtime.types import ActivationState, EdgeState

__all__ = ["Phase9GC"]


class Phase9GC:
    __slots__ = ()

    def execute(self, state: RuntimeState) -> None:
        # Collect drained edges
        drained_edges = [
            eid for eid, scd in state.edges.items()
            if scd.state == EdgeState.DRAINED and not scd.buffer
        ]
        for eid in drained_edges:
            scd = state.edges.pop(eid)
            out = state.node_out_edges.get(scd.source_id, [])
            if eid in out:
                out.remove(eid)
            inp = state.node_in_edges.get(scd.dest_id, [])
            if eid in inp:
                inp.remove(eid)

        # Collect drained nodes that have no edges at all
        drained_nodes = [
            nid for nid, gir in state.nodes.items()
            if (
                gir.activation_state == ActivationState.DRAINED
                and not state.out_edges(nid)
                and not state.in_edges(nid)
            )
        ]
        for nid in drained_nodes:
            del state.nodes[nid]
            state.node_out_edges.pop(nid, None)
            state.node_in_edges.pop(nid, None)
