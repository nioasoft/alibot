"""Shared pooled HTTP clients (keep-alive) to avoid ephemeral port exhaustion.

Creating a fresh ``httpx.AsyncClient`` / ``httpx.get`` per call opens a new TCP
connection that lands in ``TIME_WAIT`` for ~2*MSL after it closes. At the volume
this bot runs (one resolve + image download per deal, repeated health/send calls)
that churn exhausts the OS ephemeral port range and every new outbound connection
starts failing with "Can't assign requested address".

Reusing a pooled client keeps connections alive across requests and collapses the
churn to a handful of sockets. Long-lived objects should create ONE async client
in ``__init__``-time/lazily and reuse it; one-off synchronous downloads share the
module-level sync client.
"""

from __future__ import annotations

import httpx

# Tuned for steady reuse rather than burst fan-out: keep a small pool of warm
# connections alive for 30s so back-to-back requests skip the TCP/TLS handshake.
DEFAULT_LIMITS = httpx.Limits(
    max_keepalive_connections=20,
    max_connections=100,
    keepalive_expiry=30.0,
)


def new_async_client(timeout: float | None = None, **kwargs) -> httpx.AsyncClient:
    """Create a pooled ``AsyncClient``.

    Intended to be called ONCE per long-lived object and reused for that object's
    lifetime (close it with ``aclose()`` on shutdown). Per-request overrides such
    as ``timeout=`` / ``follow_redirects=`` can still be passed at the call site.
    """
    return httpx.AsyncClient(timeout=timeout, limits=DEFAULT_LIMITS, **kwargs)


_sync_client: httpx.Client | None = None


def sync_client() -> httpx.Client:
    """Return the shared pooled sync client for one-off GETs (e.g. image downloads).

    Lazily created and reused process-wide so repeated downloads reuse connections
    instead of opening a fresh socket each time.
    """
    global _sync_client
    if _sync_client is None or _sync_client.is_closed:
        _sync_client = httpx.Client(limits=DEFAULT_LIMITS, follow_redirects=True)
    return _sync_client


def close_sync_client() -> None:
    """Close the shared sync client (best-effort; safe to call multiple times)."""
    global _sync_client
    if _sync_client is not None and not _sync_client.is_closed:
        _sync_client.close()
    _sync_client = None
