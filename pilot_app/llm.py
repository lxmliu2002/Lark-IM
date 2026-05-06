from __future__ import annotations

import json
import os
from typing import Any, TypeVar

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel

load_dotenv()

DEFAULT_ARK_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
DEFAULT_SYSTEM_PROMPT = """
You are an AI office copilot that outputs strict JSON for downstream automation.
Return JSON only. Never use markdown code fences.
Prefer Simplified Chinese when the input is mainly Chinese.
""".strip()

DEFAULT_TEXT_SYSTEM_PROMPT = """
You are an AI office copilot speaking directly to a user in a task console.
Be concise, specific, and action-oriented.
Prefer Simplified Chinese when the input is mainly Chinese.
""".strip()

ModelT = TypeVar("ModelT", bound=BaseModel)


class LLMJsonClient:
    def __init__(self) -> None:
        api_key = os.getenv("ARK_API_KEY") or os.getenv("OPENAI_API_KEY")
        model_id = os.getenv("ARK_MODEL_ID")
        base_url = os.getenv("ARK_BASE_URL", DEFAULT_ARK_BASE_URL)
        self.enabled = bool(api_key and model_id)
        self._model_id = model_id or ""
        self._client = OpenAI(api_key=api_key, base_url=base_url) if self.enabled else None

    def generate_model(self, prompt: str, model_cls: type[ModelT]) -> ModelT:
        if not self.enabled or self._client is None:
            raise ValueError("LLM client is not configured.")

        response = self._client.chat.completions.create(
            model=self._model_id,
            messages=[
                {"role": "system", "content": DEFAULT_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )
        content = response.choices[0].message.content or ""
        data: Any = json.loads(_extract_json_block(content))
        return model_cls.model_validate(data)

    def generate_text(self, prompt: str) -> str:
        if not self.enabled or self._client is None:
            raise ValueError("LLM client is not configured.")

        response = self._client.chat.completions.create(
            model=self._model_id,
            messages=[
                {"role": "system", "content": DEFAULT_TEXT_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
        )
        return (response.choices[0].message.content or "").strip()


def _extract_json_block(content: str) -> str:
    stripped = content.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        return stripped

    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError(f"Model did not return valid JSON: {stripped[:200]}")
    return stripped[start : end + 1]
