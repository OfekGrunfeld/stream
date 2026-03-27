"""HUD display for Stream runtime — renders a Rich live panel each tick.

Responsibilities:
- Render global entropy meter with colour-coded tier
- Show active season / temperature / wind
- List active nodes (name, shape, activation_state)
- List active edges (kind, state, buffer depth)
- Show last N entropy events
- Show termination reason on exit

Usage::
    with HUD(state, enabled=True) as hud:
        reason = loop.run(state)
        hud.render_final(reason)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from stream.runtime.types import ActivationState, EdgeState, EntropyTier, entropy_tier

if TYPE_CHECKING:
    from stream.runtime.loop import TerminationReason
    from stream.runtime.state import RuntimeState

__all__ = ["HUD", "render_tick"]

# ──────────────────────────────────────────────────────────────────────────────
# Colour maps
# ──────────────────────────────────────────────────────────────────────────────

_TIER_COLOUR: dict[EntropyTier, str] = {
    EntropyTier.DORMANT: "bright_blue",
    EntropyTier.CALM: "green",
    EntropyTier.STIRRING: "yellow",
    EntropyTier.TURBULENT: "dark_orange",
    EntropyTier.VOLATILE: "bright_red",
    EntropyTier.CHAOTIC: "red1",
    EntropyTier.APOCALYPTIC: "bold red",
}

_EDGE_STATE_COLOUR: dict[EdgeState, str] = {
    EdgeState.ACTIVE: "green",
    EdgeState.BLOCKED: "yellow",
    EdgeState.DISRUPTED: "red",
    EdgeState.INFECTED: "magenta",
    EdgeState.DRAINED: "dim",
}

_ACTIVATION_COLOUR: dict[ActivationState, str] = {
    ActivationState.IDLE: "dim",
    ActivationState.PENDING: "yellow",
    ActivationState.RUNNING: "green",
    ActivationState.DRAINED: "red",
}


# ──────────────────────────────────────────────────────────────────────────────
# Stateless render helpers
# ──────────────────────────────────────────────────────────────────────────────


def _entropy_bar(entropy: float, width: int = 30) -> Text:
    tier = entropy_tier(entropy)
    colour = _TIER_COLOUR[tier]
    filled = int(round(entropy / 100.0 * width))
    bar = "█" * filled + "░" * (width - filled)
    t = Text()
    t.append(f"[{entropy:5.1f} Ch] ", style="bold")
    t.append(bar, style=colour)
    t.append(f"  {tier.upper()}", style=colour)
    return t


def _modifier_line(state: "RuntimeState") -> str:
    season_str = state.season.value.capitalize()
    season_lock = f" [locked]" if state.season_lock else ""
    return (
        f"Season: {season_str}{season_lock}  "
        f"Temp: {state.temperature:4.1f} Fx  "
        f"Wind: {state.wind_strength:4.1f} Bft"
    )


def _node_table(state: "RuntimeState") -> Table:
    tbl = Table(title="Nodes", show_header=True, header_style="bold cyan", expand=False)
    tbl.add_column("Name", style="cyan", no_wrap=True)
    tbl.add_column("Shape", style="white")
    tbl.add_column("State")
    tbl.add_column("In", justify="right")
    tbl.add_column("Out", justify="right")

    for gir in list(state.nodes.values())[:20]:  # cap at 20 for readability
        act_col = _ACTIVATION_COLOUR.get(gir.activation_state, "white")
        in_count = sum(len(q) for q in gir.input_ports.values())
        out_count = sum(len(q) for q in gir.output_ports.values())
        tbl.add_row(
            gir.name or gir.node_id[:8],
            gir.shape.value,
            Text(gir.activation_state.value, style=act_col),
            str(in_count),
            str(out_count),
        )
    if len(state.nodes) > 20:
        tbl.add_row(f"…+{len(state.nodes) - 20} more", "", "", "", "")
    return tbl


def _edge_table(state: "RuntimeState") -> Table:
    tbl = Table(title="Edges", show_header=True, header_style="bold magenta", expand=False)
    tbl.add_column("Kind", style="magenta", no_wrap=True)
    tbl.add_column("State")
    tbl.add_column("Buf", justify="right")
    tbl.add_column("Back", justify="center")

    for scd in list(state.edges.values())[:20]:
        st_col = _EDGE_STATE_COLOUR.get(scd.state, "white")
        tbl.add_row(
            scd.stream_kind.value,
            Text(scd.state.value, style=st_col),
            str(len(scd.buffer)),
            "↩" if scd.is_back_edge else "",
        )
    if len(state.edges) > 20:
        tbl.add_row(f"…+{len(state.edges) - 20} more", "", "", "")
    return tbl


def render_tick(state: "RuntimeState", console: Console | None = None) -> None:
    """Render a single tick snapshot to the console (non-live mode)."""
    con = console or Console()

    tier = entropy_tier(state.entropy)
    colour = _TIER_COLOUR[tier]

    lines: list[Text | Table | str] = [
        Text(f"Tick #{state.tick}", style="bold white"),
        _entropy_bar(state.entropy),
        Text(_modifier_line(state), style="dim"),
        _node_table(state),
        _edge_table(state),
    ]

    for item in lines:
        if isinstance(item, Table):
            con.print(item)
        elif isinstance(item, Text):
            con.print(item)
        else:
            con.print(item)


# ──────────────────────────────────────────────────────────────────────────────
# HUD context manager  (used when --hud flag is passed)
# ──────────────────────────────────────────────────────────────────────────────


class HUD:
    """Context manager that prints a tick-by-tick HUD to the terminal.

    When ``enabled=False`` the HUD is a no-op (used when --no-hud flag set).
    The RuntimeLoop calls ``state.hud_lines`` — this class reads those and
    combines with live state.
    """

    __slots__ = ("_state", "_console", "_enabled", "_tick_interval")

    def __init__(
        self,
        state: "RuntimeState",
        *,
        enabled: bool = True,
        tick_interval: int = 1,
        console: Console | None = None,
    ) -> None:
        self._state = state
        self._enabled = enabled
        self._tick_interval = tick_interval
        self._console = console or Console()

    def __enter__(self) -> "HUD":
        return self

    def __exit__(self, *_: object) -> None:
        pass

    def maybe_render(self) -> None:
        """Call this after each tick — renders if enabled and tick % interval == 0."""
        if not self._enabled:
            return
        if self._state.tick % self._tick_interval != 0:
            return
        render_tick(self._state, self._console)
        # Flush any HUD lines the loop stashed
        for line in self._state.hud_lines:
            self._console.print(line)
        self._state.hud_lines.clear()

    def render_final(self, reason: "TerminationReason") -> None:
        """Print termination summary."""
        if not self._enabled:
            return
        from stream.runtime.loop import TerminationReason

        style_map = {
            TerminationReason.NATURAL_DRAIN: "bold green",
            TerminationReason.EXIT_STREAM: "bold yellow",
            TerminationReason.TICK_LIMIT: "bold orange3",
            TerminationReason.TERMINAL_CASCADE: "bold red",
        }
        colour = style_map.get(reason, "white")
        self._console.print(
            Panel(
                Text(
                    f"Program terminated: {reason.value.upper()}\n"
                    f"Exit code: {self._state.exit_code}  "
                    f"Ticks: {self._state.tick}  "
                    f"Final entropy: {self._state.entropy:.1f} Ch",
                    style=colour,
                ),
                title="[bold]Stream Runtime[/bold]",
                border_style=colour,
            )
        )
