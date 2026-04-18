import sys

import openai._base_client as base_client

from bot.openai_runtime import install_openai_platform_override


def test_install_openai_platform_override_sets_static_macos_headers(monkeypatch):
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(base_client, "get_platform", lambda: "Unknown")
    base_client.platform_headers.cache_clear()

    installed = install_openai_platform_override()

    assert installed is True
    assert base_client.get_platform() == "MacOS"
    headers = base_client.platform_headers("test-version", platform=None)
    assert headers["X-Stainless-OS"] == "MacOS"


def test_install_openai_platform_override_is_idempotent(monkeypatch):
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(base_client, "get_platform", lambda: "Unknown")
    base_client.platform_headers.cache_clear()

    assert install_openai_platform_override() is True
    assert install_openai_platform_override() is False
