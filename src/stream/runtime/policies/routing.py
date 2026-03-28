"""Routing policies: filter, switch, batcher, splitter, arg-filter."""

from __future__ import annotations

import random

from stream.runtime.policies.base import POLICY_REGISTRY
from stream.runtime.types import SCD, Ch, Packet, StreamKind

__all__ = [
    "FilterPolicy",
    "FilterCondPolicy",
    "SwitchPolicy",
    "BatcherPolicy",
    "SplitterPolicy",
    "ArgFilterPolicy",
]

_rng = random.Random()


def _rand() -> float:
    return _rng.random()


def _eval_condition(condition: str, packet: Packet, entropy: Ch) -> bool:
    """Evaluate a simple stream condition expression.

    Supports: len > N, $entropy > N, $S == season, numeric comparisons.
    Falls back to True on parse failure (permissive default).
    """
    if not condition:
        return True

    cond = condition.strip()

    # $entropy comparisons
    if "$entropy" in cond:
        try:
            parts = cond.replace("$entropy", str(entropy)).split()
            if len(parts) == 3:
                lhs, op, rhs = float(parts[0]), parts[1], float(parts[2])
                return _compare(lhs, op, rhs)
        except (ValueError, IndexError):
            pass
        return True

    # len > N  (packet value length)
    if cond.startswith("len"):
        try:
            val = packet.value
            length = len(val) if hasattr(val, "__len__") else (1 if val is not None else 0)
            parts = cond.split()
            if len(parts) == 3:
                _, op, threshold = parts[0], parts[1], float(parts[2])
                return _compare(float(length), op, threshold)
        except (ValueError, IndexError):
            pass
        return True

    # Boolean-ish
    if cond in ("true", "1"):
        return True
    if cond in ("false", "0"):
        return False

    # Default: pass
    return True


def _compare(lhs: float, op: str, rhs: float) -> bool:
    match op:
        case ">":
            return lhs > rhs
        case ">=":
            return lhs >= rhs
        case "<":
            return lhs < rhs
        case "<=":
            return lhs <= rhs
        case "==" | "=":
            return lhs == rhs
        case "!=" | "<>":
            return lhs != rhs
        case _:
            return True


# ──────────────────────────────────────────────────────────────────────────────
# -/> Filter (always-pass / identity filter)
# ──────────────────────────────────────────────────────────────────────────────


class FilterPolicy:
    """-/> Unconditional filter (identity — always passes).

    Drops items at high entropy (30% misfire at Extreme).
    """

    __slots__ = ()

    def should_deliver(self, packet: Packet, scd: SCD, entropy: Ch) -> bool:
        if entropy >= 80.0:
            if _rand() < 0.30:
                return False  # extreme misfire
        elif entropy >= 60.0:
            if _rand() < 0.15:
                return False
        elif entropy >= 25.0:
            if _rand() < 0.05:
                return False
        return True

    def transform(self, packet: Packet, scd: SCD, entropy: Ch) -> Packet:
        return packet

    def on_blocked(self, scd: SCD, entropy: Ch) -> float:
        return -0.05  # filter handling load drains entropy slightly


# ──────────────────────────────────────────────────────────────────────────────
# -/|cond|\-> Conditional filter / switch
# ──────────────────────────────────────────────────────────────────────────────


class FilterCondPolicy:
    """-/|condition|\\-> Conditional filter.

    Items satisfying condition → first branch (dest_id).
    Items not satisfying → second branch (if configured).
    At Extreme entropy: filter may invert for whole ticks.
    """

    __slots__ = ()

    def should_deliver(self, packet: Packet, scd: SCD, entropy: Ch) -> bool:
        if entropy >= 80.0 and _rand() < 0.30:
            # May invert completely
            return not _eval_condition(scd.condition, packet, entropy)
        return _eval_condition(scd.condition, packet, entropy)

    def transform(self, packet: Packet, scd: SCD, entropy: Ch) -> Packet:
        return packet

    def on_blocked(self, scd: SCD, entropy: Ch) -> float:
        return -0.05


# ──────────────────────────────────────────────────────────────────────────────
# -/|\-> Switch (no condition, multi-branch routing)
# ──────────────────────────────────────────────────────────────────────────────


