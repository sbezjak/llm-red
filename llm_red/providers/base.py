import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Awaitable, Callable, TypeVar

import httpx

logger = logging.getLogger(__name__)

# Transient faults seen under heavy local-ollama contention: a long live run
# loads/evicts several models on one ollama, and a stalled call trips a timeout.
# This shows up two ways, both pure infra noise, NOT a red-team finding:
#   1. a transport timeout on OUR call to the backend (httpx.ReadTimeout); and
#   2. a 5xx from project-0, whose /ask leaves its own ollama ReadTimeout uncaught
#      and so returns 500 (502/503 for the cases it does catch).
# Both 2026-06-28 live failures were case 1; the smoke run surfaced case 2. A
# bounded retry on both keeps an hour-long run from going red on one stalled call.
# Genuine signals - refusals, compliance, blocklist verdicts - are untouched: a
# 4xx (e.g. the 400 refusal) and any non-HTTP error re-raise immediately.
RETRYABLE_EXC = (httpx.TimeoutException, httpx.ConnectError, httpx.RemoteProtocolError)
RETRYABLE_STATUS = {500, 502, 503, 504}

T = TypeVar("T")


def _is_transient(exc: Exception) -> bool:
    if isinstance(exc, RETRYABLE_EXC):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in RETRYABLE_STATUS
    return False


async def with_retry(
    call: Callable[[], Awaitable[T]], *, attempts: int = 3, backoff: float = 3.0, desc: str = ""
) -> T:
    """Run an async request, retrying a few times on transient backend faults.

    Linear backoff (3s, 6s) gives a reloading model time to settle. Anything that
    is not transient - a 4xx the provider raised, a parse error - re-raises at once,
    so real failures are never masked.
    """
    for attempt in range(1, attempts + 1):
        try:
            return await call()
        except httpx.HTTPError as exc:
            if not _is_transient(exc) or attempt == attempts:
                raise
            wait = backoff * attempt
            logger.warning(
                "transient %s on %s (attempt %d/%d), retrying in %.0fs",
                type(exc).__name__,
                desc or "provider call",
                attempt,
                attempts,
                wait,
            )
            await asyncio.sleep(wait)
    raise AssertionError("unreachable")  # pragma: no cover


class Provider(ABC):
    """The single seam where HTTP calls to a model backend or target API live.

    Tests mock at this boundary with respx, so attack construction and
    detection never need a live network.
    """

    @abstractmethod
    async def generate(self, prompt: str) -> str: ...
