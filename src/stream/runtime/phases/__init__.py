"""Tick phase implementations (one file per phase)."""

from stream.runtime.phases.phase0_entropy import Phase0Entropy
from stream.runtime.phases.phase1_modifiers import Phase1Modifiers
from stream.runtime.phases.phase2_parasites import Phase2Parasites
from stream.runtime.phases.phase3_delivery import Phase3Delivery
from stream.runtime.phases.phase4_activation import Phase4Activation
from stream.runtime.phases.phase5_events import Phase5Events
from stream.runtime.phases.phase6_signals import Phase6Signals
from stream.runtime.phases.phase7_wait import Phase7Wait
from stream.runtime.phases.phase8_mutation import Phase8Mutation
from stream.runtime.phases.phase9_gc import Phase9GC

__all__ = [
    "Phase0Entropy",
    "Phase1Modifiers",
    "Phase2Parasites",
    "Phase3Delivery",
    "Phase4Activation",
    "Phase5Events",
    "Phase6Signals",
    "Phase7Wait",
    "Phase8Mutation",
    "Phase9GC",
]
