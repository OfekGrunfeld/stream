"""Stream language lexer — tokenises human-readable source into a flat token stream.

Longest-match rules (critical precedence):
  ==>  before  =>
  -!!->  before  -!->
  -?*->  before  -?->
  -/|cond|\\->  before  -/|\\->  before  -/>
  -+>  (one or more +)   →  STREAM_THROTTLE  with level = count(+)
  ->>  (two or more >)   →  STREAM_FAST      with level = count(>) - 1
  -,→ commas+condition   →  STREAM_WAIT      with stages, condition
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Iterator

from stream.errors import LexError

__all__ = ["TokenKind", "Token", "lex"]


# ──────────────────────────────────────────────────────────────────────────────
# Token kinds
# ──────────────────────────────────────────────────────────────────────────────


class TokenKind(StrEnum):
    # Stream operators
    STREAM_BASIC = "STREAM_BASIC"
    STREAM_PRIORITY = "STREAM_PRIORITY"
    STREAM_LOSSY = "STREAM_LOSSY"
    STREAM_FILTER = "STREAM_FILTER"
    STREAM_FILTER_COND = "STREAM_FILTER_COND"
    STREAM_BLOCKED = "STREAM_BLOCKED"
    STREAM_THROTTLE = "STREAM_THROTTLE"
    STREAM_FAST = "STREAM_FAST"
    STREAM_SWITCH = "STREAM_SWITCH"
    STREAM_BATCHER = "STREAM_BATCHER"
    STREAM_SPLITTER = "STREAM_SPLITTER"
    STREAM_ARG_FILTER = "STREAM_ARG_FILTER"
    STREAM_ERROR = "STREAM_ERROR"
    STREAM_EXIT = "STREAM_EXIT"
    STREAM_CATCH = "STREAM_CATCH"
    STREAM_SIGNAL = "STREAM_SIGNAL"
    STREAM_RECEIVE = "STREAM_RECEIVE"
    STREAM_WAIT = "STREAM_WAIT"
    STREAM_PARASITE = "STREAM_PARASITE"
    STREAM_FEEDBACK = "STREAM_FEEDBACK"

    # Gyge / program primitives
    GYGE = "GYGE"  # |name| — name in .value, hint in .value2
    GYGE_BYTE_ACCESS = "GYGE_BYTE_ACCESS"  # [|buf|+4..12] — expr in .value
    ALLOC = "ALLOC"  # <o/
    DEALLOC = "DEALLOC"  # <o\
    ENTRY_POINT = "ENTRY_POINT"  # <o->
    THIS_PROGRAM = "THIS_PROGRAM"  # <o>
    IMPORT_STMT = "IMPORT_STMT"  # ><name>< — name in .value, ns in .value2

    # Section / structure
    ASSIGN = "ASSIGN"  # :=
    SECTION = "SECTION"  # ::name:: — name in .value, guard in .value2
    COLONCOLON = "COLONCOLON"  # :: standalone (for signal receive separator)

    # Modifiers
    MOD_SEASON = "MOD_SEASON"
    MOD_TEMP = "MOD_TEMP"
    MOD_TIME = "MOD_TIME"
    MOD_ENTROPY = "MOD_ENTROPY"

    # Parasite/signal targets
    TARGET_PID = "TARGET_PID"
    TARGET_NAME = "TARGET_NAME"
    TARGET_PORT = "TARGET_PORT"
    TARGET_IP = "TARGET_IP"
    TARGET_DIR = "TARGET_DIR"
    TARGET_BROADCAST = "TARGET_BROADCAST"

    # Literals / identifiers
    STRING = "STRING"
    INTEGER = "INTEGER"
    FLOAT = "FLOAT"
    VOID = "VOID"
    IDENT = "IDENT"

    # Season keyword values
    KW_SPRING = "KW_SPRING"
    KW_SUMMER = "KW_SUMMER"
    KW_AUTUMN = "KW_AUTUMN"
    KW_WINTER = "KW_WINTER"

    # Punctuation
    LBRACE = "LBRACE"
    RBRACE = "RBRACE"
    LBRACKET = "LBRACKET"
    RBRACKET = "RBRACKET"
    PLUS = "PLUS"
    AMP_COMPOSE = "AMP_COMPOSE"  # &->
    AMP_FUSE = "AMP_FUSE"  # &
    BACK_SEND = "BACK_SEND"  # <- (control channel send)

    EOF = "EOF"


_SEASON_KEYWORDS: dict[str, TokenKind] = {
    "spring": TokenKind.KW_SPRING,
    "summer": TokenKind.KW_SUMMER,
    "autumn": TokenKind.KW_AUTUMN,
    "winter": TokenKind.KW_WINTER,
}


# ──────────────────────────────────────────────────────────────────────────────
# Token dataclass
# ──────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class Token:
    kind: TokenKind
    raw: str
    line: int
    col: int
    value: str = ""
    value2: str = ""  # secondary: condition text, namespace, section guard
    level: int = 0  # operator depth (throttle '+' count, fast '>' count, wait ',' count)

    def __repr__(self) -> str:
        extra = ""
        if self.value:
            extra += f" value={self.value!r}"
        if self.value2:
            extra += f" value2={self.value2!r}"
        if self.level:
            extra += f" level={self.level}"
        return f"Token({self.kind} @ {self.line}:{self.col}{extra})"


# ──────────────────────────────────────────────────────────────────────────────
# Comment stripping
# ──────────────────────────────────────────────────────────────────────────────

_COMMENT_RE = re.compile(r"<--.*?-->", re.DOTALL)


def _strip_comments(source: str) -> str:
    return _COMMENT_RE.sub("", source)


# ──────────────────────────────────────────────────────────────────────────────
# Main token patterns (order = longest-match priority)
# ──────────────────────────────────────────────────────────────────────────────

# Named groups drive token production.  Patterns are tried in listed order via
# the master alternation regex; first match wins.
_RAW_PATTERNS: list[tuple[str, str]] = [
    # ── Whitespace (skip) ───────────────────────────────────────────────
    ("SKIP", r"[ \t\r\n]+"),
    # ── Stream operators (longest-match order) ──────────────────────────
    ("STREAM_PARASITE", r"==>"),
    ("STREAM_EXIT", r"-!!->"),
    ("STREAM_RECEIVE", r"-\?\*->"),
    ("STREAM_CATCH", r"-\?->"),
    ("STREAM_SIGNAL", r"-\*->"),
    ("STREAM_SPLITTER", r"-\.\.\.->"),
    ("STREAM_BATCHER", r"-#->"),
    ("STREAM_ERROR", r"-!->"),
    # Conditional filter/switch: -/|condition|\->  (condition has no pipe/backslash)
    ("STREAM_FILTER_COND", r"-/\|([^|\\]*)\|\\->"),
    # Bare switch: -/|\->
    ("STREAM_SWITCH", r"-/\|\\->"),
    # Simple filter: -/>
    ("STREAM_FILTER", r"-/>"),
    # Blocked: -x>
    ("STREAM_BLOCKED", r"-x>"),
    # Throttle: -+> -++> -+++> …
    ("STREAM_THROTTLE", r"-(\++>)"),
    # Fast: ->> ->>> …  (two or more >)
    ("STREAM_FAST", r"->{2,}"),
    # Wait with condition: -,(,*)condition->  (condition ends at ->)
    ("STREAM_WAIT", r"-(,{1,})([^-](?:[^->]|-(?!>))*)?->"),
    # Priority
    ("STREAM_PRIORITY", r"=>"),
    # Lossy
    ("STREAM_LOSSY", r"~>"),
    # Feedback loop
    ("STREAM_FEEDBACK", r"<~"),
    # Basic
    ("STREAM_BASIC", r"->"),
    # ── Control-channel back-send ────────────────────────────────────────
    ("BACK_SEND", r"<-"),
    # ── Gyge primitives ─────────────────────────────────────────────────
    ("ENTRY_POINT", r"<o->"),
    ("ALLOC", r"<o/"),
    ("DEALLOC", r"<o\\"),
    ("THIS_PROGRAM", r"<o>"),
    # ── Import: ><name>< or ><name+ns>< ─────────────────────────────────
    ("IMPORT_STMT", r"><([A-Za-z_][A-Za-z0-9_]*)(?:\+([A-Za-z_][A-Za-z0-9_]*))?><"),
    # ── Composition: &-> (before &) ─────────────────────────────────────
    ("AMP_COMPOSE", r"&->"),
    ("AMP_FUSE", r"&"),
    # ── Section: ::name[guard]:: ─────────────────────────────────────────
    ("SECTION", r"::([A-Za-z_][A-Za-z0-9_ ]*)(?:\[([^\]]*)\])?::"),
    # ── Standalone :: (used in signal-receive separator) ─────────────────
    ("COLONCOLON", r"::"),
    # ── Assignment ───────────────────────────────────────────────────────
    ("ASSIGN", r":="),
    # ── Modifiers ────────────────────────────────────────────────────────
    ("MOD_ENTROPY", r"\$entropy"),
    ("MOD_SEASON", r"\$S"),
    ("MOD_TEMP", r"\$C"),
    ("MOD_TIME", r"\$@"),
    # ── Parasite targets ─────────────────────────────────────────────────
    ("TARGET_PID", r"@pid:(-?\d+)"),
    ("TARGET_PORT", r"@port:(\d+)"),
    ("TARGET_NAME", r'@name:"([^"]*)"'),
    ("TARGET_IP", r'@ip:"([^"]*)"'),
    ("TARGET_DIR", r'@dir:"([^"]*)"'),
    ("TARGET_BROADCAST", r"@\*"),
    # ── Gyge byte-access: [|name|...] ────────────────────────────────────
    ("GYGE_BYTE_ACCESS", r"\[(\|[A-Za-z_][A-Za-z0-9_]*\|[^\]]*)\]"),
    # ── Gyge: |name| with optional hint prefix ───────────────────────────
    ("GYGE", r"\|([%@~?!#]?)([A-Za-z_][A-Za-z0-9_]*)\|"),
    # ── Void ─────────────────────────────────────────────────────────────
    ("VOID", r"\.\.\."),
    # ── String literal ────────────────────────────────────────────────────
    ("STRING", r'"([^"\\]|\\.)*"'),
    # ── Numeric literals ─────────────────────────────────────────────────
    ("FLOAT", r"\d+\.\d+"),
    ("INTEGER", r"-?\d+"),
    # ── Identifiers / season keywords ────────────────────────────────────
    ("IDENT", r"[A-Za-z_][A-Za-z0-9_]*"),
    # ── Punctuation ──────────────────────────────────────────────────────
    ("LBRACE", r"\{"),
    ("RBRACE", r"\}"),
    ("LBRACKET", r"\["),
    ("RBRACKET", r"\]"),
    ("PLUS", r"\+"),
    # ── Catch-all (illegal character) ────────────────────────────────────
    ("ILLEGAL", r"."),
]

# Build master regex with named groups
_MASTER_RE = re.compile(
    "|".join(f"(?P<{name}>{pat})" for name, pat in _RAW_PATTERNS)
)


# ──────────────────────────────────────────────────────────────────────────────
# Lexer
# ──────────────────────────────────────────────────────────────────────────────


def lex(source: str, filename: str = "<stdin>") -> list[Token]:
    """Tokenise *source* into a list of Tokens (EOF-terminated).

    Raises:
        LexError: on any illegal character.
    """
    clean = _strip_comments(source)
    tokens: list[Token] = []

    # Track line/col manually
    line = 1
    line_start = 0

    for m in _MASTER_RE.finditer(clean):
        kind_name = m.lastgroup
        raw = m.group(0)
        col = m.start() - line_start + 1

        # Advance line tracking
        newlines = raw.count("\n")
        if newlines:
            line += newlines
            line_start = m.start() + raw.rfind("\n") + 1

        if kind_name == "SKIP":
            continue
        if kind_name == "ILLEGAL":
            raise LexError(f"Unexpected character {raw!r}", line, col)

        tok = _build_token(kind_name, m, raw, line, col)
        if tok is not None:
            tokens.append(tok)

    tokens.append(Token(TokenKind.EOF, "", line, 0))
    return tokens


def _build_token(  # noqa: PLR0911  (many returns is fine for dispatch)
    kind_name: str,
    m: re.Match[str],
    raw: str,
    line: int,
    col: int,
) -> Token | None:
    """Convert a regex match into a Token."""

    def tok(
        kind: TokenKind,
        value: str = "",
        value2: str = "",
        level: int = 0,
    ) -> Token:
        return Token(kind, raw, line, col, value, value2, level)

    match kind_name:
        # ── Stream operators ────────────────────────────────────────────
        case "STREAM_BASIC":
            return tok(TokenKind.STREAM_BASIC)
        case "STREAM_PRIORITY":
            return tok(TokenKind.STREAM_PRIORITY)
        case "STREAM_LOSSY":
            return tok(TokenKind.STREAM_LOSSY)
        case "STREAM_FILTER":
            return tok(TokenKind.STREAM_FILTER)
        case "STREAM_FILTER_COND":
            # raw = "-/|cond|\->"  →  condition between first and second |
            parts = raw.split("|")
            condition = parts[1] if len(parts) > 2 else ""
            return tok(TokenKind.STREAM_FILTER_COND, value=condition.strip())
        case "STREAM_SWITCH":
            return tok(TokenKind.STREAM_SWITCH)
        case "STREAM_BLOCKED":
            return tok(TokenKind.STREAM_BLOCKED)
        case "STREAM_THROTTLE":
            # raw = "-+>" / "-++>" etc.  level = number of '+' chars
            return tok(TokenKind.STREAM_THROTTLE, level=raw.count("+"))
        case "STREAM_FAST":
            # raw = "->>" / "->>>" etc.  level = extra '>' count beyond first
            return tok(TokenKind.STREAM_FAST, level=raw.count(">") - 1)
        case "STREAM_WAIT":
            # raw = "-(,+)(condition)?->"  extract comma count and condition text
            inner = raw[1:-2]  # strip leading '-' and trailing '->'
            level = len(inner) - len(inner.lstrip(","))
            condition = inner.lstrip(",").strip()
            return tok(TokenKind.STREAM_WAIT, value=condition, level=level)
        case "STREAM_BATCHER":
            return tok(TokenKind.STREAM_BATCHER)
        case "STREAM_SPLITTER":
            return tok(TokenKind.STREAM_SPLITTER)
        case "STREAM_ERROR":
            return tok(TokenKind.STREAM_ERROR)
        case "STREAM_EXIT":
            return tok(TokenKind.STREAM_EXIT)
        case "STREAM_CATCH":
            return tok(TokenKind.STREAM_CATCH)
        case "STREAM_SIGNAL":
            return tok(TokenKind.STREAM_SIGNAL)
        case "STREAM_RECEIVE":
            return tok(TokenKind.STREAM_RECEIVE)
        case "STREAM_PARASITE":
            return tok(TokenKind.STREAM_PARASITE)
        case "STREAM_FEEDBACK":
            return tok(TokenKind.STREAM_FEEDBACK)
        # ── Arg-filter: handled via IDENT/special in parser ─────────────

        # ── Gyge primitives ─────────────────────────────────────────────
        case "GYGE":
            # raw = "|name|" or "|%name|" etc.
            inner = raw[1:-1]  # strip surrounding pipes
            if inner and inner[0] in "%@~?!#":
                hint_char, name = inner[0], inner[1:]
            else:
                hint_char, name = "", inner
            return tok(TokenKind.GYGE, value=name, value2=hint_char)
        case "GYGE_BYTE_ACCESS":
            # raw = "[|name|expr]"
            return tok(TokenKind.GYGE_BYTE_ACCESS, value=raw[1:-1])
        case "ALLOC":
            return tok(TokenKind.ALLOC)
        case "DEALLOC":
            return tok(TokenKind.DEALLOC)
        case "ENTRY_POINT":
            return tok(TokenKind.ENTRY_POINT)
        case "THIS_PROGRAM":
            return tok(TokenKind.THIS_PROGRAM)
        case "IMPORT_STMT":
            # raw = "><name><" or "><name+ns><"
            inner = raw[2:-2]
            if "+" in inner:
                name, ns = inner.split("+", 1)
            else:
                name, ns = inner, ""
            return tok(TokenKind.IMPORT_STMT, value=name, value2=ns)

        # ── Structure ────────────────────────────────────────────────────
        case "ASSIGN":
            return tok(TokenKind.ASSIGN)
        case "SECTION":
            # raw = "::name::" or "::name[guard]::"
            inner = raw[2:-2]  # strip leading and trailing "::"
            if "[" in inner:
                name, rest = inner.split("[", 1)
                guard = rest.rstrip("]")
            else:
                name, guard = inner, ""
            return tok(TokenKind.SECTION, value=name.strip(), value2=guard.strip())
        case "COLONCOLON":
            return tok(TokenKind.COLONCOLON)

        # ── Modifiers ────────────────────────────────────────────────────
        case "MOD_SEASON":
            return tok(TokenKind.MOD_SEASON)
        case "MOD_TEMP":
            return tok(TokenKind.MOD_TEMP)
        case "MOD_TIME":
            return tok(TokenKind.MOD_TIME)
        case "MOD_ENTROPY":
            return tok(TokenKind.MOD_ENTROPY)

        # ── Targets ──────────────────────────────────────────────────────
        case "TARGET_PID":
            # raw = "@pid:1337"
            return tok(TokenKind.TARGET_PID, value=raw[5:])
        case "TARGET_PORT":
            # raw = "@port:8080"
            return tok(TokenKind.TARGET_PORT, value=raw[6:])
        case "TARGET_NAME":
            # raw = '@name:"alice"'
            return tok(TokenKind.TARGET_NAME, value=raw[7:-1])
        case "TARGET_IP":
            # raw = '@ip:"1.2.3.4"'
            return tok(TokenKind.TARGET_IP, value=raw[5:-1])
        case "TARGET_DIR":
            # raw = '@dir:"/some/path"'
            return tok(TokenKind.TARGET_DIR, value=raw[6:-1])
        case "TARGET_BROADCAST":
            return tok(TokenKind.TARGET_BROADCAST)

        # ── Literals ─────────────────────────────────────────────────────
        case "STRING":
            content = raw[1:-1].replace('\\"', '"').replace("\\\\", "\\")
            return tok(TokenKind.STRING, value=content)
        case "INTEGER":
            return tok(TokenKind.INTEGER, value=raw)
        case "FLOAT":
            return tok(TokenKind.FLOAT, value=raw)
        case "VOID":
            return tok(TokenKind.VOID)
        case "IDENT":
            if raw in _SEASON_KEYWORDS:
                return tok(_SEASON_KEYWORDS[raw])
            return tok(TokenKind.IDENT, value=raw)

        # ── Punctuation ──────────────────────────────────────────────────
        case "LBRACE":
            return tok(TokenKind.LBRACE)
        case "RBRACE":
            return tok(TokenKind.RBRACE)
        case "LBRACKET":
            return tok(TokenKind.LBRACKET)
        case "RBRACKET":
            return tok(TokenKind.RBRACKET)
        case "PLUS":
            return tok(TokenKind.PLUS)
        case "AMP_COMPOSE":
            return tok(TokenKind.AMP_COMPOSE)
        case "AMP_FUSE":
            return tok(TokenKind.AMP_FUSE)
        case "BACK_SEND":
            return tok(TokenKind.BACK_SEND)

        case _:
            return None
