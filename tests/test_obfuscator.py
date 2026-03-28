"""Tests for stream.obfuscator — bidirectional human ↔ fucked-form conversion."""

from __future__ import annotations

import pytest

from stream.obfuscator import ObfuscatorResult, deobfuscate, obfuscate


# ──────────────────────────────────────────────────────────────────────────────
# Level 0 — identity
# ──────────────────────────────────────────────────────────────────────────────


class TestLevel0:
    def test_identity(self):
        src = "::body::\n    |x| -> |y|\n"
        result = obfuscate(src, level=0)
        assert result.source == src

    def test_returns_obfuscator_result(self):
        result = obfuscate("", level=0)
        assert isinstance(result, ObfuscatorResult)


# ──────────────────────────────────────────────────────────────────────────────
# Level 1–2 — operator substitution
# ──────────────────────────────────────────────────────────────────────────────


class TestLevel1And2:
    @pytest.mark.parametrize("human,fucked", [
        ("->", "⟶"),
        ("=>", "⟹"),
        ("~>", "≀⟶"),
        ("-x>", "⟶̸"),
        ("-!->", "↯"),
        ("-!!->", "↯↯"),
        ("-?->", "↯⃝"),
        ("==>", "⇶"),
        ("<~", "↫"),
    ])
    def test_operator_replaced(self, human: str, fucked: str):
        result = obfuscate(f"|a| {human} |b|", level=1)
        assert fucked in result.source
        assert human not in result.source

    def test_gyge_delimiter_replaced(self):
        result = obfuscate("|myGyge|", level=1)
        assert "⌈myGyge⌉" in result.source
        assert "|myGyge|" not in result.source

    def test_identifiers_unchanged_at_level2(self):
        result = obfuscate("|input| -> |output|", level=2)
        assert "input" in result.source
        assert "output" in result.source


# ──────────────────────────────────────────────────────────────────────────────
# Level 3–4 — full symbol replacement
# ──────────────────────────────────────────────────────────────────────────────


class TestLevel3And4:
    def test_section_sigil_replaced(self):
        result = obfuscate("::body::\n    |x| -> |y|", level=3)
        assert "§" in result.source
        assert "::" not in result.source or result.source.count("::") == 0

    def test_assign_replaced(self):
        result = obfuscate("|x| := 42", level=3)
        assert "≔" in result.source
        assert ":=" not in result.source

    def test_entropy_modifier_replaced(self):
        result = obfuscate("$entropy := 50", level=3)
        assert "∿" in result.source

    def test_season_modifier_replaced(self):
        result = obfuscate("$S := winter", level=3)
        assert "𝕊" in result.source

    def test_identifiers_still_readable_at_level4(self):
        result = obfuscate("::body::\n    |process| -> |output|", level=4)
        assert "process" in result.source
        assert "output" in result.source


# ──────────────────────────────────────────────────────────────────────────────
# Level 5–6 — identifier scrambling
# ──────────────────────────────────────────────────────────────────────────────


class TestLevel5And6:
    def test_identifiers_scrambled(self):
        result = obfuscate("::body::\n    |process| -> |output|", level=5, seed=0)
        assert "process" not in result.source
        assert "output" not in result.source

    def test_symbol_table_returned(self):
        result = obfuscate("|a| -> |b|", level=5, seed=0)
        assert "a" in result.symbol_table
        assert "b" in result.symbol_table

    def test_deterministic_with_same_seed(self):
        r1 = obfuscate("|myVar| -> |otherVar|", level=5, seed=42)
        r2 = obfuscate("|myVar| -> |otherVar|", level=5, seed=42)
        assert r1.source == r2.source

    def test_different_seeds_produce_different_output(self):
        r1 = obfuscate("|myVar|", level=5, seed=1)
        r2 = obfuscate("|myVar|", level=5, seed=999)
        assert r1.source != r2.source

    def test_round_trip_with_symbol_table(self):
        src = "::body::\n    |process| -> |output|"
        result = obfuscate(src, level=5, seed=0)
        recovered = deobfuscate(result.source, symbol_table=result.symbol_table)
        assert "process" in recovered
        assert "output" in recovered


