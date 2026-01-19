from collections.abc import Callable
from typing import Any

from sti.imports.resolve import resolve_import
from sti.meta.program import Program
from stream.builtins.functions import SPRING_END_RE, SPRING_START_RE
from stream.builtins.keywords import GYGE_DECL_RE, INLINE_COMMENT
from stream.builtins.operators import ASSIGN_RE
from stream.program.poc import PIPELINE_RE


def parse_program(text: str) -> Program:
    season: str | None = None
    drift: str | None = None
    gyges: dict[str, Callable[[Any], Any]] = {}
    spring_pipeline: tuple[str, str] | None = None

    lines = text.splitlines()
    i = 0

    def is_inline_comment(line: str) -> bool:
        return INLINE_COMMENT.match(line.strip()) is not None

    while i < len(lines):
        raw = lines[i]
        line = raw.strip()

        i += 1

        if not line or is_inline_comment(line):
            continue

        # gyge declaration
        m = GYGE_DECL_RE.match(raw)
        if m:
            name = m.group(1)
            import_spec = m.group(2).strip()
            target = resolve_import(import_spec)
            if not callable(target):
                raise ValueError(
                    f"Imported target for gyge {name!r} is not callable: {import_spec!r}"
                )
            gyges[name] = target
            continue

        # season/drift assignments
        m = ASSIGN_RE.match(raw)
        if m:
            key, val = m.group(1), m.group(2)
            if key == "season":
                season = val
            else:
                drift = val
            continue

        # spring block
        if SPRING_START_RE.match(raw):
            # collect until }
            block: list[str] = []
            while i < len(lines) and not SPRING_END_RE.match(lines[i]):
                block_line = lines[i].strip()
                i += 1
                if not block_line or is_inline_comment(block_line):
                    continue
                block.append(block_line)

            if i >= len(lines) or not SPRING_END_RE.match(lines[i]):
                raise ValueError("spring block missing closing '}'")
            i += 1  # consume }

            # v0: allow exactly one pipeline line in spring
            if len(block) != 1:
                raise ValueError(
                    f"v0 supports exactly one line in spring block, got {len(block)} lines"
                )

            pm = PIPELINE_RE.match(block[0])
            if not pm:
                raise ValueError(f"Unsupported spring pipeline syntax: {block[0]!r}")

            literal = pm.group(1)
            gyge_name = pm.group(2)
            spring_pipeline = (literal, gyge_name)
            continue

        raise ValueError(f"Unrecognized statement: {raw!r}")

    if spring_pipeline is None:
        raise ValueError("No spring block found")

    return Program(season=season, drift=drift, gyges=gyges, spring_pipeline=spring_pipeline)
