import pytest

from llm_red.dataset import load_attacks
from llm_red.detectors import injected_output_present
from llm_red.providers.target import TargetProvider
from llm_red.runner import run_asr


@pytest.mark.live
async def test_one_attack_round_trips_into_report():
    # Full pipe: catalog -> provider -> runner -> ASR result, against the real
    # target. Uses the positive detector (success marker present AND not a
    # refusal), not an absence-of-refusal baseline.
    di_001 = next(a for a in load_attacks() if a.id == "di-001")
    result = await run_asr(TargetProvider(), di_001, injected_output_present, trials=3)

    assert result.attack_id == "di-001"
    assert result.trials == 3
    assert 0 <= result.bypasses <= 3
    assert 0.0 <= result.asr <= 1.0
