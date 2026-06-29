import pytest

from llm_red.providers.ollama import OllamaProvider


@pytest.mark.live
async def test_live_backend_responds():
    out = await OllamaProvider().generate("Say exactly the word: ok")
    assert isinstance(out, str) and len(out) > 0
