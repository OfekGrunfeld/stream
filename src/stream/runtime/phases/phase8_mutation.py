"""Phase 8 — Graph Mutation.

All queued structural changes are applied atomically at end-of-tick.
Mutations deferred here prevent structural modification during iteration.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from stream.runtime.state import RuntimeState
from stream.runtime.types import GIR, SCD

__all__ = ["Phase8Mutation", "MutationKind", "GraphMutation"]


class MutationKind(StrEnum):
    ADD_NODE = "add_node"
    ADD_EDGE = "add_edge"
    REMOVE_EDGE = "remove_edge"
    REMOVE_NODE = "remove_node"
    SECTION_ACTIVATE = "section_activate"
    SECTION_DEACTIVATE = "section_deactivate"


@dataclass(slots=True)
class GraphMutation:
    kind: MutationKind
    node: GIR | None = None
    edge: SCD | None = None
    node_id: str = ""
    edge_id: str = ""


class Phase8Mutation:
    __slots__ = ()

    def execute(self, state: RuntimeState) -> None:
        for mutation in state.mutation_queue:
            if not isinstance(mutation, GraphMutation):
                continue
            match mutation.kind:
                case MutationKind.ADD_NODE:
                    if mutation.node is not None:
                        state.add_node(mutation.node)
                case MutationKind.ADD_EDGE:
                    if mutation.edge is not None:
                        state.add_edge(mutation.edge)
                case MutationKind.REMOVE_EDGE:
                    eid = mutation.edge_id
                    if eid in state.edges:
                        scd = state.edges.pop(eid)
                        # Clean up index
                        out = state.node_out_edges.get(scd.source_id, [])
                        if eid in out:
                            out.remove(eid)
                        inp = state.node_in_edges.get(scd.dest_id, [])
                        if eid in inp:
                            inp.remove(eid)
                case MutationKind.REMOVE_NODE:
                    nid = mutation.node_id
                    if nid in state.nodes:
                        del state.nodes[nid]
                case _:
                    pass
        state.mutation_queue.clear()
