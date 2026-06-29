import logging

import httpx

from .base import Provider, with_retry

logger = logging.getLogger(__name__)


class OllamaProvider(Provider):
    def __init__(
        self,
        model: str = "llama3.2",
        base_url: str = "http://localhost:11434",
        *,
        temperature: float | None = None,
        json_format: bool = False,
        timeout: float = 60.0,
    ):
        # temperature/json_format default to off so the existing target seam is
        # unchanged; the LLM-judge sets temperature=0 (variance control) and
        # json_format=True (Ollama constrains output to valid JSON, so a chatty
        # judge can't break the parser).
        # timeout is per-request seconds. 60s suits the small llama3.2 target; the
        # judge runs a 7B model over a long rubric prompt (~45s/call measured, more
        # under self-consistency voting), so judge usage passes a larger value.
        self.model = model
        self.base_url = base_url
        self.temperature = temperature
        self.json_format = json_format
        self.timeout = timeout

    async def generate(self, prompt: str) -> str:
        logger.info("OllamaProvider prompt:\n%s", prompt)
        payload: dict = {"model": self.model, "prompt": prompt, "stream": False}
        if self.temperature is not None:
            payload["options"] = {"temperature": self.temperature}
        if self.json_format:
            payload["format"] = "json"

        async def _call() -> str:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                r = await client.post(f"{self.base_url}/api/generate", json=payload)
                r.raise_for_status()
                return r.json()["response"]

        response = await with_retry(_call, desc=f"ollama generate {self.model}")
        logger.info("OllamaProvider response:\n%s", response)
        return response

    async def chat(self, messages: list[dict]) -> str:
        """Role-structured chat completion via /api/chat.

        Separate from generate() because Ollama applies the MODEL'S chat template
        here, not on /api/generate. Llama Guard needs this: its template injects
        the MLCommons safety policy + the S1-S14 hazard categories around the
        conversation, and it classifies the LAST turn. Hand-building that prompt
        would hardcode one Guard version's category list; letting Ollama apply the
        model's own template keeps it faithful across versions.
        """
        logger.info("OllamaProvider chat messages:\n%s", messages)
        payload: dict = {"model": self.model, "messages": messages, "stream": False}
        if self.temperature is not None:
            payload["options"] = {"temperature": self.temperature}

        async def _call() -> str:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                r = await client.post(f"{self.base_url}/api/chat", json=payload)
                r.raise_for_status()
                return r.json()["message"]["content"]

        response = await with_retry(_call, desc=f"ollama chat {self.model}")
        logger.info("OllamaProvider chat response:\n%s", response)
        return response
