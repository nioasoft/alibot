"""Resolve AliExpress short links to product IDs."""

from __future__ import annotations

import re
from typing import Optional

import httpx
from loguru import logger

_PRODUCT_ID_PATTERN = re.compile(r"/item/(\d+)\.html")


class LinkResolver:
    def __init__(self, timeout: float = 10.0):
        self._timeout = timeout
        self._cache: dict[str, Optional[str]] = {}

    async def resolve(self, url: str) -> Optional[str]:
        # Check if it's already a direct product link
        direct_match = _PRODUCT_ID_PATTERN.search(url)
        if direct_match:
            return direct_match.group(1)

        # Check cache
        if url in self._cache:
            return self._cache[url]

        # Follow redirects
        product_id = await self._follow_redirects(url)
        self._cache[url] = product_id
        return product_id

    async def _follow_redirects(self, url: str) -> Optional[str]:
        try:
            async with httpx.AsyncClient(
                follow_redirects=True,
                timeout=self._timeout,
            ) as client:
                response = await client.get(url)
                final_url = str(response.url)

                match = _PRODUCT_ID_PATTERN.search(final_url)
                if match:
                    return match.group(1)

                logger.warning(f"Resolved URL has no product ID: {final_url}")
                return None

        except httpx.TimeoutException:
            logger.error(f"Timeout resolving link: {url}")
            return None
        except httpx.HTTPError as e:
            logger.error(f"HTTP error resolving link {url}: {e}")
            return None
