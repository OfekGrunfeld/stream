"""Stream language parser — converts a token stream into an Abstract Syntax Graph.

The ASG is a directed multigraph (not a tree). Feedback edges (`<~`) create cycles.
Nodes are GygeNode objects; edges are StreamEdge objects. The parser collects both
and returns an ASG that the graph builder then converts to runtime GIR/SCD structures.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import StrEnum

from stream.errors import ParseError
from stream.lexer import Token, TokenKind, lex

__all__ = [
    "ASG",
    "GygeNode",
    "LiteralNode",
    "ModifierNode",
    "TargetNode",
    "VoidNode",
    "StreamEdge",
    "Section",
    "ProgramASG",
    "parse",
]

# ──────────────────────────────────────────────────────────────────────────────
# ASG node types
# ──────────────────────────────────────────────────────────────────────────────

type NodeId = str


def _new_id() -> NodeId:
    return str(uuid.uuid4())


@dataclass(slots=True)
class GygeNode:
    """A named gyge — the only type in Stream."""

    name: str
    hint: str = ""  # optional type hint prefix: %, @, ~, ?, !, #
    node_id: NodeId = field(default_factory=_new_id)


@dataclass(slots=True)
class LiteralNode:
    """A literal value source (string, int, float)."""

    value: str | int | float
    node_id: NodeId = field(default_factory=_new_id)


@dataclass(slots=True)
class ModifierNode:
    """A modifier reference ($S, $C, $@, $entropy)."""

    kind: str  # "season" | "temp" | "time" | "entropy"
    node_id: NodeId = field(default_factory=_new_id)


@dataclass(slots=True)
class TargetNode:
    """A parasite/signal target (@pid:N, @name:"x", etc.)."""

    kind: str  # "pid" | "name" | "port" | "ip" | "dir" | "broadcast"
    value: str  # the resolved value (PID as str, name, etc.)
    node_id: NodeId = field(default_factory=_new_id)


@dataclass(slots=True)
class VoidNode:
    """The void / discard sink (...)."""

    node_id: NodeId = field(default_factory=_new_id)


@dataclass(slots=True)
class BranchBlockNode:
    """A `{|a| |b|}` branch block used by switch/splitter operators."""

    branches: list[GygeNode]
    node_id: NodeId = field(default_factory=_new_id)


AnyNode = GygeNode | LiteralNode | ModifierNode | TargetNode | VoidNode | BranchBlockNode


# ──────────────────────────────────────────────────────────────────────────────
# Stream edge (represents one stream operator + connection)
# ──────────────────────────────────────────────────────────────────────────────


class StreamKind(StrEnum):
    BASIC = "->"
    PRIORITY = "=>"
    LOSSY = "~>"
    FILTER = "-/>"
    FILTER_COND = "-/|cond|\\->"
    BLOCKED = "-x>"
    THROTTLE = "-+>"
    FAST = "->>"
    SWITCH = "-/|\\->"
    BATCHER = "-#->"
    SPLITTER = "-...->"
    ARG_FILTER = "-|->"
    ERROR = "-!->"
    EXIT = "-!!->"
    CATCH = "-?->"
    SIGNAL = "-*->"
    RECEIVE = "-?*->"
    WAIT = "-,->"
    PARASITE = "==>"
    FEEDBACK = "<~"


@dataclass(slots=True)
class StreamEdge:
    """One typed stream edge in the ASG."""

    kind: StreamKind
    source_id: NodeId
    dest_id: NodeId
    condition: str = ""  # for FILTER_COND, SWITCH
    level: int = 0  # throttle depth, fast speed, wait stages
    is_back_edge: bool = False  # True for feedback (<~) edges


# ──────────────────────────────────────────────────────────────────────────────
# Statements (non-stream-chain constructs)
# ──────────────────────────────────────────────────────────────────────────────


@dataclass(slots=True)
class AssignStmt:
    """gyge := value"""

    target: GygeNode
    rhs: AnyNode  # literal, alloc, void, modifier, gyge


@dataclass(slots=True)
class AllocStmt:
    """gyge := <o/"""

    target: GygeNode


@dataclass(slots=True)
class DeallocStmt:
    """<o\\ |gyge|"""

    target: GygeNode


@dataclass(slots=True)
class EntryPointStmt:
    """<o-> "name" """

    name: str


@dataclass(slots=True)
class ImportStmt:
    """"><name><" or "><name+ns><" """

    module: str
    namespace: str = ""


@dataclass(slots=True)
class ModifierSetStmt:
    """$S := winter  /  $entropy := 7"""

    modifier: str  # "season" | "temp" | "time" | "entropy"
    value: str  # season name or numeric string or "..."


@dataclass(slots=True)
class SignalReceiveStmt:
    """-?*-> @port:9090 :: |buf|"""

    source: TargetNode | ModifierNode
    dest: GygeNode


@dataclass(slots=True)
class ParasiteDeclStmt:
    """::parasite |name| { ... }  (full lifecycle declaration)"""

    name: str
    body_raw: str  # raw text of the body (parsed lazily)


AnyStmt = (
    AssignStmt
    | AllocStmt
    | DeallocStmt
    | EntryPointStmt
    | ImportStmt
    | ModifierSetStmt
    | SignalReceiveStmt
    | ParasiteDeclStmt
)


# ──────────────────────────────────────────────────────────────────────────────
# Section and top-level ASG
# ──────────────────────────────────────────────────────────────────────────────


@dataclass(slots=True)
class Section:
    """A named section (::body::, ::header::, etc.)."""

    name: str
    guard: str  # condition string like "$S:winter" or "$entropy > 7"
    stmts: list[AnyStmt] = field(default_factory=list)
    edges: list[StreamEdge] = field(default_factory=list)


@dataclass(slots=True)
class ProgramASG:
    """The complete Abstract Syntax Graph of one Stream program."""

    entry_name: str = ""  # from <o-> "name"
    sections: list[Section] = field(default_factory=list)
    nodes: dict[str, AnyNode] = field(default_factory=dict)  # name → GygeNode
    all_edges: list[StreamEdge] = field(default_factory=list)
    imports: list[ImportStmt] = field(default_factory=list)


# Alias for backward compatibility
ASG = ProgramASG


# ──────────────────────────────────────────────────────────────────────────────
# Recursive-descent parser
# ──────────────────────────────────────────────────────────────────────────────

_STREAM_OP_KINDS: frozenset[TokenKind] = frozenset(
    {
        TokenKind.STREAM_BASIC,
        TokenKind.STREAM_PRIORITY,
        TokenKind.STREAM_LOSSY,
        TokenKind.STREAM_FILTER,
        TokenKind.STREAM_FILTER_COND,
        TokenKind.STREAM_BLOCKED,
        TokenKind.STREAM_THROTTLE,
        TokenKind.STREAM_FAST,
        TokenKind.STREAM_SWITCH,
        TokenKind.STREAM_BATCHER,
        TokenKind.STREAM_SPLITTER,
        TokenKind.STREAM_ARG_FILTER,
        TokenKind.STREAM_ERROR,
        TokenKind.STREAM_EXIT,
        TokenKind.STREAM_CATCH,
        TokenKind.STREAM_SIGNAL,
        TokenKind.STREAM_RECEIVE,
        TokenKind.STREAM_WAIT,
        TokenKind.STREAM_PARASITE,
        TokenKind.STREAM_FEEDBACK,
    }
)

_CHAIN_START_KINDS: frozenset[TokenKind] = frozenset(
    {
        TokenKind.GYGE,
        TokenKind.GYGE_BYTE_ACCESS,
        TokenKind.STRING,
        TokenKind.INTEGER,
        TokenKind.FLOAT,
        TokenKind.VOID,
        TokenKind.MOD_SEASON,
        TokenKind.MOD_TEMP,
        TokenKind.MOD_TIME,
        TokenKind.MOD_ENTROPY,
        TokenKind.TARGET_PID,
        TokenKind.TARGET_NAME,
        TokenKind.TARGET_PORT,
        TokenKind.TARGET_IP,
        TokenKind.TARGET_DIR,
        TokenKind.TARGET_BROADCAST,
        TokenKind.THIS_PROGRAM,
        # Receive/signal streams can start a chain
        TokenKind.STREAM_RECEIVE,
        TokenKind.STREAM_SIGNAL,
        TokenKind.STREAM_CATCH,
        TokenKind.STREAM_ERROR,
        TokenKind.STREAM_EXIT,
    }
)


class _Parser:
    __slots__ = ("_tokens", "_pos", "_asg", "_current_section")

    def __init__(self, tokens: list[Token]) -> None:
        self._tokens = tokens
        self._pos = 0
        self._asg = ProgramASG()
        self._current_section: Section | None = None

    # ── Helpers ──────────────────────────────────────────────────────────

    def _peek(self) -> Token:
        return self._tokens[self._pos]

    def _advance(self) -> Token:
        tok = self._tokens[self._pos]
        self._pos += 1
        return tok

    def _check(self, *kinds: TokenKind) -> bool:
        return self._peek().kind in kinds

    def _expect(self, kind: TokenKind) -> Token:
        tok = self._peek()
        if tok.kind != kind:
            raise ParseError(
                f"Expected {kind}, got {tok.kind} ({tok.raw!r})", tok.line, tok.col
            )
        return self._advance()

    def _at_eof(self) -> bool:
        return self._peek().kind == TokenKind.EOF

    # ── Gyge registry ────────────────────────────────────────────────────

    def _get_or_create_gyge(self, name: str, hint: str = "") -> GygeNode:
        if name not in self._asg.nodes:
            self._asg.nodes[name] = GygeNode(name=name, hint=hint)
        node = self._asg.nodes[name]
        assert isinstance(node, GygeNode)
        return node

    # ── Top-level parse ──────────────────────────────────────────────────

    def parse(self) -> ProgramASG:
        while not self._at_eof():
            if self._check(TokenKind.SECTION):
                self._parse_section()
            elif self._check(TokenKind.IMPORT_STMT):
                stmt = self._parse_import()
                self._asg.imports.append(stmt)
            else:
                # Top-level statement outside a section
                self._parse_statement()
        return self._asg

    def _parse_section(self) -> None:
        tok = self._expect(TokenKind.SECTION)
        sec = Section(name=tok.value, guard=tok.value2)
        self._asg.sections.append(sec)
        self._current_section = sec

        while not self._at_eof() and not self._check(TokenKind.SECTION):
            self._parse_statement()

        self._current_section = None

    def _add_stmt(self, stmt: AnyStmt) -> None:
        if self._current_section is not None:
            self._current_section.stmts.append(stmt)

    def _add_edge(self, edge: StreamEdge) -> None:
        self._asg.all_edges.append(edge)
        if self._current_section is not None:
            self._current_section.edges.append(edge)

    # ── Statement dispatch ───────────────────────────────────────────────

    def _parse_statement(self) -> None:
        tok = self._peek()

        match tok.kind:
            case TokenKind.ENTRY_POINT:
                self._advance()
                name_tok = self._expect(TokenKind.STRING)
                stmt = EntryPointStmt(name=name_tok.value)
                self._asg.entry_name = name_tok.value
                self._add_stmt(stmt)

            case TokenKind.ALLOC:
                self._advance()
                # <o/ as RHS of assignment is handled in assignment parsing
                # but bare <o/ is an error; skip quietly
                pass

            case TokenKind.DEALLOC:
                self._advance()
                gyge_tok = self._expect(TokenKind.GYGE)
                node = self._get_or_create_gyge(gyge_tok.value, gyge_tok.value2)
                self._add_stmt(DeallocStmt(target=node))

            case TokenKind.IMPORT_STMT:
                self._asg.imports.append(self._parse_import())

            case (
                TokenKind.MOD_SEASON
                | TokenKind.MOD_ENTROPY
                | TokenKind.MOD_TEMP
                | TokenKind.MOD_TIME
            ):
                self._parse_modifier_set()

            case TokenKind.GYGE:
                # Could be: assignment OR stream chain start
                has_next = self._pos + 1 < len(self._tokens)
                next_kind = self._tokens[self._pos + 1].kind if has_next else None
                if next_kind == TokenKind.ASSIGN:
                    self._parse_assignment()
                else:
                    self._parse_stream_chain()

            case TokenKind.STREAM_RECEIVE:
                # -?*-> target :: |gyge|
                self._parse_signal_receive()

            case _ if tok.kind in _CHAIN_START_KINDS:
                self._parse_stream_chain()

            case _:
                # Skip unknown token (e.g., stray punctuation)
                self._advance()

    def _parse_import(self) -> ImportStmt:
        tok = self._expect(TokenKind.IMPORT_STMT)
        return ImportStmt(module=tok.value, namespace=tok.value2)

    def _parse_assignment(self) -> None:
        gyge_tok = self._expect(TokenKind.GYGE)
        node = self._get_or_create_gyge(gyge_tok.value, gyge_tok.value2)
        self._expect(TokenKind.ASSIGN)

        rhs_tok = self._peek()
        match rhs_tok.kind:
            case TokenKind.ALLOC:
                self._advance()
                self._add_stmt(AllocStmt(target=node))
            case TokenKind.VOID:
                self._advance()
                self._add_stmt(AssignStmt(target=node, rhs=VoidNode()))
            case TokenKind.STRING:
                self._advance()
                self._add_stmt(
                    AssignStmt(target=node, rhs=LiteralNode(value=rhs_tok.value))
                )
            case TokenKind.INTEGER:
                self._advance()
                self._add_stmt(
                    AssignStmt(target=node, rhs=LiteralNode(value=int(rhs_tok.value)))
                )
            case TokenKind.FLOAT:
                self._advance()
                self._add_stmt(
                    AssignStmt(target=node, rhs=LiteralNode(value=float(rhs_tok.value)))
                )
            case TokenKind.GYGE:
                self._advance()
                rhs_node = self._get_or_create_gyge(rhs_tok.value, rhs_tok.value2)
                # Check for composition: &-> or &
                if self._check(TokenKind.AMP_COMPOSE):
                    self._advance()
                    other_tok = self._expect(TokenKind.GYGE)
                    self._get_or_create_gyge(other_tok.value, other_tok.value2)
                    # Create composed gyge
                    composed = GygeNode(name=node.name, hint="pipeline")
                    self._add_stmt(AssignStmt(target=node, rhs=rhs_node))
                    _ = composed  # TODO: track composition in graph
                elif self._check(TokenKind.AMP_FUSE):
                    self._advance()
                    other_tok = self._expect(TokenKind.GYGE)
                    _ = self._get_or_create_gyge(other_tok.value, other_tok.value2)
                    self._add_stmt(AssignStmt(target=node, rhs=rhs_node))
                else:
                    self._add_stmt(AssignStmt(target=node, rhs=rhs_node))
            case TokenKind.MOD_SEASON:
                self._advance()
                self._add_stmt(
                    AssignStmt(target=node, rhs=ModifierNode(kind="season"))
                )
            case _:
                raise ParseError(
                    f"Unexpected RHS in assignment: {rhs_tok.kind}",
                    rhs_tok.line,
                    rhs_tok.col,
                )

    def _parse_modifier_set(self) -> None:
        mod_tok = self._advance()
        mod_kind = {
            TokenKind.MOD_SEASON: "season",
            TokenKind.MOD_TEMP: "temp",
            TokenKind.MOD_TIME: "time",
            TokenKind.MOD_ENTROPY: "entropy",
        }[mod_tok.kind]

        self._expect(TokenKind.ASSIGN)
        val_tok = self._peek()

        match val_tok.kind:
            case TokenKind.KW_SPRING:
                self._advance()
                self._add_stmt(ModifierSetStmt(modifier=mod_kind, value="spring"))
            case TokenKind.KW_SUMMER:
                self._advance()
                self._add_stmt(ModifierSetStmt(modifier=mod_kind, value="summer"))
            case TokenKind.KW_AUTUMN:
                self._advance()
                self._add_stmt(ModifierSetStmt(modifier=mod_kind, value="autumn"))
            case TokenKind.KW_WINTER:
                self._advance()
                self._add_stmt(ModifierSetStmt(modifier=mod_kind, value="winter"))
            case TokenKind.INTEGER | TokenKind.FLOAT:
                self._advance()
                self._add_stmt(ModifierSetStmt(modifier=mod_kind, value=val_tok.value))
            case TokenKind.VOID:
                self._advance()
                self._add_stmt(ModifierSetStmt(modifier=mod_kind, value="..."))
            case TokenKind.MOD_SEASON:
                # $S := $S  (use real system season)
                self._advance()
                self._add_stmt(ModifierSetStmt(modifier=mod_kind, value="$S"))
            case _:
                raise ParseError(
                    f"Unexpected modifier value: {val_tok.kind}",
                    val_tok.line,
                    val_tok.col,
                )

    def _parse_signal_receive(self) -> None:
        """-?*-> target :: |gyge|"""
        self._expect(TokenKind.STREAM_RECEIVE)
        source = self._parse_target_or_modifier()
        self._expect(TokenKind.COLONCOLON)
        gyge_tok = self._expect(TokenKind.GYGE)
        dest = self._get_or_create_gyge(gyge_tok.value, gyge_tok.value2)
        self._add_stmt(SignalReceiveStmt(source=source, dest=dest))

    def _parse_target_or_modifier(self) -> TargetNode | ModifierNode:
        tok = self._peek()
        match tok.kind:
            case TokenKind.TARGET_PID:
                self._advance()
                return TargetNode(kind="pid", value=tok.value)
            case TokenKind.TARGET_PORT:
                self._advance()
                return TargetNode(kind="port", value=tok.value)
            case TokenKind.TARGET_NAME:
                self._advance()
                return TargetNode(kind="name", value=tok.value)
            case TokenKind.TARGET_IP:
                self._advance()
                return TargetNode(kind="ip", value=tok.value)
            case TokenKind.TARGET_DIR:
                self._advance()
                return TargetNode(kind="dir", value=tok.value)
            case TokenKind.TARGET_BROADCAST:
                self._advance()
                return TargetNode(kind="broadcast", value="*")
            case TokenKind.MOD_SEASON:
                self._advance()
                return ModifierNode(kind="season")
            case TokenKind.MOD_TEMP:
                self._advance()
                return ModifierNode(kind="temp")
            case _:
                raise ParseError(
                    f"Expected target or modifier, got {tok.kind}", tok.line, tok.col
                )

    # ── Stream chain parsing ──────────────────────────────────────────────

    def _parse_stream_chain(self) -> None:
        """Parse a stream chain like: |a| -> |b| ~> |c| -!-> "error" """
        lhs = self._parse_chain_element()

        while self._check(*_STREAM_OP_KINDS):
            op_tok = self._advance()
            rhs = self._parse_chain_element()

            edge = self._make_edge(op_tok, lhs, rhs)
            self._add_edge(edge)
            lhs = rhs

    def _parse_chain_element(self) -> AnyNode:
        tok = self._peek()

        match tok.kind:
            case TokenKind.GYGE:
                self._advance()
                return self._get_or_create_gyge(tok.value, tok.value2)
            case TokenKind.VOID:
                self._advance()
                return VoidNode()
            case TokenKind.STRING:
                self._advance()
                return LiteralNode(value=tok.value)
            case TokenKind.INTEGER:
                self._advance()
                return LiteralNode(value=int(tok.value))
            case TokenKind.FLOAT:
                self._advance()
                return LiteralNode(value=float(tok.value))
            case TokenKind.MOD_SEASON:
                self._advance()
                return ModifierNode(kind="season")
            case TokenKind.MOD_TEMP:
                self._advance()
                return ModifierNode(kind="temp")
            case TokenKind.MOD_TIME:
                self._advance()
                return ModifierNode(kind="time")
            case TokenKind.MOD_ENTROPY:
                self._advance()
                return ModifierNode(kind="entropy")
            case (
                TokenKind.TARGET_PID
                | TokenKind.TARGET_PORT
                | TokenKind.TARGET_NAME
                | TokenKind.TARGET_IP
                | TokenKind.TARGET_DIR
                | TokenKind.TARGET_BROADCAST
            ):
                return self._parse_target_or_modifier()
            case TokenKind.LBRACE:
                return self._parse_branch_block()
            case TokenKind.THIS_PROGRAM:
                self._advance()
                return GygeNode(name="<o>", hint="program")
            case TokenKind.STREAM_EXIT:
                # -!!-> 0  (exit code embedded in chain)
                self._advance()
                code_tok = self._peek()
                if code_tok.kind in (TokenKind.INTEGER, TokenKind.FLOAT):
                    self._advance()
                    return LiteralNode(value=int(code_tok.value))
                return LiteralNode(value=0)
            case _:
                raise ParseError(
                    f"Unexpected chain element: {tok.kind} ({tok.raw!r})",
                    tok.line,
                    tok.col,
                )

    def _parse_branch_block(self) -> BranchBlockNode:
        """Parse { |a| |b| |c| } branch list."""
        self._expect(TokenKind.LBRACE)
        branches: list[GygeNode] = []
        while not self._check(TokenKind.RBRACE, TokenKind.EOF):
            if self._check(TokenKind.GYGE):
                tok = self._advance()
                branches.append(self._get_or_create_gyge(tok.value, tok.value2))
            elif self._check(TokenKind.VOID):
                self._advance()  # discard branch (...)
            else:
                self._advance()  # skip unexpected
        self._expect(TokenKind.RBRACE)
        return BranchBlockNode(branches=branches)

    def _make_edge(self, op: Token, src: AnyNode, dst: AnyNode) -> StreamEdge:
        """Construct a StreamEdge from the operator token and source/dest nodes."""
        kind_map: dict[TokenKind, StreamKind] = {
            TokenKind.STREAM_BASIC: StreamKind.BASIC,
            TokenKind.STREAM_PRIORITY: StreamKind.PRIORITY,
            TokenKind.STREAM_LOSSY: StreamKind.LOSSY,
            TokenKind.STREAM_FILTER: StreamKind.FILTER,
            TokenKind.STREAM_FILTER_COND: StreamKind.FILTER_COND,
            TokenKind.STREAM_BLOCKED: StreamKind.BLOCKED,
            TokenKind.STREAM_THROTTLE: StreamKind.THROTTLE,
            TokenKind.STREAM_FAST: StreamKind.FAST,
            TokenKind.STREAM_SWITCH: StreamKind.SWITCH,
            TokenKind.STREAM_BATCHER: StreamKind.BATCHER,
            TokenKind.STREAM_SPLITTER: StreamKind.SPLITTER,
            TokenKind.STREAM_ARG_FILTER: StreamKind.ARG_FILTER,
            TokenKind.STREAM_ERROR: StreamKind.ERROR,
            TokenKind.STREAM_EXIT: StreamKind.EXIT,
            TokenKind.STREAM_CATCH: StreamKind.CATCH,
            TokenKind.STREAM_SIGNAL: StreamKind.SIGNAL,
            TokenKind.STREAM_RECEIVE: StreamKind.RECEIVE,
            TokenKind.STREAM_WAIT: StreamKind.WAIT,
            TokenKind.STREAM_PARASITE: StreamKind.PARASITE,
            TokenKind.STREAM_FEEDBACK: StreamKind.FEEDBACK,
        }
        kind = kind_map.get(op.kind, StreamKind.BASIC)
        return StreamEdge(
            kind=kind,
            source_id=src.node_id,
            dest_id=dst.node_id,
            condition=op.value,  # condition text for FILTER_COND, wait condition
            level=op.level,
            is_back_edge=(kind == StreamKind.FEEDBACK),
        )


def parse(source: str, filename: str = "<stdin>") -> ProgramASG:
    """Lex and parse *source*, returning a ProgramASG.

    Raises:
        LexError: on tokenisation failure.
        ParseError: on structural failure.
    """
    tokens = lex(source, filename)
    return _Parser(tokens).parse()
