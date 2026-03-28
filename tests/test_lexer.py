"""Tests for stream.lexer — tokenisation of human-readable source."""

from __future__ import annotations

import pytest

from stream.lexer import Token, TokenKind, lex

# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────


def kinds(src: str) -> list[TokenKind]:
    return [t.kind for t in lex(src) if t.kind != TokenKind.EOF]


def only(src: str) -> Token:
    toks = [t for t in lex(src) if t.kind != TokenKind.EOF]
    assert len(toks) == 1, toks
    return toks[0]


# ──────────────────────────────────────────────────────────────────────────────
# Comment stripping
# ──────────────────────────────────────────────────────────────────────────────


class TestComments:
    def test_single_line_comment_removed(self):
        assert kinds("<-- this is a comment -->") == []

    def test_inline_comment_removed(self):
        toks = kinds("|x| <-- name --> -> |y|")
        assert TokenKind.STREAM_BASIC in toks
        assert toks.count(TokenKind.GYGE) == 2

    def test_multiline_comment_removed(self):
        src = "<-- line1\nline2\nline3 -->"
        assert kinds(src) == []


# ──────────────────────────────────────────────────────────────────────────────
# Gyge tokens
# ──────────────────────────────────────────────────────────────────────────────


class TestGyge:
    def test_simple_gyge(self):
        tok = only("|myVar|")
        assert tok.kind == TokenKind.GYGE
        assert tok.value == "myVar"

    def test_gyge_with_hint(self):
        tok = only("|%func|")
        assert tok.kind == TokenKind.GYGE
        assert tok.value2 in ("%", "func") or "func" in tok.value

    def test_underscore_gyge(self):
        tok = only("|_private|")
        assert tok.kind == TokenKind.GYGE
        assert tok.value == "_private"


# ──────────────────────────────────────────────────────────────────────────────
# Stream operators — basic ordering correctness
# ──────────────────────────────────────────────────────────────────────────────


class TestStreamOperators:
    @pytest.mark.parametrize("src,expected", [
        ("->", TokenKind.STREAM_BASIC),
        ("=>", TokenKind.STREAM_PRIORITY),
        ("~>", TokenKind.STREAM_LOSSY),
        ("-/>", TokenKind.STREAM_FILTER),
        ("-x>", TokenKind.STREAM_BLOCKED),
        ("-!->", TokenKind.STREAM_ERROR),
        ("-!!->", TokenKind.STREAM_EXIT),
        ("-?->", TokenKind.STREAM_CATCH),
        ("-*->", TokenKind.STREAM_SIGNAL),
        ("-?*->", TokenKind.STREAM_RECEIVE),
        ("-#->", TokenKind.STREAM_BATCHER),
        ("-...->", TokenKind.STREAM_SPLITTER),
        ("==>", TokenKind.STREAM_PARASITE),
        ("<~", TokenKind.STREAM_FEEDBACK),
    ])
    def test_operator(self, src: str, expected: TokenKind):
        assert only(src).kind == expected

    def test_exit_before_error(self):
        """- !!-> must not be lexed as -!-> + >"""
        toks = kinds("-!!->")
        assert toks == [TokenKind.STREAM_EXIT]

    def test_receive_before_catch(self):
        toks = kinds("-?*->")
        assert toks == [TokenKind.STREAM_RECEIVE]

    def test_parasite_before_priority(self):
        toks = kinds("==>")
        assert toks == [TokenKind.STREAM_PARASITE]

    def test_throttle_single_plus(self):
        tok = only("-+>")
        assert tok.kind == TokenKind.STREAM_THROTTLE

    def test_fast_two_arrows(self):
        tok = only("->>")
        assert tok.kind == TokenKind.STREAM_FAST


# ──────────────────────────────────────────────────────────────────────────────
# Section / structure tokens
# ──────────────────────────────────────────────────────────────────────────────


