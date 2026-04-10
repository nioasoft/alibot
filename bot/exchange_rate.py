"""Daily USD/ILS exchange rate fetcher."""

from __future__ import annotations

import httpx
from loguru import logger


_cached_rate: float = 3.5  # sensible default


async def fetch_usd_ils_rate() -> float:
    """Fetch current USD to ILS exchange rate. Updates cached rate."""
    global _cached_rate
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get("https://api.exchangerate-api.com/v4/latest/USD")
            resp.raise_for_status()
            rate = resp.json()["rates"]["ILS"]
            _cached_rate = float(rate)
            logger.info(f"Exchange rate updated: 1 USD = {_cached_rate} ILS")
            return _cached_rate
    except Exception as e:
        logger.error(f"Failed to fetch exchange rate: {e}")
        return _cached_rate


def get_cached_rate() -> float:
    """Get the last fetched exchange rate."""
    return _cached_rate
