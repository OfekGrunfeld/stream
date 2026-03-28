"""Core runtime type definitions: GIR, SCD, Packet, EdgeState, GygShape, etc.

All value objects are frozen dataclasses or StrEnum.  No mutable module-level state.
"""

from __future__ import annotations

import uuid
from collections import deque
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

__all__ = [
    "NodeId",
    "EdgeId",
    "Ch",
    "GygShape",
    "EdgeState",
    "ActivationState",
    "Packet",
    "GyrValue",
    "GIR",
    "SCD",
    "TypeRegistry",
]

# ──────────────────────────────────────────────────────────────────────────────
# Type aliases  (Python 3.12 `type` statement)
# ──────────────────────────────────────────────────────────────────────────────

type NodeId = str
type EdgeId = str
type Ch = float  # entropy in Churn units


def _nid() -> NodeId:
    return str(uuid.uuid4())


def _eid() -> EdgeId:
    return str(uuid.uuid4())


# ──────────────────────────────────────────────────────────────────────────────
# Enumerations
# ──────────────────────────────────────────────────────────────────────────────


class GygShape(StrEnum):
    VOID = "void"
    VARIABLE = "variable"
    FUNCTION = "function"
    CLASS = "class"
    PROGRAM = "program"
    MOCK = "mock"
    BYTES = "bytes"
    GARBAGE = "garbage"


class EdgeState(StrEnum):
    ACTIVE = "active"
    BLOCKED = "blocked"
    DISRUPTED = "disrupted"
    INFECTED = "infected"
    DRAINED = "drained"


class ActivationState(StrEnum):
    IDLE = "idle"
    PENDING = "pending"
    RUNNING = "running"
    DRAINED = "drained"


class Season(StrEnum):
    SPRING = "spring"
    SUMMER = "summer"
    AUTUMN = "autumn"
    WINTER = "winter"


class EntropyTier(StrEnum):
    DORMANT = "dormant"  # 0–9.9
    CALM = "calm"  # 10–24.9
    STIRRING = "stirring"  # 25–39.9
    TURBULENT = "turbulent"  # 40–59.9
    VOLATILE = "volatile"  # 60–74.9
    CHAOTIC = "chaotic"  # 75–89.9
    APOCALYPTIC = "apocalyptic"  # 90–100


class DisasterKind(StrEnum):
    ROCKSLIDE = "rockslide"
    FLOOD = "flood"
    DROUGHT = "drought"
    LIGHTNING = "lightning"
    PARASITE_BLOOM = "parasite_bloom"
    GLACIER = "glacier"


class StreamKind(StrEnum):
    BASIC = "basic"
    PRIORITY = "priority"
    LOSSY = "lossy"
    FILTER = "filter"
    FILTER_COND = "filter_cond"
    BLOCKED = "blocked"
    THROTTLE = "throttle"
    FAST = "fast"
    SWITCH = "switch"
    BATCHER = "batcher"
    SPLITTER = "splitter"
    ARG_FILTER = "arg_filter"
    ERROR = "error"
    EXIT = "exit"
    CATCH = "catch"
    SIGNAL = "signal"
    RECEIVE = "receive"
    WAIT = "wait"
    PARASITE = "parasite"
    FEEDBACK = "feedback"


# ──────────────────────────────────────────────────────────────────────────────
# Packet — data in flight on a stream edge
# ──────────────────────────────────────────────────────────────────────────────

# GyrValue is the set of all possible gyge runtime values
GyrValue = int | float | str | bytes | dict[str, Any] | list[Any] | None | object


@dataclass(slots=True)
class Packet:
    """A unit of data travelling on a stream edge."""

    value: GyrValue
    origin_id: NodeId = ""  # node that produced this packet
    tick_born: int = 0  # tick when this packet was produced
    corrupted: bool = False  # True if packet has been garbage-corrupted


# ──────────────────────────────────────────────────────────────────────────────
# GIR — Gyge Instance Record  (runtime node)
# ──────────────────────────────────────────────────────────────────────────────


