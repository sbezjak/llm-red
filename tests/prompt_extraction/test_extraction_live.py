"""Fire system-prompt / canary extraction at the REAL hardened target.

Requires project 0 running with HARDENED=1 (the canary + 3 layers). By default
that is a second instance on :8001, so the as-is :8000 server can stay up for the
as-is live tests in the same run; override with LLMRED_HARDENED_URL.

First-run posture is OBSERVATIONAL, like the evasion live test: extraction
against a real model is non-deterministic, so we do not assert a leak rate. We
assert the pipe round-trips, then LOG the canary-leak ASR and which layer fired,
and put every raw reply in the report for us to read end to end. EVERY send is
scored (F6: an unscored "observational" send once hid a real spelled-out
leak behind a 0% ASR). Confirmed bypasses get locked as xfail(strict=True)
contracts AFTER we grade the report.
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
EXTRACTION_ATTACKS = [a for a in load_attacks() if a.family == "prompt_extraction"]


@pytest.mark.live
@pytest.mark.parametrize("attack", EXTRACTION_ATTACKS, ids=lambda a: a.id)
async def test_extraction_against_hardened_target_live(attack):
    provider = TargetProvider(HARDENED_URL)

    # canary_leaked catches a literal OR spelled-out leak deterministically; a
    # base64/translated leak slips past it (the LLM-judge gap), so a 0% on pe-005 is
    # "deterministic detector can't see it", not necessarily "safe" - read it.
    result = await run_asr(provider, attack, canary_leaked, trials=5)
    assert result.responses and all(result.responses), "target returned an empty reply"
    logger.info(
        "LIVE %s canary-leak ASR=%.0f%% (%d/%d)",
        attack.id,
        result.asr * 100,
        result.bypasses,
        result.trials,
    )

    # Secondary layer signals across the same scored sends (no extra request):
    # how often the model self-refused (L2), and how often L3 scrubbed the reply.
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
