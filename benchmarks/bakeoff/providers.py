from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable

from provider_contract import prompt_for, schema_for


class ProviderError(RuntimeError):
    pass


@dataclass(frozen=True)
class ProviderSpec:
    id: str
    required_env: tuple[str, ...]
    delay_seconds: float
    call: Callable[[dict[str, Any]], dict[str, Any]]


def _env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ProviderError(f"missing credential: {name}")
    return value


def _post_json(
    url: str,
    payload: dict[str, Any],
    headers: dict[str, str],
    *,
    attempts: int = 3,
    timeout: int = 90,
) -> dict[str, Any]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request_headers = {"Content-Type": "application/json", **headers}
    last_error: Exception | None = None
    for attempt in range(attempts):
        request = urllib.request.Request(url, data=body, headers=request_headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:2000]
            last_error = ProviderError(f"HTTP {exc.code}: {detail}")
            if exc.code not in {429, 500, 502, 503, 504} or attempt + 1 == attempts:
                raise last_error from exc
            retry_after = exc.headers.get("Retry-After")
            sleep_for = float(retry_after) if retry_after and retry_after.isdigit() else 2 ** attempt
            time.sleep(min(sleep_for, 30.0))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt + 1 == attempts:
                raise ProviderError(str(exc)) from exc
            time.sleep(2 ** attempt)
    raise ProviderError(str(last_error or "provider request failed"))


def _decode_json_text(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if not isinstance(value, str):
        raise ProviderError(f"expected JSON text/object, got {type(value).__name__}")
    try:
        decoded = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ProviderError(f"invalid provider JSON: {value[:500]}") from exc
    if not isinstance(decoded, dict):
        raise ProviderError("provider JSON root must be an object")
    return decoded


def _groq(case: dict[str, Any], model: str) -> dict[str, Any]:
    schema = schema_for(case)
    response = _post_json(
        "https://api.groq.com/openai/v1/chat/completions",
        {
            "model": model,
            "messages": [
                {"role": "system", "content": "Follow the JSON schema exactly. Do not output commentary."},
                {"role": "user", "content": prompt_for(case)},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": f"insight_desk_{case['task'].lower()}",
                    "strict": True,
                    "schema": schema,
                },
            },
            "reasoning_effort": "low",
        },
        {"Authorization": f"Bearer {_env('GROQ_API_KEY')}"},
    )
    try:
        content = response["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ProviderError(f"unexpected Groq response: {str(response)[:1000]}") from exc
    return _decode_json_text(content)


def call_groq20(case: dict[str, Any]) -> dict[str, Any]:
    return _groq(case, "openai/gpt-oss-20b")


def call_groq120(case: dict[str, Any]) -> dict[str, Any]:
    return _groq(case, "openai/gpt-oss-120b")


def call_cloudflare(case: dict[str, Any]) -> dict[str, Any]:
    account_id = _env("CLOUDFLARE_ACCOUNT_ID")
    token = _env("CLOUDFLARE_API_TOKEN")
    model = "@cf/deepseek-ai/deepseek-r1-distill-qwen-32b"
    response = _post_json(
        f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model}",
        {
            "messages": [
                {"role": "system", "content": "Return only JSON matching the supplied schema."},
                {"role": "user", "content": prompt_for(case)},
            ],
            "response_format": {"type": "json_schema", "json_schema": schema_for(case)},
            "max_tokens": 256,
            "temperature": 0,
        },
        {"Authorization": f"Bearer {token}"},
    )
    if response.get("success") is False:
        raise ProviderError(f"Cloudflare API failure: {str(response)[:1000]}")
    result = response.get("result", response)
    if isinstance(result, dict) and "response" in result:
        result = result["response"]
    return _decode_json_text(result)


def call_gemini(case: dict[str, Any]) -> dict[str, Any]:
    response = _post_json(
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.7-flash:generateContent",
        {
            "contents": [{"parts": [{"text": prompt_for(case)}]}],
            "generationConfig": {
                "responseFormat": {
                    "text": {
                        "mimeType": "application/json",
                        "schema": schema_for(case),
                    }
                }
            },
        },
        {"x-goog-api-key": _env("GEMINI_API_KEY")},
    )
    try:
        content = response["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ProviderError(f"unexpected Gemini response: {str(response)[:1000]}") from exc
    return _decode_json_text(content)


PROVIDERS: dict[str, ProviderSpec] = {
    "groq20": ProviderSpec("groq20", ("GROQ_API_KEY",), 2.1, call_groq20),
    "groq120": ProviderSpec("groq120", ("GROQ_API_KEY",), 2.1, call_groq120),
    "cloudflare": ProviderSpec(
        "cloudflare",
        ("CLOUDFLARE_ACCOUNT_ID", "CLOUDFLARE_API_TOKEN"),
        0.25,
        call_cloudflare,
    ),
    "gemini": ProviderSpec("gemini", ("GEMINI_API_KEY",), 1.0, call_gemini),
}


def available(spec: ProviderSpec) -> bool:
    return all(bool(os.environ.get(name, "").strip()) for name in spec.required_env)
