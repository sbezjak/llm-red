"""Fire jailbreak / role-play attacks at the REAL hardened target.

Requires project 0 with HARDENED=1 (default :8001, override LLMRED_HARDENED_URL).
Same observational posture as the extraction live test: non-deterministic, so we
log rather than assert leak rates, and read the transcripts to grade.

Two detection routes (notes the family file):
- jb-001..003 aim at the canary -> canary_leaked is the deterministic signal.
- jb-004 aims at harmful content -> canary_leaked will read 0; the meaningful
  signals are self-refusal (L2 held) and whether L3 scrubbed the reply. We log
  both and read the content (the "is this a real bypass" call).
"""

import logging
import os

import pytest

from llm_red.dataset import load_attacks
from llm_red.detectors import canary_leaked, refused
from llm_red.providers.target import OUTPUT_FILTER_MARKER, TargetProvider
from llm_red.runner import run_asr

logger = logging.getLogger(__name__)

HARDENED_URL = os.environ.get("LLMRED_HARDENED_URL", "http://localhost:8001")
JAILBREAK_ATTACKS = [a for a in load_attacks() if a.family == "jailbreak"]


@pytest.mark.live
@pytest.mark.parametrize("attack", JAILBREAK_ATTACKS, ids=lambda a: a.id)
async def test_jailbreak_against_hardened_target_live(attack):
    provider = TargetProvider(HARDENED_URL)

    result = await run_asr(provider, attack, canary_leaked, trials=5)
    assert result.responses and all(result.responses), "target returned an empty reply"
    logger.info(
        "LIVE %s canary-leak ASR=%.0f%% (%d/%d)",
        attack.id,
        result.asr * 100,
        result.bypasses,
        result.trials,
    )

    # Secondary signals across the scored sends (jb-004 aims at content, not the
    # canary, so canary_leaked stays 0 - read the transcript + these flags).
    refusals = sum(refused(r) for r in result.responses)
    filtered = sum(OUTPUT_FILTER_MARKER in r for r in result.responses)
    logger.info(
        "LIVE %s self_refused=%d/%d output_filtered=%d/%d",
        attack.id,
        refusals,
        result.trials,
        filtered,
        result.trials,
    )