class SwitchPolicy:
    """-/|\\-> Switch stream.

    Routes to branches based on condition if present, else distributes.
    At Extreme: may lock to one branch for 5–10 ticks.
    """

    __slots__ = ("_locked_branch", "_lock_remaining")

    def __init__(self) -> None:
        self._locked_branch: int = 0
        self._lock_remaining: int = 0

    def should_deliver(self, packet: Packet, scd: SCD, entropy: Ch) -> bool:
        if entropy >= 80.0:
            if self._lock_remaining > 0:
                self._lock_remaining -= 1
                return True  # locked to delivering
            if _rand() < 0.25:
                self._lock_remaining = _rng.randint(5, 10)
                return True
        return True

    def transform(self, packet: Packet, scd: SCD, entropy: Ch) -> Packet:
        return packet

    def on_blocked(self, scd: SCD, entropy: Ch) -> float:
        return 0.0


# ──────────────────────────────────────────────────────────────────────────────
# -#-> Batcher
# ──────────────────────────────────────────────────────────────────────────────


class BatcherPolicy:
    """-#-> Batcher — accumulates into batches before forwarding.

    Uses SCD.level as the approximate batch size.  Releases on size or timeout.
    At Extreme entropy: batch boundaries collapse.
    """

    __slots__ = ()

    DEFAULT_BATCH_SIZE = 10

    def should_deliver(self, packet: Packet, scd: SCD, entropy: Ch) -> bool:
        if entropy >= 80.0:
            return True  # batch boundaries collapse

        batch_size = max(1, scd.level or self.DEFAULT_BATCH_SIZE)

        # Entropy variance on batch size
        if entropy >= 60.0:
            variance = int(batch_size * 0.20)
            batch_size = max(1, batch_size + _rng.randint(-variance, variance))
        elif entropy >= 25.0:
            if _rand() < 0.05:
                batch_size = max(1, batch_size + _rng.choice([-1, 1]))

        return len(scd.buffer) >= batch_size

    def transform(self, packet: Packet, scd: SCD, entropy: Ch) -> Packet:
        return packet

    def on_blocked(self, scd: SCD, entropy: Ch) -> float:
        return 0.0


# ──────────────────────────────────────────────────────────────────────────────
# -...-> Splitter (fan-out)
# ──────────────────────────────────────────────────────────────────────────────


class SplitterPolicy:
    """-...-> Splitter — fans data to N branches simultaneously.

    +0.08 Ch/tick per branch beyond first.
    Wind compounds imbalance.  At Extreme: some branches may starve.
    """

    __slots__ = ()

    def should_deliver(self, packet: Packet, scd: SCD, entropy: Ch) -> bool:
        if entropy >= 80.0 and _rand() < 0.20:
            # Some branches get nothing this tick
            return False
        return True

    def transform(self, packet: Packet, scd: SCD, entropy: Ch) -> Packet:
        return packet

    def on_blocked(self, scd: SCD, entropy: Ch) -> float:
        # +0.08 Ch/tick per branch (level = branch count)
        branches = max(1, scd.level)
        return 0.08 * max(0, branches - 1)


# ──────────────────────────────────────────────────────────────────────────────
# -|-> Argument filter (positional)
# ──────────────────────────────────────────────────────────────────────────────


class ArgFilterPolicy:
    """-|-> Argument filter — extracts a specific positional argument from a tuple stream.

    level = position to extract (0-indexed).
    """

    __slots__ = ()

    def should_deliver(self, packet: Packet, scd: SCD, entropy: Ch) -> bool:
        return True

    def transform(self, packet: Packet, scd: SCD, entropy: Ch) -> Packet:
        val = packet.value
        pos = scd.level

        # Entropy misread
        if entropy >= 80.0 and _rand() < 0.25:
            pos = _rng.randint(0, max(0, pos + 2))
        elif entropy >= 25.0 and _rand() < 0.03:
            pos = max(0, pos + _rng.choice([-1, 1]))

        if isinstance(val, (list, tuple)) and pos < len(val):
            extracted = val[pos]
        else:
            extracted = val

        return Packet(
            value=extracted,
            origin_id=packet.origin_id,
            tick_born=packet.tick_born,
            corrupted=packet.corrupted,
        )

    def on_blocked(self, scd: SCD, entropy: Ch) -> float:
        return 0.0


# ──────────────────────────────────────────────────────────────────────────────
# Registration
# ──────────────────────────────────────────────────────────────────────────────

POLICY_REGISTRY.register(StreamKind.FILTER, FilterPolicy())
POLICY_REGISTRY.register(StreamKind.FILTER_COND, FilterCondPolicy())
POLICY_REGISTRY.register(StreamKind.SWITCH, SwitchPolicy())
POLICY_REGISTRY.register(StreamKind.BATCHER, BatcherPolicy())
POLICY_REGISTRY.register(StreamKind.SPLITTER, SplitterPolicy())
POLICY_REGISTRY.register(StreamKind.ARG_FILTER, ArgFilterPolicy())
