"""Tests for stream.graph — GraphBuilder (ASG → RuntimeState)."""

from __future__ import annotations

import pytest

from stream.graph import build
from stream.parser import parse
from stream.runtime.state import ProgramConfig, RuntimeState
from stream.runtime.types import GygShape, Season


def _build(src: str, **cfg_kwargs) -> RuntimeState:
    asg = parse(src.strip(), filename="<test>")
    cfg = ProgramConfig(**cfg_kwargs)
    return build(asg, cfg)


# ──────────────────────────────────────────────────────────────────────────────
# Node creation
# ──────────────────────────────────────────────────────────────────────────────


class TestNodeCreation:
    def test_named_gyges_become_gir_nodes(self):
        state = _build("::body::\n    |x| -> |y|")
        names = {gir.name for gir in state.nodes.values()}
        assert "x" in names
        assert "y" in names

    def test_builtin_function_shape(self):
        state = _build("::body::\n    |x| -> |print|")
        girs_by_name = {g.name: g for g in state.nodes.values()}
        assert girs_by_name["print"].shape == GygShape.FUNCTION
        assert callable(girs_by_name["print"].fn_body)

    def test_literal_assign_sets_variable_shape(self):
        state = _build("::body::\n    |x| := 42")
        girs_by_name = {g.name: g for g in state.nodes.values()}
        assert girs_by_name["x"].shape == GygShape.VARIABLE
        assert girs_by_name["x"].stored_value == 42

    def test_string_assign(self):
        state = _build('::body::\n    |x| := "hello"')
        girs_by_name = {g.name: g for g in state.nodes.values()}
        assert girs_by_name["x"].stored_value == "hello"

    def test_void_assign_sets_void_shape(self):
        state = _build("::body::\n    |x| := ...")
        girs_by_name = {g.name: g for g in state.nodes.values()}
        assert girs_by_name["x"].shape == GygShape.VOID

    def test_alloc_sets_bytes_shape(self):
        state = _build("::alloc::\n    |buf| := <o/")
        girs_by_name = {g.name: g for g in state.nodes.values()}
        assert girs_by_name["buf"].shape == GygShape.BYTES
        assert isinstance(girs_by_name["buf"].stored_value, bytearray)


# ──────────────────────────────────────────────────────────────────────────────
# Edge creation
# ──────────────────────────────────────────────────────────────────────────────


class TestEdgeCreation:
    def test_basic_edge_created(self):
        state = _build("::body::\n    |a| -> |b|")
        assert len(state.edges) == 1

    def test_chain_creates_two_edges(self):
        state = _build("::body::\n    |a| -> |b| -> |c|")
        assert len(state.edges) == 2

    def test_edge_source_and_dest_wired(self):
        state = _build("::body::\n    |a| -> |b|")
        edge = next(iter(state.edges.values()))
        girs_by_name = {g.name: g for g in state.nodes.values()}
        assert edge.source_id == girs_by_name["a"].node_id
        assert edge.dest_id == girs_by_name["b"].node_id

    def test_back_edge_flag_preserved(self):
        state = _build("::body::\n    |a| -> |b|\n    |b| <~ |a|")
        back_edges = [e for e in state.edges.values() if e.is_back_edge]
        assert len(back_edges) >= 1

    def test_node_out_edges_index(self):
        state = _build("::body::\n    |a| -> |b|")
        girs_by_name = {g.name: g for g in state.nodes.values()}
        a_id = girs_by_name["a"].node_id
        assert len(state.node_out_edges.get(a_id, [])) == 1

    def test_node_in_edges_index(self):
        state = _build("::body::\n    |a| -> |b|")
        girs_by_name = {g.name: g for g in state.nodes.values()}
        b_id = girs_by_name["b"].node_id
        assert len(state.node_in_edges.get(b_id, [])) == 1


# ──────────────────────────────────────────────────────────────────────────────
# Header section processing
# ──────────────────────────────────────────────────────────────────────────────


class TestHeaderProcessing:
    def test_entropy_set_from_header(self):
        state = _build("::header::\n    $entropy := 50\n::body::\n    |a| -> |b|")
        assert state.entropy == pytest.approx(50.0)

    def test_season_set_from_header(self):
        state = _build("::header::\n    $S := summer\n::body::\n    |a| -> |b|")
        assert state.season == Season.SUMMER

    def test_season_lock_set(self):
        state = _build("::header::\n    $S := winter\n::body::\n    |a| -> |b|")
        assert state.season_lock == Season.WINTER


# ──────────────────────────────────────────────────────────────────────────────
# ProgramConfig injection
# ──────────────────────────────────────────────────────────────────────────────


class TestConfig:
    def test_entropy_initial_applied(self):
        state = _build("::body::\n    |a| -> |b|", entropy_initial=30.0)
        assert state.entropy == pytest.approx(30.0)

    def test_entropy_cap_applied(self):
        state = _build("::body::\n    |a| -> |b|", entropy_cap=50.0)
        assert state.entropy_cap == pytest.approx(50.0)

    def test_seed_deterministic(self):
        state1 = _build("::body::\n    |a| -> |b|", seed=42)
        state2 = _build("::body::\n    |a| -> |b|", seed=42)
        # Both RNGs produce the same sequence
        assert state1.rng.random() == state2.rng.random()

    def test_different_seeds_differ(self):
        state1 = _build("::body::\n    |a| -> |b|", seed=1)
        state2 = _build("::body::\n    |a| -> |b|", seed=2)
        assert state1.rng.random() != state2.rng.random()


# ──────────────────────────────────────────────────────────────────────────────
# Topological sort
# ──────────────────────────────────────────────────────────────────────────────


class TestTopoSort:
    def test_topo_order_non_empty(self):
        state = _build("::body::\n    |a| -> |b| -> |c|")
        assert len(state.topo_order) >= 3

    def test_source_before_sink(self):
        state = _build("::body::\n    |a| -> |b|")
        girs_by_name = {g.name: g for g in state.nodes.values()}
        a_pos = state.topo_order.index(girs_by_name["a"].node_id)
        b_pos = state.topo_order.index(girs_by_name["b"].node_id)
        assert a_pos < b_pos


# ──────────────────────────────────────────────────────────────────────────────
# Initial value seeding
# ──────────────────────────────────────────────────────────────────────────────


class TestInitialValueSeeding:
    def test_variable_node_has_packet_in_output(self):
        state = _build("::body::\n    |x| := 42\n    |x| -> |print|")
        girs_by_name = {g.name: g for g in state.nodes.values()}
        x = girs_by_name["x"]
        assert x.shape == GygShape.VARIABLE
        # Output port should have a seeded packet
        out_q = x.output_ports.get("default")
        assert out_q is not None and len(out_q) == 1
        assert out_q[0].value == 42