class TestSections:
    def test_section_token(self):
        tok = only("::body::")
        assert tok.kind == TokenKind.SECTION
        assert tok.value == "body"

    def test_section_with_spaces(self):
        tok = only("::my section::")
        assert tok.kind == TokenKind.SECTION

    def test_assign(self):
        assert only(":=").kind == TokenKind.ASSIGN

    def test_coloncolon_standalone(self):
        # ::  not followed by name::  → COLONCOLON
        toks = [t for t in lex(":: |x|") if t.kind != TokenKind.EOF]
        assert toks[0].kind == TokenKind.COLONCOLON


# ──────────────────────────────────────────────────────────────────────────────
# Literals
# ──────────────────────────────────────────────────────────────────────────────


class TestLiterals:
    def test_string(self):
        tok = only('"hello world"')
        assert tok.kind == TokenKind.STRING

    def test_string_with_escape(self):
        tok = only(r'"hello \"name\""')
        assert tok.kind == TokenKind.STRING

    def test_integer(self):
        tok = only("42")
        assert tok.kind == TokenKind.INTEGER

    def test_float(self):
        tok = only("3.14")
        assert tok.kind == TokenKind.FLOAT

    def test_void(self):
        assert only("...").kind == TokenKind.VOID


# ──────────────────────────────────────────────────────────────────────────────
# Modifiers
# ──────────────────────────────────────────────────────────────────────────────


class TestModifiers:
    @pytest.mark.parametrize("src,expected", [
        ("$S", TokenKind.MOD_SEASON),
        ("$C", TokenKind.MOD_TEMP),
        ("$@", TokenKind.MOD_TIME),
        ("$entropy", TokenKind.MOD_ENTROPY),
    ])
    def test_modifier(self, src: str, expected: TokenKind):
        assert only(src).kind == expected


# ──────────────────────────────────────────────────────────────────────────────
# Targets
# ──────────────────────────────────────────────────────────────────────────────


class TestTargets:
    def test_pid_target(self):
        tok = only("@pid:1337")
        assert tok.kind == TokenKind.TARGET_PID
        assert tok.value == "1337"

    def test_port_target(self):
        tok = only("@port:8080")
        assert tok.kind == TokenKind.TARGET_PORT
        assert tok.value == "8080"

    def test_broadcast(self):
        assert only("@*").kind == TokenKind.TARGET_BROADCAST


# ──────────────────────────────────────────────────────────────────────────────
# Program primitives
# ──────────────────────────────────────────────────────────────────────────────


class TestProgramPrimitives:
    def test_entry_point(self):
        assert only("<o->").kind == TokenKind.ENTRY_POINT

    def test_alloc(self):
        assert only("<o/").kind == TokenKind.ALLOC

    def test_dealloc(self):
        assert only("<o\\").kind == TokenKind.DEALLOC

    def test_this_program(self):
        assert only("<o>").kind == TokenKind.THIS_PROGRAM


# ──────────────────────────────────────────────────────────────────────────────
# Source position tracking
# ──────────────────────────────────────────────────────────────────────────────


class TestSourcePositions:
    def test_first_token_col_1(self):
        tok = lex("|x|")[0]
        assert tok.line == 1
        assert tok.col == 1

    def test_multiline_line_tracking(self):
        src = "|a|\n|b|\n|c|"
        toks = [t for t in lex(src) if t.kind == TokenKind.GYGE]
        assert [t.line for t in toks] == [1, 2, 3]

    def test_col_after_spaces(self):
        src = "   |x|"
        tok = lex(src)[0]
        assert tok.col == 4


# ──────────────────────────────────────────────────────────────────────────────
# Full chain expression
# ──────────────────────────────────────────────────────────────────────────────


class TestChainExpression:
    def test_basic_chain(self):
        k = kinds("|a| -> |b| -> |c|")
        assert k.count(TokenKind.GYGE) == 3
        assert k.count(TokenKind.STREAM_BASIC) == 2

    def test_mixed_operators(self):
        k = kinds("|a| -> |b| => |c| ~> |d|")
        assert k.count(TokenKind.STREAM_BASIC) == 1
        assert k.count(TokenKind.STREAM_PRIORITY) == 1
        assert k.count(TokenKind.STREAM_LOSSY) == 1
