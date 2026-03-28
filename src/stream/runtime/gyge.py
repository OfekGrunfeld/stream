"""Gyge resolver and built-in gyge function bindings.

The GyrResolver is called once per node on first activation (Phase 4).
Built-in functions (len, print, str, etc.) are registered here so that
gyges with those names automatically resolve as FUNCTION shape with
a Python callable body.
"""

from __future__ import annotations

from typing import Any

from stream.runtime.types import GygShape, NodeId, TypeRegistry

__all__ = ["GyrResolver", "BUILTIN_FUNCTIONS"]


# ──────────────────────────────────────────────────────────────────────────────
# Built-in function bindings
# ──────────────────────────────────────────────────────────────────────────────


def _builtin_len(val: Any) -> Any:
    try:
        return len(val)
    except TypeError:
        return 0


def _builtin_str(val: Any) -> str:
    return str(val)


def _builtin_int(val: Any) -> int:
    try:
        return int(val)
    except (TypeError, ValueError):
        return 0


def _builtin_float_(val: Any) -> float:
    try:
        return float(val)
    except (TypeError, ValueError):
        return 0.0


def _builtin_bytes(val: Any) -> bytes:
    if isinstance(val, bytes):
        return val
    try:
        return str(val).encode()
    except Exception:
        return b""


def _builtin_upper(val: Any) -> str:
    return str(val).upper()


def _builtin_lower(val: Any) -> str:
    return str(val).lower()


def _builtin_print(val: Any) -> Any:
    print(val)
    return val


BUILTIN_FUNCTIONS: dict[str, Any] = {
    "len": _builtin_len,
    "str": _builtin_str,
    "int": _builtin_int,
    "float": _builtin_float_,
    "bytes": _builtin_bytes,
    "upper": _builtin_upper,
    "lower": _builtin_lower,
    "print": _builtin_print,
    "log": _builtin_print,
    "output": _builtin_print,
}


# ──────────────────────────────────────────────────────────────────────────────
# GyrResolver
# ──────────────────────────────────────────────────────────────────────────────


class GyrResolver:
    """Resolves gyge shapes lazily on first activation.

    Uses the registry to detect if a gyge was previously seen (for
    re-use of known shapes) and registers the result.
    """

    __slots__ = ("_registry", "_builtins")

    def __init__(self, registry: TypeRegistry) -> None:
        self._registry = registry
        self._builtins = BUILTIN_FUNCTIONS

    def get_builtin(self, name: str) -> Any | None:
        return self._builtins.get(name)

    def is_builtin(self, name: str) -> bool:
        return name in self._builtins

    def resolve_from_name(self, name: str) -> GygShape | None:
        """Check if the name itself implies a shape."""
        if name in self._builtins:
            return GygShape.FUNCTION
        if name in ("<o>", "<o/>"):
            return GygShape.PROGRAM
        return None

    def record(self, node_id: NodeId, shape: GygShape) -> None:
        self._registry.register(node_id, shape)

    def previously_resolved(self, node_id: NodeId) -> GygShape | None:
        shape = self._registry.get(node_id)
        return shape if shape != GygShape.VOID else None
