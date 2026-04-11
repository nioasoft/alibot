"""Stub publisher for future web/export destinations."""

from __future__ import annotations

from loguru import logger


class WebPublisher:
    def __init__(self, enabled: bool = False) -> None:
        self._enabled = enabled

    @property
    def is_enabled(self) -> bool:
        return self._enabled

    async def send_deal(
        self,
        target_ref: str,
        payload: dict,
    ) -> bool:
        if not self._enabled:
            logger.warning(f"Web destination '{target_ref}' is disabled")
            return False

        logger.info(f"Web export not implemented yet for target '{target_ref}': {payload.get('deal_id')}")
        return False
