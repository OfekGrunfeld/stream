"""Modifier engine — manages seasons, temperature, wind and their effects.

All math comes from modifiers.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from stream.runtime.types import Ch, Season

if TYPE_CHECKING:
    from stream.runtime.state import RuntimeState

__all__ = ["ModifierEngine", "SeasonConfig", "temperature_fx", "wind_beaufort"]


# ──────────────────────────────────────────────────────────────────────────────
# Season configuration (from modifiers.md)
# ──────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class SeasonConfig:
    attractor: float  # Ch level entropy drifts toward
    drift_rate: float  # Ch/tick toward attractor
    temp_baseline: float  # Flux baseline
    parasite_rate_mult: float  # multiplier on base parasite spawn rate
    wind_bonus: float  # added to wind formula


SEASON_CONFIGS: dict[Season, SeasonConfig] = {
    Season.SPRING: SeasonConfig(
        attractor=30.0,
        drift_rate=0.05,
        temp_baseline=35.0,
        parasite_rate_mult=1.20,
        wind_bonus=1.0,
    ),
    Season.SUMMER: SeasonConfig(
        attractor=50.0,
        drift_rate=0.08,
        temp_baseline=65.0,
        parasite_rate_mult=1.00,
        wind_bonus=0.5,
    ),
    Season.AUTUMN: SeasonConfig(
        attractor=35.0,
        drift_rate=0.06,
        temp_baseline=40.0,
        parasite_rate_mult=0.70,
        wind_bonus=2.0,
    ),
    Season.WINTER: SeasonConfig(
        attractor=15.0,
        drift_rate=0.10,
        temp_baseline=10.0,
        parasite_rate_mult=0.30,
        wind_bonus=-1.0,
    ),
}

# Season-transition entropy spikes: (from_season, to_season) → Ch spike
TRANSITION_SPIKES: dict[tuple[Season, Season], float] = {
    (Season.WINTER, Season.SPRING): 3.0,
    (Season.SPRING, Season.SUMMER): 5.0,
    (Season.SUMMER, Season.AUTUMN): -3.0,
    (Season.AUTUMN, Season.WINTER): -4.0,
    (Season.AUTUMN, Season.SPRING): -1.0,
    (Season.SUMMER, Season.SPRING): -1.0,
    (Season.SPRING, Season.AUTUMN): 0.0,
}


# ──────────────────────────────────────────────────────────────────────────────
# Derived formulas
# ──────────────────────────────────────────────────────────────────────────────

_SEASON_ORDER = [Season.SPRING, Season.SUMMER, Season.AUTUMN, Season.WINTER]


def temperature_fx(season: Season, stream_count: int, entropy: Ch) -> float:
    """Compute temperature in Flux.  Formula from modifiers.md:

        Temp = SeasonBaseline + (StreamLoad × 0.5) + (Entropy × 0.3)
    """
    cfg = SEASON_CONFIGS[season]
    stream_load = min(stream_count, 40)  # cap stream contribution
    return cfg.temp_baseline + (stream_load * 0.5) + (entropy * 0.3)


def wind_beaufort(entropy: Ch, season: Season) -> float:
    """Compute wind strength on Beaufort scale (0–10).

        Wind = (Entropy × 0.08) + SeasonBonus
    """
    cfg = SEASON_CONFIGS[season]
    raw = entropy * 0.08 + cfg.wind_bonus
    return max(0.0, min(10.0, raw))


def _next_season(current: Season) -> Season:
    idx = _SEASON_ORDER.index(current)
    return _SEASON_ORDER[(idx + 1) % 4]


# ──────────────────────────────────────────────────────────────────────────────
# ModifierEngine
# ──────────────────────────────────────────────────────────────────────────────


class ModifierEngine:
    """Manages season cycling, temperature, and wind.

    Called in Phase 1 of the tick loop.  Returns delta vectors rather than
    mutating state directly.
    """

    __slots__ = ()

    def tick(self, state: "RuntimeState") -> float:
        """Advance modifier state for one tick.

        Returns:
            entropy_delta: Ch contribution from modifier season attractor this tick.
        """
        # ── Season cycling ───────────────────────────────────────────────
        if state.season_lock is not None:
            state.season = state.season_lock
        else:
            state.season_tick_counter += 1
            if state.season_tick_counter >= state.season_duration:
                state.season_tick_counter = 0
                next_s = _next_season(state.season)
                spike = TRANSITION_SPIKES.get((state.season, next_s), 0.0)
                state.season = next_s
                state.entropy = max(0.0, state.entropy + spike)

        # ── Temperature ─────────────────────────────────────────────────
        state.temperature = temperature_fx(state.season, len(state.edges), state.entropy)

        # ── Wind ─────────────────────────────────────────────────────────
        if state.wind_enabled:
            state.wind_strength = wind_beaufort(state.entropy, state.season)
        else:
            state.wind_strength = 0.0

        # ── Season attractor nudge ────────────────────────────────────────
        cfg = SEASON_CONFIGS[state.season]
        diff = cfg.attractor - state.entropy
        return diff * cfg.drift_rate  # positive = pull up, negative = pull down

    def transition_spike(self, from_season: Season, to_season: Season) -> float:
        return TRANSITION_SPIKES.get((from_season, to_season), 0.0)

    @staticmethod
    def stream_throughput_multiplier(temperature: float) -> float:
        """0.0–1.0 multiplier on stream throughput based on temperature."""
        if temperature < 20.0:
            return 0.70  # cold: -30%
        if temperature > 76.0:
            return 1.10  # scorching: streams run hot
        return 1.00  # warm: baseline

    @staticmethod
    def lossy_rate_multiplier(temperature: float) -> float:
        """Multiplier on ~> loss rate based on temperature."""
        if temperature < 20.0:
            return 0.5  # cold preserves data
        if temperature > 76.0:
            return 3.0  # scorching: 3× loss
        if temperature > 51.0:
            return 1.5  # hot: 1.5× loss
        return 1.0
