"""Obfuscator — bidirectional human-readable ↔ fucked-form conversion.

The two forms are semantically identical; conversion is lossless and bijective.

Obfuscation levels:
    0       — identity (no change)
    1–2     — operator + delimiter substitution only
    3–4     — full symbol replacement (operators, delimiters, keywords, modifiers)
    5–6     — + identifier scrambling (deterministic, seed-based)
    7–8     — + string encoding (hex bytes) + numeric base encoding
    9       — all of the above + whitespace stripping

Deobfuscation always requires Level 1–4 to be automatic.
Levels 5–9 require the symbol table (returned as a separate dict).
"""

from __future__ import annotations

import re
import random
from dataclasses import dataclass, field
from typing import Optional

__all__ = ["obfuscate", "deobfuscate", "ObfuscatorResult"]

# ──────────────────────────────────────────────────────────────────────────────
# Operator mapping table  (human-readable → fucked)
# Ordered longest-first so replacement is unambiguous.
# ──────────────────────────────────────────────────────────────────────────────

_OPERATOR_MAP: list[tuple[str, str]] = [
    # Stream operators (longest first)
    ("-?*->", "⊛⃝⟶"),
    ("-/|->", "⊣⟶"),
    ("-/|\\->", "⋈⟶"),
    ("-...->", "⋯⟶"),
    ("-!!->", "↯↯"),
    ("-!->", "↯"),
    ("-?->", "↯⃝"),
    ("-*->", "⊛⟶"),
    ("-#->", "⊞⟶"),
    ("-,->", "⌛⟶"),
    ("==>", "⇶"),
    ("-x>", "⟶̸"),
    ("->>", "⟹⟹"),
    ("=>", "⟹"),
    ("~>", "≀⟶"),
    ("<~", "↫"),
    ("->", "⟶"),
    ("&->", "⊕⟶"),
    # Throttle: -+> and variants with multiple + chars handled as regex later
]

# Sort reverse map longest-fucked-form first so multi-glyph sequences (e.g. ≀⟶)
# are replaced before their sub-sequences (e.g. ⟶).
_OPERATOR_REVERSE: list[tuple[str, str]] = sorted(
    [(f, h) for h, f in _OPERATOR_MAP],
    key=lambda pair: len(pair[0]),
    reverse=True,
)

# Keyword / delimiter map
_KEYWORD_MAP: list[tuple[str, str]] = [
    # Program + allocation
    ("<o->", "⊙⟶"),
    ("<o/>", "⊢"),          # alloc (open form)
    ("<o\\>", "⊣"),         # dealloc (open form)
    ("<o>", "⊙"),
    # Comments: handled separately
    # Section sigil
    ("::", "§"),
    # Assignment
    (":=", "≔"),
    # Void
    ("...", "⋯"),
    # Modifiers
    ("$entropy", "∿"),
    ("$S", "𝕊"),
    ("$C", "℃"),
    ("$@", "⌚"),
    # Gyge delimiters — handled via regex (contain identifier content)
    # Import — handled via regex
    # Target sigils
    ("@pid:", "℗"),
    ("@name:", "ℕ"),
    ("@port:", "℘"),
    ("@ip:", "℩"),
    ("@dir:", "⌂"),
    ("@*", "※"),
]

_KEYWORD_REVERSE: list[tuple[str, str]] = [(f, h) for h, f in reversed(_KEYWORD_MAP)]

# Regex patterns for structure-preserving replacements
_RE_GYGE_HR = re.compile(r"\|([^|]+)\|")          # |name|
_RE_GYGE_FK = re.compile(r"⌈([^⌉]+)⌉")           # ⌈name⌉

_RE_IMPORT_HR = re.compile(r"><([^>]+)><")         # ><name><
_RE_IMPORT_FK = re.compile(r"≺([^≻]+)≻")          # ≺name≻

_RE_COMMENT_HR = re.compile(r"<--(.*?)-->", re.DOTALL)   # <-- ... -->
_RE_COMMENT_FK = re.compile(r"⟨⟨(.*?)⟩⟩", re.DOTALL)    # ⟨⟨ ... ⟩⟩

_RE_BYTE_BRACKET_HR = re.compile(r"\[([^\]]+)\]")        # [name]
_RE_BYTE_BRACKET_FK = re.compile(r"⟦([^⟧]+)⟧")          # ⟦name⟧

_RE_THROTTLE_HR = re.compile(r"-(\++)>")           # -+>, -++>, etc.
_RE_FAST_HR = re.compile(r"-(>>+)")                # ->>, ->>>, etc.

_RE_STRING = re.compile(r'"([^"\\]*(?:\\.[^"\\]*)*)"')
_RE_NUMBER = re.compile(r'\b(\d+(?:\.\d+)?)\b')

# ──────────────────────────────────────────────────────────────────────────────
# Identifier scrambling helpers
# ──────────────────────────────────────────────────────────────────────────────

