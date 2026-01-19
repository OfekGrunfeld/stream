import sys
from pathlib import Path

from sti.meta.program import Program
from sti.parse.program import parse_program


def run(prog: Program) -> None:
    literal, gyge_name = prog.spring_pipeline

    if gyge_name not in prog.gyges:
        raise ValueError(f"Unknown gyge used in spring: {gyge_name!r}")

    sink = prog.gyges[gyge_name]

    # For now: pipeline is just literal -> sink
    sink(literal)


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: uv run python -m sti <file.st>", file=sys.stderr)
        raise SystemExit(2)

    path = Path(sys.argv[1])
    text = path.read_text(encoding="utf-8", errors="replace")

    prog = parse_program(text)
    run(prog)


if __name__ == "__main__":
    main()
