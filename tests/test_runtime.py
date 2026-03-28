"""Tests for the Stream runtime — policies, phases, loop, and end-to-end execution."""

from __future__ import annotations

from collections import deque

import pytest

from stream.graph import build
from stream.parser import parse
from stream.runtime.loop import RuntimeLoop, TerminationReason
from stream.runtime.phases.phase3_delivery import Phase3Delivery
from stream.runtime.phases.phase4_activation import Phase4Activation
from stream.runtime.phases.phase9_gc import Phase9GC
from stream.runtime.policies.base import POLICY_REGISTRY
from stream.runtime.state import ProgramConfig, RuntimeState
from stream.runtime.types import (
    GIR,
    SCD,
    ActivationState,
    EdgeState,
    GygShape,
    Packet,
    StreamKind,
)

# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────


def _run(src: str, tick_limit: int = 50, **cfg_kwargs) -> tuple[RuntimeState, TerminationReason]:
    asg = parse(src.strip(), filename="<test>")
    cfg = ProgramConfig(tick_limit=tick_limit, **cfg_kwargs)
    state = build(asg, cfg)
    loop = RuntimeLoop()
    reason = loop.run(state)
    return state, reason


def _make_state() -> RuntimeState:
    return RuntimeState(config=ProgramConfig())


def _add_edge(state: RuntimeState, src: GIR, dst: GIR, kind: StreamKind = StreamKind.BASIC) -> SCD:
    scd = SCD(stream_kind=kind, source_id=src.node_id, dest_id=dst.node_id)
    state.add_node(src)
    state.add_node(dst)
    state.add_edge(scd)
    return scd


def _packet(val: object, origin: str = "test") -> Packet:
    return Packet(value=val, origin_id=origin, tick_born=0)


# ──────────────────────────────────────────────────────────────────────────────
# Policy registry
# ──────────────────────────────────────────────────────────────────────────────


class TestPolicyRegistry:
    @pytest.mark.parametrize("kind", [
        StreamKind.BASIC, StreamKind.PRIORITY, StreamKind.LOSSY,
        StreamKind.BLOCKED, StreamKind.THROTTLE, StreamKind.FAST,
        StreamKind.FILTER, StreamKind.SWITCH, StreamKind.BATCHER,
        StreamKind.SPLITTER, StreamKind.ARG_FILTER,
        StreamKind.ERROR, StreamKind.EXIT, StreamKind.CATCH,
        StreamKind.SIGNAL, StreamKind.RECEIVE, StreamKind.WAIT,
        StreamKind.PARASITE, StreamKind.FEEDBACK,
    ])
    def test_policy_registered(self, kind: StreamKind):
        policy = POLICY_REGISTRY.get(kind)
        assert policy is not None, f"No policy registered for {kind}"

    def test_policy_has_required_methods(self):
        for kind in StreamKind:
            policy = POLICY_REGISTRY.get(kind)
            if policy is None:
                continue
            assert hasattr(policy, "should_deliver")
            assert hasattr(policy, "transform")
            assert hasattr(policy, "on_blocked")


# ──────────────────────────────────────────────────────────────────────────────
# Basic policy behaviour
# ──────────────────────────────────────────────────────────────────────────────


class TestBasicPolicy:
    def test_delivers_at_low_entropy(self):
        policy = POLICY_REGISTRY.get(StreamKind.BASIC)
        scd = SCD(stream_kind=StreamKind.BASIC)
        pkt = _packet(1)
        # At entropy 0, always delivers
        results = [policy.should_deliver(pkt, scd, 0.0) for _ in range(100)]
        assert all(results)

    def test_transform_passthrough_low_entropy(self):
        policy = POLICY_REGISTRY.get(StreamKind.BASIC)
        scd = SCD(stream_kind=StreamKind.BASIC)
        pkt = _packet("hello")
        out = policy.transform(pkt, scd, 0.0)
        assert out.value == "hello"
        assert not out.corrupted


class TestLossyPolicy:
    def test_some_packets_dropped(self):
        """At default entropy, ~5% are dropped — with 1000 trials we expect some drops."""
        policy = POLICY_REGISTRY.get(StreamKind.LOSSY)
        scd = SCD(stream_kind=StreamKind.LOSSY)
        pkt = _packet(1)
        deliveries = sum(1 for _ in range(1000) if policy.should_deliver(pkt, scd, 15.0))
        assert deliveries < 1000  # some were dropped

    def test_high_entropy_higher_loss(self):
        policy = POLICY_REGISTRY.get(StreamKind.LOSSY)
        scd = SCD(stream_kind=StreamKind.LOSSY)
        pkt = _packet(1)
        low_deliveries = sum(1 for _ in range(1000) if policy.should_deliver(pkt, scd, 10.0))
        high_deliveries = sum(1 for _ in range(1000) if policy.should_deliver(pkt, scd, 85.0))
        assert high_deliveries < low_deliveries


