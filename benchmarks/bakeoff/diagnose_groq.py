from __future__ import annotations

import json
import os
import urllib.error
import urllib.request


def main() -> None:
    key = os.environ.get("GROQ_API_KEY", "").strip()
    if not key:
        print("GROQ_DIAGNOSTIC_SKIPPED missing_credentials")
        return

    payload = {
        "model": "openai/gpt-oss-20b",
        "messages": [{"role": "user", "content": "Reply with OK only."}],
        "max_completion_tokens": 16,
        "temperature": 0,
    }
    body = json.dumps(payload).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "insight-desk-bakeoff/0.1",
    }
    request = urllib.request.Request(
        "https://api.groq.com/openai/v1/chat/completions",
        data=body,
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            text = response.read().decode("utf-8", errors="replace")
            print(f"GROQ_DIAGNOSTIC_HTTP_OK status={response.status} body={text[:1200]}")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:4000]
        print(f"GROQ_DIAGNOSTIC_HTTP_ERROR status={exc.code} detail={detail}")
        raise SystemExit(2)


if __name__ == "__main__":
    main()
