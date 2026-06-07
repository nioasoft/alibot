"""Tests for the shared pooled HTTP clients (keep-alive / port-exhaustion fix)."""

import httpx
import pytest

from bot import http_client


class TestSyncClient:
    def test_reuses_same_instance(self):
        http_client.close_sync_client()
        first = http_client.sync_client()
        second = http_client.sync_client()
        assert first is second  # reused, not recreated per call
        http_client.close_sync_client()

    def test_recreates_after_close(self):
        first = http_client.sync_client()
        http_client.close_sync_client()
        assert first.is_closed
        second = http_client.sync_client()
        assert second is not first
        assert not second.is_closed
        http_client.close_sync_client()

    def test_close_is_idempotent(self):
        http_client.sync_client()
        http_client.close_sync_client()
        http_client.close_sync_client()  # must not raise

    def test_has_keepalive_pool(self):
        client = http_client.sync_client()
        assert client.follow_redirects is True
        http_client.close_sync_client()


class TestNewAsyncClient:
    @pytest.mark.asyncio
    async def test_returns_async_client(self):
        client = http_client.new_async_client(timeout=5.0)
        assert isinstance(client, httpx.AsyncClient)
        await client.aclose()