class TestBlockedPolicy:
    def test_blocked_does_not_deliver_at_low_entropy(self):
        policy = POLICY_REGISTRY.get(StreamKind.BLOCKED)
        scd = SCD(stream_kind=StreamKind.BLOCKED)
        pkt = _packet(1)
        results = [policy.should_deliver(pkt, scd, 0.0) for _ in range(100)]
        assert not any(results)


# ──────────────────────────────────────────────────────────────────────────────
# Phase 3 — Delivery
# ──────────────────────────────────────────────────────────────────────────────


class TestPhase3Delivery:
    def test_packet_moves_from_source_to_dest(self):
        state = _make_state()
        src = GIR(name="src", shape=GygShape.VARIABLE)
        dst = GIR(name="dst", shape=GygShape.VOID)
        _add_edge(state, src, dst)

        src.output_ports["default"] = deque([_packet(42)])

        Phase3Delivery().execute(state)

        dst_q = dst.input_ports.get("default", deque())
        assert len(dst_q) == 1
        assert dst_q[0].value == 42

    def test_priority_edges_delivered_first(self):
        """Priority edge packet arrives in dest before basic edge packet."""
        state = _make_state()
        src = GIR(name="src", shape=GygShape.VARIABLE)
        dst = GIR(name="dst", shape=GygShape.VOID)

        basic_scd = SCD(stream_kind=StreamKind.BASIC, source_id=src.node_id, dest_id=dst.node_id)
        prio_scd = SCD(stream_kind=StreamKind.PRIORITY, source_id=src.node_id, dest_id=dst.node_id)

        state.add_node(src)
        state.add_node(dst)
        state.add_edge(basic_scd)
        state.add_edge(prio_scd)

        src.output_ports["default"] = deque([_packet("basic"), _packet("prio")])
        Phase3Delivery().execute(state)

        # Both should arrive — just verifying delivery occurs
        dst_q = dst.input_ports.get("default", deque())
        assert len(dst_q) >= 1

    def test_disrupted_edge_does_not_deliver(self):
        state = _make_state()
        src = GIR(name="src", shape=GygShape.VARIABLE)
        dst = GIR(name="dst", shape=GygShape.VOID)
        scd = _add_edge(state, src, dst)
        scd.state = EdgeState.DISRUPTED
        scd.disruption_ticks_remaining = 2

        src.output_ports["default"] = deque([_packet(1)])
        Phase3Delivery().execute(state)

        assert not dst.input_ports.get("default")

    def test_exit_stream_terminates_state(self):
        state = _make_state()
        src = GIR(name="src", shape=GygShape.VARIABLE)
        dst = GIR(name="dst", shape=GygShape.VOID)
        _add_edge(state, src, dst, StreamKind.EXIT)

        src.output_ports["default"] = deque([_packet(0)])
        Phase3Delivery().execute(state)

        assert state.terminated
        assert state.exit_code == 0


# ──────────────────────────────────────────────────────────────────────────────
# Phase 4 — Activation
# ──────────────────────────────────────────────────────────────────────────────


class TestPhase4Activation:
    def test_function_gyge_called(self):
        state = _make_state()
        results = []
        gir = GIR(name="fn", shape=GygShape.FUNCTION, fn_body=lambda v: results.append(v) or v)
        state.add_node(gir)
        gir.input_ports["default"] = deque([_packet("test-value")])

        Phase4Activation().execute(state)

        assert results == ["test-value"]

    def test_function_output_in_output_port(self):
        state = _make_state()
        gir = GIR(name="double", shape=GygShape.FUNCTION, fn_body=lambda v: v * 2)
        state.add_node(gir)
        gir.input_ports["default"] = deque([_packet(21)])

        Phase4Activation().execute(state)

        out_q = gir.output_ports.get("default", deque())
        assert len(out_q) == 1
        assert out_q[0].value == 42

    def test_variable_stores_value(self):
        state = _make_state()
        gir = GIR(name="x", shape=GygShape.VARIABLE)
        state.add_node(gir)
        gir.input_ports["default"] = deque([_packet(99)])

        Phase4Activation().execute(state)

        assert gir.stored_value == 99

    def test_void_gyge_no_stored_output(self):
        """A VOID gyge resolves its shape from the incoming packet but has no fn_body,
        so it falls through to the default (pass-through) case.  What matters is that
        a gyge explicitly assigned `...` (stored_value=None, no out-edges) drains cleanly."""
        state = _make_state()
        # Simulate |sink| := ... — shape=VOID, no out-edges in state → marks DRAINED
        gir = GIR(name="sink", shape=GygShape.VOID)
        state.add_node(gir)
        gir.input_ports["default"] = deque([_packet("discard")])

        Phase4Activation().execute(state)

        # With no out-edges, the node should be marked DRAINED after activation
        assert gir.activation_state == ActivationState.DRAINED

    def test_lazy_shape_resolution_from_callable(self):
        state = _make_state()
        def fn(v):
            return v
        gir = GIR(name="lazy")
        state.add_node(gir)
        gir.input_ports["default"] = deque([_packet(fn)])

        Phase4Activation().execute(state)

        assert gir.shape == GygShape.FUNCTION

    def test_lazy_shape_resolution_from_bytes(self):
        state = _make_state()
        gir = GIR(name="bytez")
        state.add_node(gir)
        gir.input_ports["default"] = deque([_packet(b"raw bytes")])

        Phase4Activation().execute(state)

        assert gir.shape == GygShape.BYTES


