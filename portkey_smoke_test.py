#!/usr/bin/env python3
"""
Local Portkey connectivity check for both Chat Completions and Responses APIs.

Usage:
  USE_PORTKEY=true \
  PORTKEY_BASE_URL=https://api.portkey.ai/v1 \
  PORTKEY_VIRTUAL_KEY=pk_live_xxx \
  PORTKEY_API_KEY=pk_api_xxx \
  OPENAI_API_KEY=sk-ignored \
  python portkey_smoke_test.py
"""

import os
import time
import json
try:
    from dotenv import load_dotenv
    # Load .env explicitly from project root (current working directory)
    load_dotenv(dotenv_path=os.path.join(os.getcwd(), ".env"))
except Exception:
    pass
from openai_client import make_openai_client, current_openai_route_info


def pretty(obj):
    try:
        return json.dumps(obj, indent=2, ensure_ascii=False)
    except Exception:
        return str(obj)


def test_chat(client):
    start = time.time()
    resp = client.chat.completions.create(
        model=os.getenv("TEST_MODEL", "gpt-4o-mini"),
        messages=[{"role": "user", "content": "Reply with OK"}],
        max_tokens=3,
        temperature=0,
    )
    elapsed = (time.time() - start) * 1000
    msg = resp.choices[0].message.content if resp.choices else ""
    return {
        "ms": round(elapsed, 1),
        "id": getattr(resp, "id", None),
        "model": getattr(resp, "model", None),
        "message": msg,
    }


def test_responses(client):
    start = time.time()
    resp = client.responses.create(
        model=os.getenv("TEST_MODEL", "gpt-4o-mini"),
        input="Reply with OK",
        max_output_tokens=32,
    )
    elapsed = (time.time() - start) * 1000
    # Try common shapes
    out = None
    if hasattr(resp, "output_text"):
        out = resp.output_text
    elif hasattr(resp, "choices") and resp.choices:
        out = resp.choices[0].message.content
    else:
        out = str(resp)
    return {
        "ms": round(elapsed, 1),
        "id": getattr(resp, "id", None),
        "model": getattr(resp, "model", None),
        "output": out,
    }


def main():
    # Echo key envs (mask secrets) to confirm .env loaded
    env_preview = {
        "USE_PORTKEY": os.getenv("USE_PORTKEY"),
        "PORTKEY_BASE_URL": os.getenv("PORTKEY_BASE_URL"),
        "PORTKEY_VIRTUAL_KEY_set": bool(os.getenv("PORTKEY_VIRTUAL_KEY")),
        "PORTKEY_API_KEY_set": bool(os.getenv("PORTKEY_API_KEY")),
    }
    print("Env:", pretty(env_preview))
    print("Route:", pretty(current_openai_route_info()))

    if os.getenv("USE_PORTKEY", "false").lower() == "true":
        missing = []
        if not os.getenv("PORTKEY_BASE_URL"): missing.append("PORTKEY_BASE_URL")
        if not os.getenv("PORTKEY_VIRTUAL_KEY"): missing.append("PORTKEY_VIRTUAL_KEY")
        if not os.getenv("PORTKEY_API_KEY"): missing.append("PORTKEY_API_KEY")
        if missing:
            print("❌ Missing required Portkey env vars in .env:", ", ".join(missing))
            return
    try:
        client = make_openai_client(async_client=False)
    except Exception as e:
        print("❌ Failed to create client:", repr(e))
        return

    # Chat test
    try:
        chat = test_chat(client)
        print("✅ Chat OK:", pretty(chat))
    except Exception as e:
        print("❌ Chat error:", repr(e))

    # Responses test
    try:
        res = test_responses(client)
        print("✅ Responses OK:", pretty(res))
    except Exception as e:
        print("❌ Responses error:", repr(e))


if __name__ == "__main__":
    main()


