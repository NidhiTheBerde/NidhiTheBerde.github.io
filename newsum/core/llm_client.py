import json
import logging
import os
from typing import Literal, Optional

import anthropic
import httpx

from core.database import Database

logger = logging.getLogger(__name__)

CLAUDE_MODEL = "claude-opus-4-5"
CLAUDE_TIMEOUT = 30.0
OLLAMA_TIMEOUT = 120.0


class LLMClient:
    def __init__(
        self,
        provider: Optional[Literal["claude", "ollama"]] = None,
        db: Optional[Database] = None,
    ):
        self.provider = provider or os.getenv("LLM_PROVIDER", "claude")
        self.db = db
        if self.provider == "claude":
            self.client = anthropic.AsyncAnthropic(
                api_key=os.getenv("ANTHROPIC_API_KEY"),
                timeout=CLAUDE_TIMEOUT,
            )
        else:
            self.base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
            self.model = os.getenv("OLLAMA_MODEL", "llama3.1:8b")

    async def _complete_once(self, system: str, user: str, max_tokens: int) -> str:
        if self.provider == "claude":
            response = await self.client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            if self.db is not None:
                await self.db.log_usage(
                    agent="llm_client",
                    model=CLAUDE_MODEL,
                    input_tokens=response.usage.input_tokens,
                    output_tokens=response.usage.output_tokens,
                    cost_usd=0.0,
                )
            return response.content[0].text
        else:
            async with httpx.AsyncClient(timeout=OLLAMA_TIMEOUT) as client:
                r = await client.post(
                    f"{self.base_url}/api/chat",
                    json={
                        "model": self.model,
                        "messages": [
                            {"role": "system", "content": system},
                            {"role": "user", "content": user},
                        ],
                        "stream": False,
                    },
                )
                r.raise_for_status()
                return r.json()["message"]["content"]

    async def complete(self, system: str, user: str, max_tokens: int = 2000) -> str:
        try:
            return await self._complete_once(system, user, max_tokens)
        except (httpx.TimeoutException, httpx.HTTPStatusError) as exc:
            logger.warning("LLM call failed, not retrying transport error: %s", exc)
            raise

    async def complete_json(
        self, system: str, user: str, max_tokens: int = 2000
    ) -> dict:
        raw = await self.complete(system, user, max_tokens)
        try:
            return _parse_json(raw)
        except (json.JSONDecodeError, ValueError):
            logger.warning("Malformed JSON from LLM, retrying once")
            retry_user = (
                user
                + "\n\nIMPORTANT: Your previous response was not valid JSON. "
                "Return ONLY valid JSON, with no surrounding text or markdown fences."
            )
            raw = await self.complete(system, retry_user, max_tokens)
            return _parse_json(raw)


def _parse_json(raw: str) -> dict:
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        original_error = exc

    # Smaller/local models often wrap JSON in prose despite instructions.
    # Fall back to extracting the first balanced {...} block.
    start = text.find("{")
    if start == -1:
        raise original_error
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[start : i + 1])
    raise json.JSONDecodeError("No balanced JSON object found", text, start)
