"""Phase 3 — Edge Delivery.

Pass A: all => priority edges (guaranteed before normal).
Pass B: all other edge types in topological order.
Back-edges (<~) processed last in Pass B.

For each edge:
  1. Check source has output
  2. policy.should_deliver(packet, edge, entropy)
  3. policy.transform(packet, entropy)
  4. Enqueue result in dest input port
"""

from __future__ import annotations

from collections import deque

from stream.runtime.policies import POLICY_REGISTRY
from stream.runtime.policies.error import ErrorEvent
from stream.runtime.state import RuntimeState
from stream.runtime.types import SCD, EdgeState, StreamKind

__all__ = ["Phase3Delivery"]


class Phase3Delivery:
    __slots__ = ()

    def execute(self, state: RuntimeState) -> None:
        priority_edges: list[SCD] = []
        normal_edges: list[SCD] = []
        back_edges: list[SCD] = []

        for scd in state.edges.values():
            if scd.state == EdgeState.DRAINED:
                continue
            if scd.is_back_edge:
                back_edges.append(scd)
            elif scd.stream_kind == StreamKind.PRIORITY:
                priority_edges.append(scd)
            else:
                normal_edges.append(scd)

        # Pass A — priority edges first
        for scd in priority_edges:
            self._deliver(scd, state)

        # Pass B — topological order (approximate: use topo_order if available)
        topo = state.topo_order
        if topo:
            edge_by_source: dict[str, list[SCD]] = {}
            for scd in normal_edges:
                edge_by_source.setdefault(scd.source_id, []).append(scd)
            for nid in topo:
                for scd in edge_by_source.get(nid, []):
                    self._deliver(scd, state)
        else:
            for scd in normal_edges:
                self._deliver(scd, state)

        # Back-edges last
        for scd in back_edges:
            self._deliver(scd, state)

    def _deliver(self, scd: SCD, state: RuntimeState) -> None:
        src = state.get_node(scd.source_id)
        dst = state.get_node(scd.dest_id)

        if src is None or dst is None:
            return

        # Disrupted edges don't deliver
        if scd.state == EdgeState.DISRUPTED:
            if scd.disruption_ticks_remaining > 0:
                scd.disruption_ticks_remaining -= 1
            else:
                scd.state = EdgeState.ACTIVE
            return

        out_q = src.output_ports.get("default")
        if not out_q:
            return  # source has nothing to send

        policy = POLICY_REGISTRY.get(scd.stream_kind)
        effective_entropy = state.effective_entropy(scd.local_entropy)

        # Refill token bucket for throttle edges (called each tick in on_blocked)
        if scd.stream_kind == StreamKind.THROTTLE:
            policy.on_blocked(scd, effective_entropy)

        # Deliver packets from source buffer
        packets_to_deliver = list(out_q)
        out_q.clear()

        for packet in packets_to_deliver:
            if not policy.should_deliver(packet, scd, effective_entropy):
                # Packet dropped — on_blocked handles backpressure
                policy.on_blocked(scd, effective_entropy)
                continue

            transformed = policy.transform(packet, scd, effective_entropy)

            # Special handling: EXIT stream terminates the program
            if scd.stream_kind == StreamKind.EXIT:
                code = int(transformed.value) if isinstance(transformed.value, (int, float)) else 0
                state.exit_code = code
                state.terminated = True
                return

            # Special handling: ERROR stream raises an error event
            if scd.stream_kind == StreamKind.ERROR:
                error_event = ErrorEvent(
                    payload=transformed,
                    source_edge_id=scd.edge_id,
                    source_node_id=scd.source_id,
                    entropy_at_raise=effective_entropy,
                    tick=state.tick,
                )
                state.error_queue.append(error_event)
                continue

            # Normal delivery: enqueue in destination input port
            in_q = dst.input_ports.setdefault("default", deque())
            in_q.append(transformed)
