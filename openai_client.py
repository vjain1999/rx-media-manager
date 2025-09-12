"""Factory for OpenAI clients with optional Portkey routing.

Reads environment variables so we can switch between direct OpenAI and
Portkey without changing call sites across the codebase.
"""

import os
from typing import Dict
from openai import OpenAI, AsyncOpenAI


USE_PORTKEY = os.getenv("USE_PORTKEY", "false").lower() == "true"
PORTKEY_BASE_URL = os.getenv("PORTKEY_BASE_URL", "https://api.portkey.ai/v1")
PORTKEY_VIRTUAL_KEY = os.getenv("PORTKEY_VIRTUAL_KEY", "")
PORTKEY_API_KEY = os.getenv("PORTKEY_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")


def make_openai_client(async_client: bool = False):
    """Return an OpenAI or AsyncOpenAI client routed via Portkey if enabled."""
    kwargs: Dict = {}

    if USE_PORTKEY:
        kwargs.update({
            "api_key": "ignored",
            "base_url": PORTKEY_BASE_URL,
            "default_headers": {
                # Portkey standard headers
                "x-portkey-virtual-key": PORTKEY_VIRTUAL_KEY,
                "x-portkey-api-key": PORTKEY_API_KEY,
            },
        })
    else:
        kwargs["api_key"] = OPENAI_API_KEY

    return AsyncOpenAI(**kwargs) if async_client else OpenAI(**kwargs)


def make_direct_openai_client(async_client: bool = False):
    """Return a client that talks directly to OpenAI (bypassing Portkey)."""
    kwargs: Dict = {"api_key": OPENAI_API_KEY}
    return AsyncOpenAI(**kwargs) if async_client else OpenAI(**kwargs)