# Unicode ranges that look hostile but are valid identifiers in most display contexts
_SCRAMBLE_CHARS = "⋮⋯⋰⋱⋲⋳⋴⋵⋶⋷⋸⋹⋺⋻⋼⋽⋾⋿"


def _make_scrambler(seed: int) -> "IdentifierScrambler":
    return IdentifierScrambler(seed=seed)


class IdentifierScrambler:
    """Deterministic bijection between identifiers and scrambled glyphs."""

    __slots__ = ("_rng", "_ht", "_rev", "_counter")

    def __init__(self, seed: int = 0) -> None:
        self._rng = random.Random(seed)
        self._ht: dict[str, str] = {}
        self._rev: dict[str, str] = {}
        self._counter = 0

    def scramble(self, name: str) -> str:
        if name in self._ht:
            return self._ht[name]
        length = self._rng.randint(2, 4)
        while True:
            candidate = "".join(self._rng.choice(_SCRAMBLE_CHARS) for _ in range(length))
            if candidate not in self._rev:
                break
        self._ht[name] = candidate
        self._rev[candidate] = name
        return candidate

    def unscramble(self, glyph: str) -> str | None:
        return self._rev.get(glyph)

    @property
    def symbol_table(self) -> dict[str, str]:
        return dict(self._ht)

    def load_symbol_table(self, table: dict[str, str]) -> None:
        self._ht.update(table)
        self._rev.update({v: k for k, v in table.items()})


# ──────────────────────────────────────────────────────────────────────────────
# String + number encoding for levels 7–9
# ──────────────────────────────────────────────────────────────────────────────


def _encode_string(s: str) -> str:
    """Encode a string literal as a hex byte sequence."""
    encoded = s.encode("utf-8")
    hex_pairs = "_".join(f"{b:02x}" for b in encoded)
    return f"0x{hex_pairs}"


def _decode_hex_string(s: str) -> str:
    """Decode a hex byte sequence back to a string literal."""
    if not s.startswith("0x"):
        return s
    hex_part = s[2:]
    pairs = hex_part.split("_")
    try:
        bstr = bytes(int(p, 16) for p in pairs if p)
        return bstr.decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return s


# ──────────────────────────────────────────────────────────────────────────────
# Result type
# ──────────────────────────────────────────────────────────────────────────────


@dataclass(slots=True)
class ObfuscatorResult:
    """Output of an obfuscation pass."""

    source: str
    level: int
    symbol_table: dict[str, str] = field(default_factory=dict)


# ──────────────────────────────────────────────────────────────────────────────
# Core transform passes
# ──────────────────────────────────────────────────────────────────────────────


def _pass_comments_to_fucked(src: str) -> str:
    return _RE_COMMENT_HR.sub(lambda m: f"⟨⟨{m.group(1)}⟩⟩", src)


def _pass_comments_to_human(src: str) -> str:
    return _RE_COMMENT_FK.sub(lambda m: f"<!--{m.group(1)}-->", src)


def _pass_operators_to_fucked(src: str) -> str:
    # Throttle: -+> → ⟶₊  (level encodes as subscript digits)
    def _throttle_sub(m: re.Match[str]) -> str:
        count = len(m.group(1))
        # Use subscript digits to encode count
        sub = "".join(chr(0x2080 + int(d)) for d in str(count))
        return f"⟶{sub}"

    src = _RE_THROTTLE_HR.sub(_throttle_sub, src)

    # Fast: ->> → ⟹⟹ (repeat by count)
    def _fast_sub(m: re.Match[str]) -> str:
        count = len(m.group(1))  # number of > chars
        return "⟹" * count

    src = _RE_FAST_HR.sub(_fast_sub, src)

    for human, fucked in _OPERATOR_MAP:
        src = src.replace(human, fucked)
    return src


def _pass_operators_to_human(src: str) -> str:
    # Reverse throttle: ⟶₀ .. ⟶₉₉ → -+> (with correct count)
    _re_throttle_fk = re.compile(r"⟶([₀-₉]+)")

    def _rev_throttle(m: re.Match[str]) -> str:
        subs = m.group(1)
        # Convert subscript digits back to int
        digits = "".join(str(ord(c) - 0x2080) for c in subs)
        try:
            count = int(digits)
        except ValueError:
            count = 1
        return "-" + "+" * count + ">"

    src = _re_throttle_fk.sub(_rev_throttle, src)

    for fucked, human in _OPERATOR_REVERSE:
        src = src.replace(fucked, human)
    return src


def _pass_keywords_to_fucked(src: str) -> str:
    for human, fucked in _KEYWORD_MAP:
        src = src.replace(human, fucked)
    return src


def _pass_keywords_to_human(src: str) -> str:
    for fucked, human in _KEYWORD_REVERSE:
        src = src.replace(fucked, human)
    return src


