"""Factory for OpenAI clients with optional Portkey routing.

Reads environment variables so we can switch between direct OpenAI and
Portkey without changing call sites across the codebase.
"""

import os
import logging
from typing import Dict
from openai import OpenAI, AsyncOpenAI


def _env() -> Dict:
    return {
        "USE_PORTKEY": os.getenv("USE_PORTKEY", "false").lower() == "true",
        "PORTKEY_BASE_URL": os.getenv("PORTKEY_BASE_URL", "https://api.portkey.ai/v1"),
        "PORTKEY_VIRTUAL_KEY": os.getenv("PORTKEY_VIRTUAL_KEY", ""),
        "PORTKEY_API_KEY": os.getenv("PORTKEY_API_KEY", ""),
        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY", ""),
    }


def make_openai_client(async_client: bool = False):
    """Return an OpenAI or AsyncOpenAI client routed via Portkey if enabled."""
    env = _env()
    kwargs: Dict = {}
    if env["USE_PORTKEY"]:
        kwargs.update({
            "api_key": "ignored",
            "base_url": env["PORTKEY_BASE_URL"],
            "default_headers": {
                "x-portkey-virtual-key": env["PORTKEY_VIRTUAL_KEY"],
                "x-portkey-api-key": env["PORTKEY_API_KEY"],
            },
        })
    else:
        kwargs["api_key"] = env["OPENAI_API_KEY"]

    return AsyncOpenAI(**kwargs) if async_client else OpenAI(**kwargs)


def make_direct_openai_client(async_client: bool = False):
    """Deprecated: keep for compatibility, but we now route all via Portkey when USE_PORTKEY=true."""
    env = _env()
    kwargs: Dict = {"api_key": env["OPENAI_API_KEY"]}
    return AsyncOpenAI(**kwargs) if async_client else OpenAI(**kwargs)


def current_openai_route_info() -> Dict:
    """Return the effective routing info for logging/diagnostics."""
    env = _env()
    if env["USE_PORTKEY"]:
        return {
            "provider": "portkey",
            "base_url": env["PORTKEY_BASE_URL"],
            "has_virtual_key": bool(env["PORTKEY_VIRTUAL_KEY"]),
            "has_api_key": bool(env["PORTKEY_API_KEY"]),
        }
    return {
        "provider": "openai",
        "base_url": "https://api.openai.com/v1",
        "has_api_key": bool(env["OPENAI_API_KEY"]),
    }


# One-time boot log to confirm route in app logs
try:
    _logger = logging.getLogger(__name__)
    route = current_openai_route_info()
    _logger.info(
        "OpenAI route configured: provider=%s base_url=%s",
        route.get("provider"), route.get("base_url")
    )
except Exception:
    pass


