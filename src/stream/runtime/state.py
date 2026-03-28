"""RuntimeState — the single mutable object passed through all tick phases.

No global mutable variables.  Everything lives here.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from stream.runtime.types import (
    GIR,
    SCD,
    Ch,
    EdgeId,
    NodeId,
    Season,
    TypeRegistry,
)

if TYPE_CHECKING:
    from stream.runtime.entropy import EntropyEvent

__all__ = ["RuntimeState", "ProgramConfig"]


@dataclass(slots=True)
class ProgramConfig:
    """Tunable runtime parameters (SDK control surface from entropy.md)."""

    entropy_initial: Ch = 15.0
    entropy_cap: Ch = 85.0  # raise to 100.0 to enable Terminal Cascade
    entropy_decay_rate: float = 1.0  # multiplier on all sources
    entropy_sink_rate: float = 1.0  # multiplier on all sinks
    disaster_freq: float = 1.0  # 0.0 = no disasters
    parasite_rate: float = 1.0  # 0.0 = no modifier-created parasites
    wind_enabled: bool = True
    season_lock: Season | None = None  # None = natural cycling
    season_duration: int = 1000  # ticks per season
    tick_limit: int = 100_000  # safety cap for non-terminating programs
    seed: int | None = None  # PRNG seed (None = random); same seed = reproducible


@dataclass(slots=True)
class RuntimeState:
    """Complete mutable state of one running Stream program."""

    # Graph
    nodes: dict[NodeId, GIR] = field(default_factory=dict)
    edges: dict[EdgeId, SCD] = field(default_factory=dict)
    type_registry: TypeRegistry = field(default_factory=TypeRegistry)

    # Topology helpers
    node_out_edges: dict[NodeId, list[EdgeId]] = field(default_factory=dict)
    node_in_edges: dict[NodeId, list[EdgeId]] = field(default_factory=dict)
    topo_order: list[NodeId] = field(default_factory=list)

    # Entropy
    entropy: Ch = 15.0
    entropy_cap: Ch = 85.0
    entropy_floor: Ch = 5.0
    entropy_decay_rate: float = 1.0
    entropy_sink_rate: float = 1.0
    pending_entropy_events: list[EntropyEvent] = field(default_factory=list)

    # Modifiers
    season: Season = Season.WINTER
    season_tick_counter: int = 0
    season_duration: int = 1000
    season_lock: Season | None = None
    temperature: float = 10.0  # Flux (Fx)
    wind_strength: float = 0.0  # Beaufort 0–10
    wind_enabled: bool = True

    # Active disasters: disaster_kind → ticks_remaining (-1 = instantaneous/done)
    active_disasters: dict[str, int] = field(default_factory=dict)

    # Parasite tracking (simulated)
    active_parasites: list[object] = field(default_factory=list)

    # Error event queue
    error_queue: list[object] = field(default_factory=list)  # list[ErrorEvent]

    # Signal queue
    signal_queue: list[object] = field(default_factory=list)  # list[SignalEvent]

    # Pending graph mutations (applied at end of tick, Phase 8)
    mutation_queue: list[object] = field(default_factory=list)

    # Tick counter
    tick: int = 0

    # Termination
    exit_code: int | None = None  # set when -!!-> fires
    terminated: bool = False

    # PRNG (seeded for reproducibility)
    rng: random.Random = field(default_factory=random.Random)

    # Config
    config: ProgramConfig = field(default_factory=ProgramConfig)

    # HUD output lines (populated by display module each tick)
    hud_lines: list[str] = field(default_factory=list)

    def add_node(self, gir: GIR) -> None:
        self.nodes[gir.node_id] = gir
        if gir.node_id not in self.node_out_edges:
            self.node_out_edges[gir.node_id] = []
        if gir.node_id not in self.node_in_edges:
            self.node_in_edges[gir.node_id] = []

    def add_edge(self, scd: SCD) -> None:
        self.edges[scd.edge_id] = scd
        self.node_out_edges.setdefault(scd.source_id, []).append(scd.edge_id)
        self.node_in_edges.setdefault(scd.dest_id, []).append(scd.edge_id)

    def get_node(self, node_id: NodeId) -> GIR | None:
        return self.nodes.get(node_id)

    def get_edge(self, edge_id: EdgeId) -> SCD | None:
        return self.edges.get(edge_id)

    def out_edges(self, node_id: NodeId) -> list[SCD]:
        return [
            self.edges[eid]
            for eid in self.node_out_edges.get(node_id, [])
            if eid in self.edges
        ]

    def in_edges(self, node_id: NodeId) -> list[SCD]:
        return [
            self.edges[eid]
            for eid in self.node_in_edges.get(node_id, [])
            if eid in self.edges
        ]

    def effective_entropy(self, local_modifier: float = 0.0) -> Ch:
        """Clamp global + local entropy modifier to [0, 100]."""
        return max(0.0, min(100.0, self.entropy + local_modifier))

    def is_active(self) -> bool:
        return not self.terminated and self.exit_code is None
