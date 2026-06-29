"""The bounded retry that keeps a long live run from going red on one stalled
call (both 2026-06-28 live failures were a single httpx.ReadTimeout under ollama
contention - infra noise, not a finding). Verifies a transient transport fault is
retried and a real error is NOT, so genuine failures still surface."""

import httpx
import pytest
import respx
from httpx import Response

from llm_red.providers import base
from llm_red.providers.base import RETRYABLE_EXC, _is_transient, with_retry
from llm_red.providers.target import TargetProvider


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    """Don't actually wait out the backoff in tests."""

    async def _instant(_seconds):
        return None

    monkeypatch.setattr(base.asyncio, "sleep", _instant)


@pytest.mark.mocked
async def test_retries_transient_then_succeeds():
    calls = {"n": 0}

    async def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise httpx.ReadTimeout("stalled model reload")
        return "ok"

    assert await with_retry(flaky, attempts=3, backoff=0) == "ok"
    assert calls["n"] == 3


@pytest.mark.mocked
async def test_gives_up_after_attempts():
    async def always_timeout():
        raise httpx.ConnectError("ollama down")

    with pytest.raises(httpx.ConnectError):
        await with_retry(always_timeout, attempts=2, backoff=0)


@pytest.mark.mocked
async def test_non_transient_raises_immediately():
    calls = {"n": 0}

    async def boom():
        calls["n"] += 1
        raise ValueError("a parse bug, not a transport fault")

    with pytest.raises(ValueError):
        await with_retry(boom, attempts=3, backoff=0)
    assert calls["n"] == 1, "a non-transport error must not be retried"


def test_transient_classification():
    # Guard the exact faults the live runs hit: a transport timeout (both
    # 2026-06-28 failures) and a project-0 500 (its uncaught ollama ReadTimeout,
    # seen in the smoke run). A 4xx is NOT transient - it is a real verdict.
    assert isinstance(httpx.ReadTimeout("x"), RETRYABLE_EXC)
    resp500 = Response(500, request=httpx.Request("POST", "http://x/ask"))
    assert _is_transient(httpx.HTTPStatusError("e", request=resp500.request, response=resp500))
    resp400 = Response(400, request=httpx.Request("POST", "http://x/ask"))
    assert not _is_transient(httpx.HTTPStatusError("e", request=resp400.request, response=resp400))


@pytest.mark.mocked
@respx.mock
async def test_target_provider_retries_timeout():
    # The _no_sleep fixture makes the provider's default backoff instant here.
    route = respx.post("http://localhost:8000/ask").mock(
        side_effect=[httpx.ReadTimeout("stalled"), Response(200, json={"answer": "Paris"})]
    )
    out = await TargetProvider().generate("What is the capital of France?")
    assert out == "Paris"
    assert route.call_count == 2


@pytest.mark.mocked
@respx.mock
async def test_target_provider_retries_project0_500():
    # project-0 returns 500 when its own ollama call times out (uncaught
    # ReadTimeout). That is transient infra noise, so the suite retries it.
    route = respx.post("http://localhost:8000/ask").mock(
        side_effect=[
            Response(500, json={"detail": "boom"}),
            Response(200, json={"answer": "Paris"}),
        ]
    )
    out = await TargetProvider().generate("What is the capital of France?")
    assert out == "Paris"
    assert route.call_count == 2
