"""Small provider wrapper for structured extraction; all failures return None."""

import json

import httpx

from app.config import settings

EXTRACTION_PROMPT = """Extract the clinical question into JSON only, with keys specialty, condition, topic, intent, question, key_context, confidence. Use only these allowed values: specialties Oncology/Cardiology/Endocrinology/Other; conditions Breast cancer/Lung cancer/Heart failure/Atrial fibrillation/Type 2 diabetes/Obesity/Other; topics Treatment sequencing/Side-effect management/Clinical trials/Access/coverage/Guideline update/Drug interactions/Monitoring/Other; intents Clinical update/Evidence review/Case consult/Safety concern/Access question/Other. question must be one sentence. key_context must be a list of short non-identifying phrases. confidence must be a number from 0 to 1. Do not include patient identifiers.\nQuestion: """


def extract_with_llm(text: str) -> dict | None:
    provider = settings.llm_provider.casefold()
    if provider == "none" or not settings.llm_api_key or provider not in {"openai", "anthropic"}:
        return None
    timeout = httpx.Timeout(settings.llm_timeout_seconds)
    try:
        with httpx.Client(timeout=timeout) as client:
            if provider == "openai":
                response = client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {settings.llm_api_key}"},
                    json={"model": settings.llm_model or "gpt-4o-mini", "temperature": 0,
                          "response_format": {"type": "json_object"},
                          "messages": [{"role": "user", "content": EXTRACTION_PROMPT + text}]},
                )
                response.raise_for_status()
                result_text = response.json()["choices"][0]["message"]["content"]
            else:
                response = client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={"x-api-key": settings.llm_api_key, "anthropic-version": "2023-06-01"},
                    json={"model": settings.llm_model or "claude-3-5-haiku-latest", "max_tokens": 500,
                          "temperature": 0, "messages": [{"role": "user", "content": EXTRACTION_PROMPT + text}]},
                )
                response.raise_for_status()
                result_text = response.json()["content"][0]["text"]
        parsed = json.loads(result_text)
        return parsed if isinstance(parsed, dict) else None
    except (httpx.HTTPError, ValueError, KeyError, TypeError, IndexError):
        return None
