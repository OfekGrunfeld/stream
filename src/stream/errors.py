"""Exception hierarchy for the Stream language."""

from __future__ import annotations

__all__ = [
    "StreamError",
    "LexError",
    "ParseError",
    "BuildError",
    "StreamRuntimeError",
    "EntropyError",
]


class StreamError(Exception):
    """Base exception for all Stream language errors."""


class LexError(StreamError):
    """Raised when the lexer encounters invalid syntax."""

    def __init__(self, message: str, line: int, col: int) -> None:
        super().__init__(f"{message} at line {line}, col {col}")
        self.line = line
        self.col = col


class ParseError(StreamError):
    """Raised when the parser encounters structurally invalid input."""

    def __init__(self, message: str, line: int = 0, col: int = 0) -> None:
        loc = f" at line {line}, col {col}" if line else ""
        super().__init__(f"{message}{loc}")
        self.line = line
        self.col = col


class BuildError(StreamError):
    """Raised during runtime graph construction from the ASG."""


class StreamRuntimeError(StreamError):
    """Raised during program execution (non-entropic failures)."""


class EntropyError(StreamError):
    """Raised on entropy catastrophe (Terminal Cascade at 100 Ch)."""

    def __init__(self, tick: int, entropy: float) -> None:
        super().__init__(
            f"Terminal Cascade at tick {tick}: entropy reached {entropy:.1f} Ch"
        )
        self.tick = tick
        self.entropy = entropy
