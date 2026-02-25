from __future__ import annotations

import json
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import get_settings


class LlmUnavailable(Exception):
    pass


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=0.5, min=0.5, max=4))
def openai_compatible_chat_json(system: str, user: str, *, schema_hint: dict[str, Any]) -> dict[str, Any]:
    """
    Calls an OpenAI-compatible chat endpoint (if configured) and asks for strict JSON output.
    If not configured, raise LlmUnavailable.
    """
    s = get_settings()
    if not s.openai_api_key:
        raise LlmUnavailable("OPENAI_API_KEY not set")

    base_url = (s.openai_base_url or "https://api.openai.com/v1").rstrip("/")
    url = f"{base_url}/chat/completions"

    payload = {
        "model": s.openai_model,
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
            {
                "role": "user",
                "content": "Return ONLY valid JSON. Output must match this schema hint:\n"
                + json.dumps(schema_hint, ensure_ascii=False),
            },
        ],
    }

    headers = {"Authorization": f"Bearer {s.openai_api_key}"}
    with httpx.Client(timeout=20.0, headers=headers) as client:
        r = client.post(url, json=payload)
        r.raise_for_status()
        data = r.json()

    content = data["choices"][0]["message"]["content"]
    return json.loads(content)