@dataclass(slots=True)
class GIR:
    """Runtime representation of one gyge node."""

    node_id: NodeId = field(default_factory=_nid)
    name: str = ""
    shape: GygShape = GygShape.VOID
    hint: str = ""  # optional type hint from source

    # Port maps: channel buffers keyed by port name
    input_ports: dict[str, deque[Packet]] = field(default_factory=dict)
    output_ports: dict[str, deque[Packet]] = field(default_factory=dict)

    activation_state: ActivationState = ActivationState.IDLE
    local_entropy: Ch = 0.0  # per-node entropy modifier (−0.2 to +0.2)
    parasite_vulnerability: float = 0.0  # 0.0–1.0

    # Stored value (for VARIABLE shape)
    stored_value: GyrValue = None

    # Callable body (for FUNCTION shape)
    fn_body: object = None  # Callable[[GyrValue], GyrValue] | None

    def default_input(self) -> deque[Packet]:
        if "default" not in self.input_ports:
            self.input_ports["default"] = deque()
        return self.input_ports["default"]

    def default_output(self) -> deque[Packet]:
        if "default" not in self.output_ports:
            self.output_ports["default"] = deque()
        return self.output_ports["default"]

    def has_input(self) -> bool:
        return any(len(q) > 0 for q in self.input_ports.values())

    def has_output(self) -> bool:
        return any(len(q) > 0 for q in self.output_ports.values())


# ──────────────────────────────────────────────────────────────────────────────
# SCD — Stream Channel Descriptor  (runtime edge)
# ──────────────────────────────────────────────────────────────────────────────


@dataclass(slots=True)
class SCD:
    """Runtime representation of one typed stream edge."""

    edge_id: EdgeId = field(default_factory=_eid)
    stream_kind: StreamKind = StreamKind.BASIC

    source_id: NodeId = ""
    source_port: str = "default"
    dest_id: NodeId = ""
    dest_port: str = "default"

    # Edge buffer
    buffer: deque[Packet] = field(default_factory=deque)

    state: EdgeState = EdgeState.ACTIVE
    local_entropy: Ch = 0.0  # ±0.2 deviation from global entropy

    # Operator parameters
    condition: str = ""  # filter/switch condition expression
    level: int = 0  # throttle '+' count / fast '>' count / wait ',' stages
    is_back_edge: bool = False  # feedback loop edge

    # Token bucket for throttle edges
    token_bucket: float = 10.0
    token_bucket_capacity: float = 10.0
    token_refill_rate: float = 1.0

    # Disruption tracking
    disruption_ticks_remaining: int = 0

    # Error stream state
    error_payload: Packet | None = None


# ──────────────────────────────────────────────────────────────────────────────
# Type Registry
# ──────────────────────────────────────────────────────────────────────────────


class TypeRegistry:
    """Maps node IDs to their resolved GygShape.

    Mutable (parasites can reclassify nodes). Historical record kept for
    entropy-engine computation of how much chaos a node has experienced.
    """

    __slots__ = ("_current", "_history")

    def __init__(self) -> None:
        self._current: dict[NodeId, GygShape] = {}
        self._history: dict[NodeId, list[GygShape]] = {}

    def register(self, node_id: NodeId, shape: GygShape) -> None:
        if node_id in self._current:
            self._history.setdefault(node_id, []).append(self._current[node_id])
        self._current[node_id] = shape

    def get(self, node_id: NodeId) -> GygShape:
        return self._current.get(node_id, GygShape.VOID)

    def reclassify(self, node_id: NodeId, new_shape: GygShape) -> None:
        """Parasite-driven shape change."""
        self.register(node_id, new_shape)

    def change_count(self, node_id: NodeId) -> int:
        return len(self._history.get(node_id, []))

    def __len__(self) -> int:
        return len(self._current)


def entropy_tier(ch: Ch) -> EntropyTier:
    """Return the EntropyTier for a given Ch value."""
    if ch < 10.0:
        return EntropyTier.DORMANT
    if ch < 25.0:
        return EntropyTier.CALM
    if ch < 40.0:
        return EntropyTier.STIRRING
    if ch < 60.0:
        return EntropyTier.TURBULENT
    if ch < 75.0:
        return EntropyTier.VOLATILE
    if ch < 90.0:
        return EntropyTier.CHAOTIC
    return EntropyTier.APOCALYPTIC
