"""WhatsApp publisher — sends deals to WhatsApp group via Baileys microservice."""

from __future__ import annotations

from typing import Optional

import httpx
from loguru import logger


class WhatsAppPublisher:
    def __init__(self, base_url: str = "http://localhost:3001", group_jid: str = ""):
        self._base_url = base_url
        self._group_jid = group_jid
        self._enabled = bool(group_jid)

    @property
    def is_enabled(self) -> bool:
        return self._enabled

    async def check_health(self) -> bool:
        """Check if WhatsApp service is running and connected."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self._base_url}/health")
                data = resp.json()
                return data.get("status") == "connected"
        except Exception:
            return False

    async def send_deal(
        self,
        text: str,
        image_path: Optional[str] = None,
        group_jid: Optional[str] = None,
    ) -> bool:
        """Send a deal to WhatsApp group.

        Args:
            text: Deal text (Hebrew).
            image_path: Path to image file (optional).
            group_jid: Override default group JID.

        Returns:
            True if sent successfully.
        """
        if not self._enabled:
            return False

        target = group_jid or self._group_jid

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                if image_path:
                    with open(image_path, "rb") as f:
                        resp = await client.post(
                            f"{self._base_url}/send-image",
                            data={"text": text, "group_jid": target},
                            files={"image": ("deal.jpg", f, "image/jpeg")},
                        )
                else:
                    resp = await client.post(
                        f"{self._base_url}/send",
                        json={"text": text, "group_jid": target},
                    )

                if resp.status_code == 200:
                    logger.info(f"WhatsApp deal sent to {target}")
                    return True
                else:
                    logger.error(f"WhatsApp send failed: {resp.status_code} {resp.text}")
                    return False

        except httpx.ConnectError:
            logger.warning("WhatsApp service not running")
            return False
        except Exception as e:
            logger.error(f"WhatsApp send error: {e}")
            return False
