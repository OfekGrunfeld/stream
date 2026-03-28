"""Tests for stream.parser — ProgramASG construction from source."""

from __future__ import annotations

import pytest

from stream.parser import (
    AllocStmt,
    AssignStmt,
    DeallocStmt,
    EntryPointStmt,
    GygeNode,
    LiteralNode,
    ModifierSetStmt,
    ProgramASG,
    StreamKind,
    VoidNode,
    parse,
)

# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────


def _parse(src: str) -> ProgramASG:
    return parse(src.strip(), filename="<test>")


def _stmts_of(asg: ProgramASG, section: str) -> list:
    for sec in asg.sections:
        if sec.name.lower() == section.lower():
            return sec.stmts
    return []


# ──────────────────────────────────────────────────────────────────────────────
# Named gyge nodes
# ──────────────────────────────────────────────────────────────────────────────


class TestGygeNodes:
    def test_single_gyge_registered(self):
        asg = _parse("::body::\n    |x| -> |y|")
        assert "x" in asg.nodes
        assert "y" in asg.nodes

    def test_gyge_node_type(self):
        asg = _parse("::body::\n    |x| -> |y|")
        assert isinstance(asg.nodes["x"], GygeNode)

    def test_duplicate_gyge_same_node(self):
        """Reusing the same gyge name in two edges should reuse the same node."""
        asg = _parse("::body::\n    |a| -> |b|\n    |b| -> |c|")
        assert len(asg.nodes) == 3  # a, b, c


# ──────────────────────────────────────────────────────────────────────────────
# Stream edges
# ──────────────────────────────────────────────────────────────────────────────


class TestStreamEdges:
    def test_basic_edge(self):
        asg = _parse("::body::\n    |a| -> |b|")
        assert len(asg.all_edges) == 1
        assert asg.all_edges[0].kind == StreamKind.BASIC

    def test_chain_creates_multiple_edges(self):
        asg = _parse("::body::\n    |a| -> |b| -> |c|")
        assert len(asg.all_edges) == 2

    @pytest.mark.parametrize("op,kind", [
        ("->", StreamKind.BASIC),
        ("=>", StreamKind.PRIORITY),
        ("~>", StreamKind.LOSSY),
        ("-/>", StreamKind.FILTER),
        ("-x>", StreamKind.BLOCKED),
        ("-!->", StreamKind.ERROR),
        ("-!!->", StreamKind.EXIT),
        ("-?->", StreamKind.CATCH),
        ("-*->", StreamKind.SIGNAL),
        ("-#->", StreamKind.BATCHER),
        ("-...->", StreamKind.SPLITTER),
        ("==>", StreamKind.PARASITE),
        ("<~", StreamKind.FEEDBACK),
    ])
    def test_operator_maps_to_kind(self, op: str, kind: StreamKind):
        if op == "<~":
            src = "::body::\n    |a| -> |b|\n    |b| <~ |a|"
        else:
            src = f"::body::\n    |a| {op} |b|"
        asg = _parse(src)
        kinds_found = {e.kind for e in asg.all_edges}
        assert kind in kinds_found


# ──────────────────────────────────────────────────────────────────────────────
# Sections
# ──────────────────────────────────────────────────────────────────────────────


class TestSections:
    def test_section_names_captured(self):
        asg = _parse("::header::\n::body::\n    |x| -> |y|")
        names = [s.name.lower() for s in asg.sections]
        assert "header" in names
        assert "body" in names

    def test_multiple_sections(self):
        asg = _parse("::header::\n::body::\n    |a| -> |b|\n::cleanup::")
        assert len(asg.sections) >= 3


# ──────────────────────────────────────────────────────────────────────────────
# Statements
# ──────────────────────────────────────────────────────────────────────────────


class TestStatements:
    def test_entry_point_stmt(self):
        asg = _parse('::header::\n    <o-> "main"')
        stmts = _stmts_of(asg, "header")
        assert any(isinstance(s, EntryPointStmt) for s in stmts)

    def test_modifier_season(self):
        asg = _parse("::header::\n    $S := winter")
        stmts = _stmts_of(asg, "header")
        mod = next((s for s in stmts if isinstance(s, ModifierSetStmt)), None)
        assert mod is not None
        assert mod.modifier == "season"
        assert mod.value == "winter"

    def test_modifier_entropy(self):
        asg = _parse("::header::\n    $entropy := 42")
        stmts = _stmts_of(asg, "header")
        mod = next((s for s in stmts if isinstance(s, ModifierSetStmt)), None)
        assert mod is not None
        assert mod.modifier == "entropy"

    def test_assign_stmt_literal(self):
        asg = _parse("::body::\n    |x| := 99")
        stmts = _stmts_of(asg, "body")
        assign = next((s for s in stmts if isinstance(s, AssignStmt)), None)
        assert assign is not None
        assert isinstance(assign.rhs, LiteralNode)
        assert assign.rhs.value == 99

    def test_assign_stmt_string(self):
        asg = _parse('::body::\n    |x| := "hello"')
        stmts = _stmts_of(asg, "body")
        assign = next((s for s in stmts if isinstance(s, AssignStmt)), None)
        assert assign is not None
        assert isinstance(assign.rhs, LiteralNode)
        assert assign.rhs.value == "hello"

    def test_assign_void(self):
        asg = _parse("::body::\n    |x| := ...")
        stmts = _stmts_of(asg, "body")
        assign = next((s for s in stmts if isinstance(s, AssignStmt)), None)
        assert assign is not None
        assert isinstance(assign.rhs, VoidNode)

    def test_alloc_stmt(self):
        asg = _parse("::alloc::\n    |buf| := <o/")
        stmts = _stmts_of(asg, "alloc")
        assert any(isinstance(s, AllocStmt) for s in stmts)

    def test_dealloc_stmt(self):
        asg = _parse("::cleanup::\n    <o\\ |buf|")
        stmts = _stmts_of(asg, "cleanup")
        assert any(isinstance(s, DeallocStmt) for s in stmts)


# ──────────────────────────────────────────────────────────────────────────────
# Feedback / back-edge detection
# ──────────────────────────────────────────────────────────────────────────────


class TestBackEdges:
    def test_feedback_edge_flagged(self):
        asg = _parse("::body::\n    |a| -> |b|\n    |b| <~ |a|")
        back = [e for e in asg.all_edges if e.is_back_edge]
        assert len(back) >= 1


# ──────────────────────────────────────────────────────────────────────────────
# Empty / edge cases
# ──────────────────────────────────────────────────────────────────────────────


class TestEdgeCases:
    def test_empty_source(self):
        asg = _parse("")
        assert len(asg.nodes) == 0
        assert len(asg.all_edges) == 0

    def test_comment_only(self):
        asg = _parse("<-- nothing here -->")
        assert len(asg.nodes) == 0

    def test_full_header_program(self):
        src = """
::header::
    <o-> "watcher"
    $entropy := 20
    $S := winter

::body::
    |input| -> |process| -?-> |err|
    |err| -> |log|
"""
        asg = _parse(src)
        assert "input" in asg.nodes
        assert "process" in asg.nodes
        assert "err" in asg.nodes
        assert "log" in asg.nodes
        assert len(asg.all_edges) >= 3
