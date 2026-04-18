"""Runtime safeguards for OpenAI SDK behavior in the bot process."""

from __future__ import annotations

import sys

from loguru import logger


def install_openai_platform_override() -> bool:
    """Avoid macOS fork crashes caused by OpenAI platform detection."""

    if sys.platform != "darwin":
        return False

    import openai._base_client as base_client

    if getattr(base_client.get_platform, "__alibot_safe__", False):
        return False

    def _safe_get_platform() -> str:
        return "MacOS"

    _safe_get_platform.__alibot_safe__ = True  # type: ignore[attr-defined]
    base_client.get_platform = _safe_get_platform

    cache_clear = getattr(base_client.platform_headers, "cache_clear", None)
    if callable(cache_clear):
        cache_clear()

    logger.info("Installed safe OpenAI platform override for macOS")
    return True
