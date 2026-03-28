"""Phase 6 — Signal Processing.

-*-> (Send signal) and -?*-> (Receive signal) are processed out-of-band,
after normal delivery.  Modifier change subscriptions are also resolved here.
"""

from __future__ import annotations

from collections import deque

from stream.runtime.policies.signal import SignalEvent
from stream.runtime.state import RuntimeState
from stream.runtime.types import StreamKind

__all__ = ["Phase6Signals"]


class Phase6Signals:
    __slots__ = ()

    def execute(self, state: RuntimeState) -> None:
        pending: list[SignalEvent] = [
            e for e in state.signal_queue if isinstance(e, SignalEvent)
        ]
        state.signal_queue.clear()

        for event in pending:
            self._route_signal(event, state)

        # Process all RECEIVE edges: deliver if they have data
        for scd in state.edges.values():
            if scd.stream_kind not in (StreamKind.RECEIVE, StreamKind.SIGNAL):
                continue
            dst = state.get_node(scd.dest_id)
            if dst is None:
                continue
            if scd.buffer:
                packet = scd.buffer.popleft()
                in_q = dst.input_ports.setdefault("default", deque())
                in_q.append(packet)

    def _route_signal(self, event: SignalEvent, state: RuntimeState) -> None:
        # Find RECEIVE edges that match the signal source
        for scd in state.edges.values():
            if scd.stream_kind != StreamKind.RECEIVE:
                continue
            if scd.source_id == event.source_id or scd.condition == event.dest_id:
                dst = state.get_node(scd.dest_id)
                if dst is not None:
                    in_q = dst.input_ports.setdefault("default", deque())
                    in_q.append(event.payload)