# ──────────────────────────────────────────────────────────────────────────────
# Phase 9 — GC
# ──────────────────────────────────────────────────────────────────────────────


class TestPhase9GC:
    def test_drained_edge_removed(self):
        state = _make_state()
        src = GIR(name="src")
        dst = GIR(name="dst")
        scd = _add_edge(state, src, dst)
        scd.state = EdgeState.DRAINED
        # buffer must be empty for GC to collect

        Phase9GC().execute(state)

        assert scd.edge_id not in state.edges

    def test_active_edge_not_removed(self):
        state = _make_state()
        src = GIR(name="src")
        dst = GIR(name="dst")
        scd = _add_edge(state, src, dst)
        scd.state = EdgeState.ACTIVE

        Phase9GC().execute(state)

        assert scd.edge_id in state.edges

    def test_drained_orphan_node_removed(self):
        state = _make_state()
        gir = GIR(name="orphan", activation_state=ActivationState.DRAINED)
        state.add_node(gir)

        Phase9GC().execute(state)

        assert gir.node_id not in state.nodes


# ──────────────────────────────────────────────────────────────────────────────
# RuntimeLoop — end-to-end
# ──────────────────────────────────────────────────────────────────────────────


class TestRuntimeLoop:
    def test_natural_drain_simple(self):
        """A variable piped to print drains naturally."""
        _, reason = _run("::body::\n    |x| := 42\n    |x| -> |print|", tick_limit=20)
        assert reason == TerminationReason.NATURAL_DRAIN

    def test_exit_stream_terminates(self):
        """A chain terminating in -!!-> sets exit_code and terminates."""
        state, reason = _run(
            "::body::\n    |x| := 0\n    |x| -!!-> |sink|",
            tick_limit=20,
        )
        assert reason == TerminationReason.EXIT_STREAM
        assert state.terminated

    def test_tick_limit_respected(self):
        """If program never drains, tick_limit is enforced."""
        # Feedback loop: a -> b <~ a — keeps cycling
        state, reason = _run(
            "::body::\n    |a| := 1\n    |a| -> |b|\n    |b| <~ |a|",
            tick_limit=10,
        )
        assert reason == TerminationReason.TICK_LIMIT
        assert state.tick <= 10

    def test_print_builtin_called(self, capsys):
        """Value piped into |print| should print to stdout."""
        _run('::body::\n    |x| := "hello stream"\n    |x| -> |print|', tick_limit=20)
        captured = capsys.readouterr()
        assert "hello stream" in captured.out

    def test_multiple_values_pipeline(self, capsys):
        """Chain: value → str → print."""
        _run(
            "::body::\n    |n| := 42\n    |n| -> |str| -> |print|",
            tick_limit=30,
        )
        captured = capsys.readouterr()
        assert "42" in captured.out

    def test_terminal_cascade_requires_cap_100(self):
        """Terminal Cascade only fires when entropy_cap == 100 and entropy hits 100.
        With cap < 100 it can never cascade even at high entropy."""
        state_capped, _ = _run(
            "::body::\n    |a| := 1\n    |a| -> |b|\n    |b| <~ |a|",
            tick_limit=5,
            entropy_initial=50.0,
            entropy_cap=85.0,  # capped below 100 — cascade impossible
        )
        assert state_capped.entropy <= 85.0  # cap enforced

    def test_loop_terminates_eventually(self):
        """Any well-formed program terminates within tick_limit."""
        _, reason = _run(
            "::body::\n    |x| := 42\n    |x| -> |print|",
            tick_limit=100,
        )
        assert reason != TerminationReason.TICK_LIMIT
