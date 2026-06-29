import pytest

from llm_red.providers.target import TargetProvider


@pytest.mark.live
async def test_live_target_responds():
    out = await TargetProvider().generate("Say exactly the word: ok")
    assert isinstance(out, str) and len(out) > 0
