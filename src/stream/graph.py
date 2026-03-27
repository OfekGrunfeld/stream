"""Graph Builder — converts a ProgramASG into a populated RuntimeState.

Responsibilities:
- Create GIR nodes for every GygeNode in the ASG
- Create SCD edges for every StreamEdge, with the correct policy
- Pre-configure modifier state from ::header:: section
- Compute topological order (with cycle detection / back-edge flagging)
- Seed the RNG from ProgramConfig
"""

from __future__ import annotations

import random
from collections import defaultdict, deque

from stream.errors import BuildError
from stream.parser import (
    AllocStmt,
    AnyNode,
    AnyStmt,
    AssignStmt,
    BranchBlockNode,
    DeallocStmt,
    EntryPointStmt,
    GygeNode,
    ImportStmt,
    LiteralNode,
    ModifierNode,
    ModifierSetStmt,
    ProgramASG,
    Section,
    SignalReceiveStmt,
    StreamEdge,
    TargetNode,
    VoidNode,
)
from stream.parser import StreamKind as ASTStreamKind
from stream.runtime.gyge import GyrResolver
from stream.runtime.state import ProgramConfig, RuntimeState
from stream.runtime.types import (
    GIR,
    GygShape,
    Packet,
    SCD,
    Season,
    StreamKind,
    TypeRegistry,
)

__all__ = ["build", "GraphBuilder"]

# Map from AST StreamKind to runtime StreamKind
_SK_MAP: dict[ASTStreamKind, StreamKind] = {
    ASTStreamKind.BASIC: StreamKind.BASIC,
    ASTStreamKind.PRIORITY: StreamKind.PRIORITY,
    ASTStreamKind.LOSSY: StreamKind.LOSSY,
    ASTStreamKind.FILTER: StreamKind.FILTER,
    ASTStreamKind.FILTER_COND: StreamKind.FILTER_COND,
    ASTStreamKind.BLOCKED: StreamKind.BLOCKED,
    ASTStreamKind.THROTTLE: StreamKind.THROTTLE,
    ASTStreamKind.FAST: StreamKind.FAST,
    ASTStreamKind.SWITCH: StreamKind.SWITCH,
    ASTStreamKind.BATCHER: StreamKind.BATCHER,
    ASTStreamKind.SPLITTER: StreamKind.SPLITTER,
    ASTStreamKind.ARG_FILTER: StreamKind.ARG_FILTER,
    ASTStreamKind.ERROR: StreamKind.ERROR,
    ASTStreamKind.EXIT: StreamKind.EXIT,
    ASTStreamKind.CATCH: StreamKind.CATCH,
    ASTStreamKind.SIGNAL: StreamKind.SIGNAL,
    ASTStreamKind.RECEIVE: StreamKind.RECEIVE,
    ASTStreamKind.WAIT: StreamKind.WAIT,
    ASTStreamKind.PARASITE: StreamKind.PARASITE,
    ASTStreamKind.FEEDBACK: StreamKind.FEEDBACK,
}