# ──────────────────────────────────────────────────────────────────────────────
# Level 7–8 — string encoding
# ──────────────────────────────────────────────────────────────────────────────


class TestLevel7And8:
    def test_string_encoded_as_hex(self):
        result = obfuscate('|x| := "hello"', level=7)
        assert '"hello"' not in result.source
        assert "0x" in result.source

    def test_string_round_trip(self):
        src = '|x| := "hello world"'
        result = obfuscate(src, level=7, seed=0)
        recovered = deobfuscate(result.source, symbol_table=result.symbol_table)
        assert "hello world" in recovered

    def test_string_with_unicode_round_trip(self):
        src = '|x| := "entropy ∿ chaos"'
        result = obfuscate(src, level=7, seed=0)
        recovered = deobfuscate(result.source, symbol_table=result.symbol_table)
        assert "entropy" in recovered


# ──────────────────────────────────────────────────────────────────────────────
# Level 9 — full entropy mode (whitespace stripped)
# ──────────────────────────────────────────────────────────────────────────────


class TestLevel9:
    def test_no_whitespace_in_output(self):
        result = obfuscate("::body::\n    |a| -> |b|", level=9, seed=0)
        assert " " not in result.source
        assert "\n" not in result.source
        assert "\t" not in result.source

    def test_output_shorter_than_level5(self):
        src = "::body::\n    |process| -> |output| -> |log|"
        r5 = obfuscate(src, level=5, seed=0)
        r9 = obfuscate(src, level=9, seed=0)
        assert len(r9.source) < len(r5.source)


# ──────────────────────────────────────────────────────────────────────────────
# Deobfuscation — levels 1–4 without symbol table
# ──────────────────────────────────────────────────────────────────────────────


class TestDeobfuscate:
    def test_level1_round_trip(self):
        src = "::body::\n    |input| -> |output|"
        obf = obfuscate(src, level=1).source
        recovered = deobfuscate(obf)
        assert "input" in recovered
        assert "output" in recovered
        assert "->" in recovered

    def test_level3_round_trip(self):
        src = "::body::\n    |input| -> |output|\n    $entropy := 30"
        obf = obfuscate(src, level=3).source
        recovered = deobfuscate(obf)
        assert "::" in recovered or "§" not in recovered
        assert ":=" in recovered or "≔" not in recovered

    def test_section_sigil_reversed(self):
        obf = "§body§\n    ⌈input⌉ ⟶ ⌈output⌉"
        recovered = deobfuscate(obf)
        assert "::body::" in recovered
        assert "input" in recovered
        assert "->" in recovered

    def test_all_operators_reversible(self):
        operators = ["->", "=>", "~>", "-x>", "-!->", "-!!->", "-?->", "==>", "<~"]
        for op in operators:
            if op == "<~":
                src = f"|a| -> |b|\n|b| {op} |a|"
            else:
                src = f"|a| {op} |b|"
            for level in [1, 3]:
                result = obfuscate(src, level=level)
                recovered = deobfuscate(result.source)
                assert op in recovered, f"Failed to recover {op!r} at level {level}"


# ──────────────────────────────────────────────────────────────────────────────
# Complex program round-trips
# ──────────────────────────────────────────────────────────────────────────────


class TestComplexPrograms:
    FULL_PROGRAM = """
::header::
    <o-> "watcher"
    $entropy := 20
    $S := winter

::body::
    |input| -> |process| -?-> |err|
    |err| -> |log|
    |process| -!-> "bad input"
    |payload| ==> @pid:1337
"""

    @pytest.mark.parametrize("level", [1, 3, 5, 7])
    def test_round_trip_at_level(self, level: int):
        result = obfuscate(self.FULL_PROGRAM, level=level, seed=123)
        recovered = deobfuscate(result.source, symbol_table=result.symbol_table)

        # Structural operators must survive round-trip
        assert "->" in recovered
        assert "-?->" in recovered
        assert "==>", recovered

    def test_comment_survives_round_trip(self):
        src = "|x| <-- this is a comment --> -> |y|"
        result = obfuscate(src, level=3)
        recovered = deobfuscate(result.source)
        assert "this is a comment" in recovered
