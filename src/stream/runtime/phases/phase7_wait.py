"""Phase 7 — Wait Stream Resolution.

-,-> edges check their wait conditions after all delivery and signal phases.
Conditions that resolve release held packets into delivery buffers.
"""

from __future__ import annotations

from collections import deque

from stream.runtime.state import RuntimeState
from stream.runtime.types import StreamKind

__all__ = ["Phase7Wait"]


class Phase7Wait:
    __slots__ = ()

    def execute(self, state: RuntimeState) -> None:
        for scd in state.edges.values():
            if scd.stream_kind != StreamKind.WAIT:
                continue
            if not scd.buffer:
                continue

            policy = _get_wait_policy()
            effective_entropy = state.effective_entropy(scd.local_entropy)

            if policy.should_deliver(scd.buffer[0], scd, effective_entropy):  # type: ignore[attr-defined]
                # Release all held packets to destination input
                dst = state.get_node(scd.dest_id)
                if dst is not None:
                    in_q = dst.input_ports.setdefault("default", deque())
                    while scd.buffer:
                        in_q.append(scd.buffer.popleft())


def _get_wait_policy() -> object:
    from stream.runtime.policies import POLICY_REGISTRY
    from stream.runtime.types import StreamKind

    return POLICY_REGISTRY.get(StreamKind.WAIT)
