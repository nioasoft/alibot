"""Three-layer duplicate detection for deals."""

from __future__ import annotations

import datetime
from typing import Optional

from sqlalchemy import select, delete
from sqlalchemy.orm import Session
from loguru import logger

from bot.models import Deal


def _hamming_distance(hash1: str, hash2: str) -> int:
    """Compute hamming distance between two hex hash strings.

    @param hash1 - First hex hash string
    @param hash2 - Second hex hash string
    @returns Number of differing bits
    """
    n1 = int(hash1, 16)
    n2 = int(hash2, 16)
    return bin(n1 ^ n2).count("1")


class DuplicateChecker:
    """Three-layer duplicate checker: product ID, text hash, image perceptual hash."""

    def __init__(self, session: Session, window_hours: int, image_hash_threshold: int):
        """Initialize the duplicate checker.

        @param session - SQLAlchemy database session
        @param window_hours - Time window in hours for duplicate detection
        @param image_hash_threshold - Max hamming distance to consider image hashes similar
        """
        self._session = session
        self._window_hours = window_hours
        self._image_hash_threshold = image_hash_threshold

    def _cutoff(self) -> datetime.datetime:
        """Return the cutoff datetime for the dedup window."""
        return datetime.datetime.now(datetime.UTC) - datetime.timedelta(
            hours=self._window_hours
        )

    def is_duplicate(
        self,
        product_id: Optional[str] = None,
        text_hash: Optional[str] = None,
        image_hash: Optional[str] = None,
    ) -> bool:
        """Check if a deal is a duplicate using three layers of detection.

        Layers checked in order (most to least precise):
        1. Product ID exact match
        2. Text hash exact match
        3. Image perceptual hash similarity (hamming distance)

        @param product_id - AliExpress product ID to check
        @param text_hash - MD5 hash of normalized product name
        @param image_hash - Perceptual hash of product image (hex string)
        @returns True if a duplicate is found within the time window
        """
        cutoff = self._cutoff()

        # Layer 1: Product ID exact match
        if product_id is not None:
            exists = self._session.execute(
                select(Deal.id).where(
                    Deal.product_id == product_id,
                    Deal.created_at >= cutoff,
                )
            ).first()
            if exists:
                logger.debug(f"Duplicate: product_id={product_id}")
                return True

        # Layer 2: Text hash exact match
        if text_hash is not None:
            exists = self._session.execute(
                select(Deal.id).where(
                    Deal.text_hash == text_hash,
                    Deal.created_at >= cutoff,
                )
            ).first()
            if exists:
                logger.debug(f"Duplicate: text_hash={text_hash}")
                return True

        # Layer 3: Image perceptual hash similarity
        if image_hash is not None:
            recent_hashes = (
                self._session.execute(
                    select(Deal.image_hash).where(
                        Deal.image_hash.isnot(None),
                        Deal.created_at >= cutoff,
                    )
                )
                .scalars()
                .all()
            )

            for existing_hash in recent_hashes:
                try:
                    distance = _hamming_distance(image_hash, existing_hash)
                    if distance < self._image_hash_threshold:
                        logger.debug(
                            f"Duplicate: image_hash distance={distance} "
                            f"(threshold={self._image_hash_threshold})"
                        )
                        return True
                except ValueError:
                    continue

        return False

    def cleanup_old(self) -> int:
        """Remove deals older than the dedup window.

        @returns Number of deals deleted
        """
        cutoff = self._cutoff()
        result = self._session.execute(
            delete(Deal).where(Deal.created_at < cutoff)
        )
        self._session.commit()
        count = result.rowcount
        if count:
            logger.info(f"Cleaned up {count} old deals")
        return count