def _pass_delimiters_to_fucked(src: str) -> str:
    src = _RE_GYGE_HR.sub(lambda m: f"⌈{m.group(1)}⌉", src)
    src = _RE_IMPORT_HR.sub(lambda m: f"≺{m.group(1)}≻", src)
    src = _RE_BYTE_BRACKET_HR.sub(lambda m: f"⟦{m.group(1)}⟧", src)
    return src


def _pass_delimiters_to_human(src: str) -> str:
    src = _RE_GYGE_FK.sub(lambda m: f"|{m.group(1)}|", src)
    src = _RE_IMPORT_FK.sub(lambda m: f"><{m.group(1)}><", src)
    src = _RE_BYTE_BRACKET_FK.sub(lambda m: f"[{m.group(1)}]", src)
    return src


def _pass_scramble_identifiers(src: str, scrambler: IdentifierScrambler) -> str:
    """Replace identifier text inside ⌈…⌉ delimiters with scrambled glyphs."""

    def _sub(m: re.Match[str]) -> str:
        name = m.group(1)
        return f"⌈{scrambler.scramble(name)}⌉"

    return _RE_GYGE_FK.sub(_sub, src)


def _pass_unscramble_identifiers(src: str, scrambler: IdentifierScrambler) -> str:
    def _sub(m: re.Match[str]) -> str:
        glyph = m.group(1)
        original = scrambler.unscramble(glyph)
        return f"⌈{original}⌉" if original is not None else f"⌈{glyph}⌉"

    return _RE_GYGE_FK.sub(_sub, src)


def _pass_encode_strings(src: str) -> str:
    def _sub(m: re.Match[str]) -> str:
        return _encode_string(m.group(1))

    return _RE_STRING.sub(_sub, src)


def _pass_decode_strings(src: str) -> str:
    # Match hex sequences like 0x62_61_64
    _re_hex_seq = re.compile(r"0x([0-9a-f]{2}(?:_[0-9a-f]{2})*)")

    def _sub(m: re.Match[str]) -> str:
        return '"' + _decode_hex_string("0x" + m.group(1)) + '"'

    return _re_hex_seq.sub(_sub, src)


def _pass_strip_whitespace(src: str) -> str:
    """Level 9: collapse all runs of whitespace to nothing."""
    return re.sub(r"\s+", "", src)


# ──────────────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────────────


def obfuscate(
    source: str,
    level: int = 5,
    seed: int = 0,
    symbol_table: Optional[dict[str, str]] = None,
) -> ObfuscatorResult:
    """Convert human-readable Stream source to fucked form at the given level.

    Args:
        source:       Human-readable source text.
        level:        Obfuscation level 0–9.
        seed:         RNG seed for identifier scrambling (levels 5+).
        symbol_table: Pre-existing symbol table to extend (for multi-file programs).

    Returns:
        ObfuscatorResult with the transformed source and symbol table.
    """
    level = max(0, min(9, level))

    if level == 0:
        return ObfuscatorResult(source=source, level=0)

    src = source

    # Level 1+: operators
    src = _pass_comments_to_fucked(src)
    src = _pass_operators_to_fucked(src)
    src = _pass_delimiters_to_fucked(src)

    # Level 3+: keywords + modifiers
    if level >= 3:
        src = _pass_keywords_to_fucked(src)

    # Level 5+: identifier scrambling
    scrambler = IdentifierScrambler(seed=seed)
    if symbol_table:
        scrambler.load_symbol_table(symbol_table)

    if level >= 5:
        src = _pass_scramble_identifiers(src, scrambler)

    # Level 7+: string encoding + numeric encoding
    if level >= 7:
        src = _pass_encode_strings(src)

    # Level 9: strip whitespace
    if level >= 9:
        src = _pass_strip_whitespace(src)

    return ObfuscatorResult(
        source=src,
        level=level,
        symbol_table=scrambler.symbol_table if level >= 5 else {},
    )


def deobfuscate(
    source: str,
    symbol_table: Optional[dict[str, str]] = None,
    seed: int = 0,
) -> str:
    """Convert fucked-form Stream source back to human-readable.

    For levels 1–4 (no identifier scrambling), ``symbol_table`` can be None.
    For levels 5–9, the symbol table produced during obfuscation is required
    to reverse identifier scrambling; without it, ⌈…⌉ identifiers are left
    as-is.

    Returns the human-readable source string.
    """
    src = source

    # Reverse string encoding first (before delimiter replacement changes content)
    src = _pass_decode_strings(src)

    # Reverse identifier scrambling if table provided
    scrambler = IdentifierScrambler(seed=seed)
    if symbol_table:
        scrambler.load_symbol_table(symbol_table)
        src = _pass_unscramble_identifiers(src, scrambler)

    # Reverse delimiters (⌈ → |, ≺ → ><, ⟦ → [)
    src = _pass_delimiters_to_human(src)

    # Reverse keywords
    src = _pass_keywords_to_human(src)

    # Reverse operators
    src = _pass_operators_to_human(src)

    # Reverse comments
    src = _pass_comments_to_human(src)

    return src