class GraphBuilder:
    """Converts a ProgramASG + ProgramConfig into a RuntimeState."""

    __slots__ = ("_asg", "_cfg", "_state", "_resolver", "_ast_to_runtime_id")

    def __init__(self, asg: ProgramASG, cfg: ProgramConfig | None = None) -> None:
        self._asg = asg
        self._cfg = cfg or ProgramConfig()
        self._state = RuntimeState(config=self._cfg)
        self._resolver = GyrResolver(self._state.type_registry)
        # Map from AST node_id → runtime GIR node_id (usually same, but kept explicit)
        self._ast_to_runtime_id: dict[str, str] = {}

    def build(self) -> RuntimeState:
        """Full build pipeline."""
        state = self._state

        # Seed RNG
        state.rng = random.Random(self._cfg.seed)
        state.entropy = self._cfg.entropy_initial
        state.entropy_cap = self._cfg.entropy_cap
        state.season_duration = self._cfg.season_duration
        state.season_lock = self._cfg.season_lock
        state.wind_enabled = self._cfg.wind_enabled

        # Step 1: Create GIR nodes for all named gyges
        for name, ast_node in self._asg.nodes.items():
            gir = self._make_gir(ast_node)
            state.add_node(gir)
            self._ast_to_runtime_id[ast_node.node_id] = gir.node_id

        # Step 2: Process ::header:: statements first (entry, entropy, season)
        for section in self._asg.sections:
            if section.name.lower() in ("header",):
                self._apply_section_stmts(section, state)

        # Step 3: Process remaining sections
        for section in self._asg.sections:
            if section.name.lower() not in ("header",):
                self._apply_section_stmts(section, state)

        # Step 4: Create SCD edges for all stream edges
        for ast_edge in self._asg.all_edges:
            self._make_edge(ast_edge, state)

        # Step 5: Compute topological order
        state.topo_order = self._topo_sort(state)

        # Step 6: Pre-seed initial values from assignments
        self._seed_initial_values(state)

        return state

    def _make_gir(self, ast_node: AnyNode) -> GIR:
        """Create a GIR from an AST node."""
        match ast_node:
            case GygeNode(name=name, hint=hint, node_id=nid):
                gir = GIR(name=name, hint=hint)
                # Check for built-in function
                fn = self._resolver.get_builtin(name)
                if fn is not None:
                    gir.shape = GygShape.FUNCTION
                    gir.fn_body = fn
                return gir

            case LiteralNode(value=val, node_id=nid):
                gir = GIR(name=f"__lit_{nid[:8]}")
                gir.shape = GygShape.VARIABLE
                gir.stored_value = val
                return gir

            case ModifierNode(kind=kind, node_id=nid):
                gir = GIR(name=f"$${kind}")
                gir.shape = GygShape.VARIABLE
                return gir

            case TargetNode(kind=kind, value=val, node_id=nid):
                gir = GIR(name=f"@{kind}:{val}")
                gir.shape = GygShape.VARIABLE
                return gir

            case VoidNode(node_id=nid):
                gir = GIR(name="__void__")
                gir.shape = GygShape.VOID
                return gir

            case BranchBlockNode(node_id=nid):
                gir = GIR(name=f"__branch_{nid[:8]}")
                gir.shape = GygShape.VOID
                return gir

            case _:
                gir = GIR(name="__unknown__")
                return gir

    def _make_edge(self, ast_edge: StreamEdge, state: RuntimeState) -> None:
        """Create an SCD from an AST StreamEdge."""
        src_id = self._ast_to_runtime_id.get(ast_edge.source_id)
        dst_id = self._ast_to_runtime_id.get(ast_edge.dest_id)

        if src_id is None or dst_id is None:
            # Edge references a node not yet in the graph — skip
            return

        runtime_kind = _SK_MAP.get(ast_edge.kind, StreamKind.BASIC)

        scd = SCD(
            stream_kind=runtime_kind,
            source_id=src_id,
            dest_id=dst_id,
            condition=ast_edge.condition,
            level=ast_edge.level,
            is_back_edge=ast_edge.is_back_edge,
        )
        state.add_edge(scd)

    def _apply_section_stmts(self, section: Section, state: RuntimeState) -> None:
        """Process statements from a section."""
        for stmt in section.stmts:
            self._apply_stmt(stmt, state)

    def _apply_stmt(self, stmt: AnyStmt, state: RuntimeState) -> None:
        match stmt:
            case EntryPointStmt(name=name):
                state.config.entropy_initial = state.entropy  # keep current

            case ModifierSetStmt(modifier="season", value=val):
                if val and val != "$S":
                    try:
                        state.season = Season(val)
                        state.season_lock = Season(val)
                    except ValueError:
                        pass

            case ModifierSetStmt(modifier="entropy", value=val):
                if val == "...":
                    state.entropy = state.rng.uniform(5.0, 30.0)
                else:
                    try:
                        state.entropy = float(val)
                    except ValueError:
                        pass

            case AssignStmt(target=target, rhs=rhs):
                # Pre-seed stored values for named gyges
                nid = self._ast_to_runtime_id.get(target.node_id)
                if nid is None:
                    return
                gir = state.get_node(nid)
                if gir is None:
                    return
                match rhs:
                    case LiteralNode(value=val):
                        gir.stored_value = val
                        gir.shape = GygShape.VARIABLE
                    case VoidNode():
                        gir.shape = GygShape.VOID
                    case _:
                        pass

            case AllocStmt(target=target):
                nid = self._ast_to_runtime_id.get(target.node_id)
                if nid:
                    gir = state.get_node(nid)
                    if gir:
                        gir.shape = GygShape.BYTES
                        gir.stored_value = bytearray()

            case _:
                pass  # other stmts handled at runtime

    def _seed_initial_values(self, state: RuntimeState) -> None:
        """Emit initial packets from literal/variable nodes into the graph."""
        for gir in list(state.nodes.values()):
            if gir.shape == GygShape.VARIABLE and gir.stored_value is not None:
                out_q = gir.output_ports.setdefault("default", deque())
                out_q.append(
                    Packet(value=gir.stored_value, origin_id=gir.node_id, tick_born=0)
                )

    def _topo_sort(self, state: RuntimeState) -> list[str]:
        """Kahn's algorithm topological sort (cycles → break at back-edges)."""
        in_degree: dict[str, int] = defaultdict(int)
        adj: dict[str, list[str]] = defaultdict(list)

        for scd in state.edges.values():
            if scd.is_back_edge:
                continue  # skip cycles
            adj[scd.source_id].append(scd.dest_id)
            in_degree[scd.dest_id] += 1
            in_degree.setdefault(scd.source_id, 0)

        queue: deque[str] = deque(
            nid for nid in state.nodes if in_degree.get(nid, 0) == 0
        )
        order: list[str] = []

        while queue:
            nid = queue.popleft()
            order.append(nid)
            for successor in adj.get(nid, []):
                in_degree[successor] -= 1
                if in_degree[successor] == 0:
                    queue.append(successor)

        return order


def build(asg: ProgramASG, cfg: ProgramConfig | None = None) -> RuntimeState:
    """Build a RuntimeState from a ProgramASG."""
    return GraphBuilder(asg, cfg).build()
