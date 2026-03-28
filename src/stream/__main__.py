"""CLI entry point for the Stream esoteric language interpreter.

Commands:
    stream run <file> [options]     — execute a .stm program
    stream obfuscate <file>         — convert to obfuscated form (coming Phase 8)
    stream deobfuscate <file>       — convert back to readable form
    stream lex <file>               — dump token list (debug)
    stream parse <file>             — dump ASG summary (debug)
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

app = typer.Typer(
    name="stream",
    help="Stream esoteric language interpreter",
    add_completion=False,
    no_args_is_help=True,
)

_console = Console()
_err_console = Console(stderr=True)


# ──────────────────────────────────────────────────────────────────────────────
# stream run
# ──────────────────────────────────────────────────────────────────────────────


@app.command("run")
def run_program(
    file: Annotated[Path, typer.Argument(help="Path to .stm source file")],
    entropy: Annotated[
        float, typer.Option("--entropy", "-e", help="Initial entropy (Ch)")
    ] = 15.0,
    entropy_cap: Annotated[
        float,
        typer.Option("--entropy-cap", help="Entropy cap (100 = Terminal Cascade enabled)"),
    ] = 85.0,
    tick_limit: Annotated[
        int, typer.Option("--tick-limit", "-t", help="Maximum tick count")
    ] = 100_000,
    seed: Annotated[
        int | None, typer.Option("--seed", "-s", help="RNG seed for reproducibility")
    ] = None,
    hud: Annotated[bool, typer.Option("--hud/--no-hud", help="Live HUD display")] = True,
    hud_interval: Annotated[
        int, typer.Option("--hud-interval", help="Render HUD every N ticks")
    ] = 1,
    disaster_freq: Annotated[
        float, typer.Option("--disaster-freq", help="Disaster frequency multiplier (0=none)")
    ] = 1.0,
    wind: Annotated[bool, typer.Option("--wind/--no-wind", help="Enable wind modifier")] = True,
) -> None:
    """Execute a Stream program."""
    if not file.exists():
        _err_console.print(f"[red]Error:[/red] file not found: {file}")
        raise typer.Exit(code=1)

    source = file.read_text(encoding="utf-8")

    from stream.graph import build
    from stream.lexer import LexError
    from stream.parser import ParseError, parse
    from stream.runtime.display import HUD
    from stream.runtime.loop import RuntimeLoop
    from stream.runtime.state import ProgramConfig

    # ── Lex + Parse ──────────────────────────────────────────────────────────
    try:
        asg = parse(source, filename=str(file))
    except LexError as exc:
        _err_console.print(f"[red]Lex error:[/red] {exc}")
        raise typer.Exit(code=2) from exc
    except ParseError as exc:
        _err_console.print(f"[red]Parse error:[/red] {exc}")
        raise typer.Exit(code=2) from exc

    # ── Build graph ───────────────────────────────────────────────────────────
    cfg = ProgramConfig(
        entropy_initial=entropy,
        entropy_cap=entropy_cap,
        tick_limit=tick_limit,
        seed=seed,
        disaster_freq=disaster_freq,
        wind_enabled=wind,
    )
    state = build(asg, cfg)

    # ── Run ───────────────────────────────────────────────────────────────────
    loop = RuntimeLoop()

    with HUD(state, enabled=hud, tick_interval=hud_interval, console=_console) as display:
        # Patch loop to call display after each tick

        def run_with_hud(s):  # type: ignore[no-untyped-def]

            tick_limit_inner = s.config.tick_limit
            quiescent_count = 0

            while s.tick < tick_limit_inner:
                for phase in loop._phases:
                    phase.execute(s)
                    if s.terminated:
                        from stream.runtime.loop import TerminationReason
                        display.render_final(TerminationReason.EXIT_STREAM)
                        return TerminationReason.EXIT_STREAM

                s.tick += 1
                display.maybe_render()

                if s.entropy >= 100.0 and s.entropy_cap >= 100.0:
                    from stream.runtime.loop import TerminationReason, _apply_terminal_cascade
                    _apply_terminal_cascade(s)
                    display.render_final(TerminationReason.TERMINAL_CASCADE)
                    return TerminationReason.TERMINAL_CASCADE

                from stream.runtime.loop import TerminationReason, _is_quiescent
                if _is_quiescent(s):
                    quiescent_count += 1
                    if quiescent_count >= loop._max_quiescent:
                        display.render_final(TerminationReason.NATURAL_DRAIN)
                        return TerminationReason.NATURAL_DRAIN
                else:
                    quiescent_count = 0

            from stream.runtime.loop import TerminationReason
            display.render_final(TerminationReason.TICK_LIMIT)
            return TerminationReason.TICK_LIMIT

        run_with_hud(state)

    raise typer.Exit(code=state.exit_code if state.exit_code is not None else 0)


# ──────────────────────────────────────────────────────────────────────────────
# stream lex  (debug)
# ──────────────────────────────────────────────────────────────────────────────


@app.command("lex")
def lex_file(
    file: Annotated[Path, typer.Argument(help="Path to .stm source file")],
) -> None:
    """Dump the token list for a source file (debug)."""
    if not file.exists():
        _err_console.print(f"[red]Error:[/red] file not found: {file}")
        raise typer.Exit(code=1)

    from stream.lexer import LexError, lex

    try:
        tokens = lex(file.read_text(encoding="utf-8"), filename=str(file))
    except LexError as exc:
        _err_console.print(f"[red]Lex error:[/red] {exc}")
        raise typer.Exit(code=2) from exc

    from rich.table import Table

    tbl = Table(title=f"Tokens — {file.name}", show_header=True)
    tbl.add_column("Line", justify="right")
    tbl.add_column("Col", justify="right")
    tbl.add_column("Kind")
    tbl.add_column("Raw")
    tbl.add_column("Value")

    for tok in tokens:
        tbl.add_row(
            str(tok.line),
            str(tok.col),
            tok.kind.value,
            repr(tok.raw),
            repr(tok.value) if tok.value is not None else "",
        )

    _console.print(tbl)


# ──────────────────────────────────────────────────────────────────────────────
# stream parse  (debug)
# ──────────────────────────────────────────────────────────────────────────────


@app.command("parse")
def parse_file(
    file: Annotated[Path, typer.Argument(help="Path to .stm source file")],
) -> None:
    """Dump the ASG summary for a source file (debug)."""
    if not file.exists():
        _err_console.print(f"[red]Error:[/red] file not found: {file}")
        raise typer.Exit(code=1)

    from stream.lexer import LexError
    from stream.parser import ParseError, parse

    try:
        asg = parse(file.read_text(encoding="utf-8"), filename=str(file))
    except (LexError, ParseError) as exc:
        _err_console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=2) from exc

    _console.print(f"[bold]Nodes[/bold] ({len(asg.nodes)}):")
    for name, node in asg.nodes.items():
        _console.print(f"  {name}: {node}")

    _console.print(f"\n[bold]Sections[/bold] ({len(asg.sections)}):")
    for sec in asg.sections:
        _console.print(f"  ::{sec.name}::  ({len(sec.stmts)} stmts)")

    _console.print(f"\n[bold]Edges[/bold] ({len(asg.all_edges)}):")
    for edge in asg.all_edges[:30]:
        _console.print(f"  {edge.source_id} --[{edge.kind}]--> {edge.dest_id}")
    if len(asg.all_edges) > 30:
        _console.print(f"  …+{len(asg.all_edges) - 30} more")


# ──────────────────────────────────────────────────────────────────────────────
# stream obfuscate / deobfuscate  (Phase 8 stubs)
# ──────────────────────────────────────────────────────────────────────────────


@app.command("obfuscate")
def obfuscate_file(
    file: Annotated[Path, typer.Argument(help="Path to .stm source file")],
    level: Annotated[int, typer.Option("--level", "-l", help="Obfuscation level (1-10)")] = 5,
    output: Annotated[
        Path | None, typer.Option("--output", "-o", help="Output path")
    ] = None,
) -> None:
    """Obfuscate a Stream source file."""
    try:
        from stream.obfuscator import obfuscate
    except ImportError:
        _err_console.print("[yellow]Obfuscator not yet implemented (Phase 8).[/yellow]")
        raise typer.Exit(code=3) from None

    if not file.exists():
        _err_console.print(f"[red]Error:[/red] file not found: {file}")
        raise typer.Exit(code=1)

    result = obfuscate(file.read_text(encoding="utf-8"), level=level)
    out_path = output or file.with_suffix(".obf.stm")
    out_path.write_text(result.source, encoding="utf-8")
    _console.print(f"[green]Obfuscated:[/green] {out_path}")


@app.command("deobfuscate")
def deobfuscate_file(
    file: Annotated[Path, typer.Argument(help="Path to obfuscated .stm file")],
    output: Annotated[
        Path | None, typer.Option("--output", "-o", help="Output path")
    ] = None,
) -> None:
    """Deobfuscate a Stream source file."""
    try:
        from stream.obfuscator import deobfuscate
    except ImportError:
        _err_console.print("[yellow]Obfuscator not yet implemented (Phase 8).[/yellow]")
        raise typer.Exit(code=3) from None

    if not file.exists():
        _err_console.print(f"[red]Error:[/red] file not found: {file}")
        raise typer.Exit(code=1)

    result = deobfuscate(file.read_text(encoding="utf-8"))
    out_path = output or file.with_suffix(".readable.stm")
    out_path.write_text(result, encoding="utf-8")
    _console.print(f"[green]Deobfuscated:[/green] {out_path}")


# ──────────────────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────────────────


def main() -> None:
    app()


if __name__ == "__main__":
    main()
