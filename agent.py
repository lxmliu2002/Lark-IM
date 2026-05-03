import json
import os
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

from schemas import AnalysisResult

load_dotenv()

DEFAULT_ARK_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
DEFAULT_SYSTEM_PROMPT = """
You are an office collaboration assistant.
Analyze IM chat logs and return structured data only.
Your output must be valid JSON and must match the requested schema exactly.
Do not wrap the JSON in markdown code fences.
Use the same language as the source chat whenever practical.
If the source chat is mainly in Chinese, respond in Simplified Chinese.
""".strip()


def _build_client() -> tuple[OpenAI, str]:
    api_key = os.getenv("ARK_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError(
            "Missing API key. Please set ARK_API_KEY in .env with the real key from Volcengine."
        )

    model_id = os.getenv("ARK_MODEL_ID")
    if not model_id:
        raise ValueError(
            "Missing model ID. Please set ARK_MODEL_ID in .env, for example ep-xxxxxxxx."
        )

    base_url = os.getenv("ARK_BASE_URL", DEFAULT_ARK_BASE_URL)
    client = OpenAI(api_key=api_key, base_url=base_url)
    return client, model_id


def _extract_json_block(content: str) -> str:
    content = content.strip()
    if content.startswith("{") and content.endswith("}"):
        return content

    start = content.find("{")
    end = content.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError(f"Model did not return valid JSON: {content[:200]}")
    return content[start : end + 1]


def _parse_analysis_result(content: str) -> AnalysisResult:
    json_text = _extract_json_block(content)
    data: Any = json.loads(json_text)
    return AnalysisResult.model_validate(data)


def call_llm(prompt: str) -> AnalysisResult:
    client, model_id = _build_client()
    response = client.chat.completions.create(
        model=model_id,
        messages=[
            {"role": "system", "content": DEFAULT_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
    )

    content = response.choices[0].message.content or ""
    return _parse_analysis_result(content)


def analyze_im_chat(chat_text: str) -> AnalysisResult:
    prompt = f"""
Analyze the following IM chat content and return valid JSON with this schema:

{{
  "topic": "string",
  "summary": ["string", "string"],
  "action_items": [
    {{
      "task": "string",
      "owner": "string",
      "deadline": "string",
      "status": "string"
    }}
  ],
  "owners": [
    {{
      "name": "string",
      "responsibility": "string"
    }}
  ],
  "deadlines": [
    {{
      "item": "string",
      "due": "string"
    }}
  ],
  "ppt_outline": [
    {{
      "title": "string",
      "bullets": ["string", "string"]
    }}
  ]
}}

Rules:
- Return JSON only.
- Keep the schema exactly as specified.
- Use concise, presentation-ready wording.
- If some information is missing, use an empty string or an empty array instead of inventing details.
- Keep ppt_outline render-neutral and content-focused.
- Match the language of the chat content. For Chinese chats, use Simplified Chinese.

Chat content:

{chat_text}
""".strip()
    return call_llm(prompt)
