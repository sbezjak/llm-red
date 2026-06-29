"""Fires one attack N times and computes its Attack Success Rate (ASR).

The target is non-deterministic, so a single pass/fail lies - an attack might
work 3 times in 10. ASR over N trials is the red-team analog of project 0's
"run 10x, threshold the result" (PLAN.md production practice 1).

The runner takes a `detector` CALLABLE, never a concrete detector class, so the
real detectors drop in without touching this code (the detector seam).
"""

import logging
from dataclasses import dataclass, field
from typing import Callable

from .dataset import Attack
from .providers.base import Provider

logger = logging.getLogger(__name__)

# Given the attack and the target's response, was the guardrail bypassed?
# True = bypass (attack succeeded). The detectors implement this shape.
Detector = Callable[[Attack, str], bool]


@dataclass
class ASRResult:
    attack_id: str
    trials: int
    bypasses: int
    # The raw reply from each trial, in order. Every send is scored (no separate
    # unscored "observational" send), so a bypass on any trial counts toward ASR -
    # and a caller can re-read the replies for secondary signals (which layer
    # fired) without firing extra requests.
    responses: list[str] = field(default_factory=list)

    @property
    def asr(self) -> float:
        """Attack success rate, 0.0-1.0."""
        return self.bypasses / self.trials if self.trials else 0.0


async def run_asr(
    provider: Provider, attack: Attack, detector: Detector, trials: int = 5
) -> ASRResult:
    """Send `attack` at the target `trials` times and count detected bypasses."""
    bypasses = 0
    responses: list[str] = []
    for i in range(trials):
        response = await provider.generate(attack.payload)
        responses.append(response)
        bypassed = detector(attack, response)
        logger.info("ASR %s trial %d/%d: bypass=%s", attack.id, i + 1, trials, bypassed)
        if bypassed:
            bypasses += 1
    result = ASRResult(attack.id, trials, bypasses, responses)
    logger.info("ASR %s: %d/%d = %.0f%%", attack.id, bypasses, trials, result.asr * 100)
    return result
