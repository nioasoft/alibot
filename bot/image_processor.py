"""Image processing: watermark overlay and perceptual hashing."""

from __future__ import annotations

import io
from typing import Optional

import imagehash
from PIL import Image
from loguru import logger

_MAX_DIMENSION = 4096
_MAX_FILE_SIZE = 10_000_000  # 10MB Telegram limit


def compute_image_hash(image_bytes: bytes) -> str:
    """Compute perceptual hash (dhash) for duplicate detection."""
    img = Image.open(io.BytesIO(image_bytes))
    return str(imagehash.dhash(img))


class ImageProcessor:
    def __init__(
        self,
        logo_path: str,
        position: str = "bottom-right",
        opacity: float = 0.4,
        scale: float = 0.15,
    ):
        self._logo = Image.open(logo_path).convert("RGBA")
        self._position = position
        self._opacity = opacity
        self._scale = scale

    def add_watermark(self, image_bytes: bytes) -> bytes:
        """Add watermark logo to image. Returns JPEG bytes."""
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")

        # Resize if too large
        img = self._resize_if_needed(img)

        # Prepare logo for this image size
        logo = self._prepare_logo(img.width, img.height)

        # Compute position
        x, y = self._compute_position(img.width, img.height, logo.width, logo.height)

        # Paste with transparency
        img.paste(logo, (x, y), logo)

        # Encode as JPEG
        buf = io.BytesIO()
        quality = 90
        img.save(buf, format="JPEG", quality=quality)

        # Reduce quality if still too large
        while buf.tell() > _MAX_FILE_SIZE and quality > 30:
            quality -= 10
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=quality)

        return buf.getvalue()

    def _prepare_logo(self, img_width: int, img_height: int) -> Image.Image:
        logo_width = int(img_width * self._scale)
        logo_height = int(self._logo.height * (logo_width / self._logo.width))
        logo = self._logo.resize((logo_width, logo_height), Image.LANCZOS)

        # Apply opacity
        r, g, b, a = logo.split()
        a = a.point(lambda p: int(p * self._opacity))
        logo.putalpha(a)

        return logo

    def _compute_position(
        self, img_w: int, img_h: int, logo_w: int, logo_h: int
    ) -> tuple[int, int]:
        margin = 10
        positions = {
            "bottom-right": (img_w - logo_w - margin, img_h - logo_h - margin),
            "bottom-left": (margin, img_h - logo_h - margin),
            "top-right": (img_w - logo_w - margin, margin),
            "top-left": (margin, margin),
        }
        return positions.get(self._position, positions["bottom-right"])

    def _resize_if_needed(self, img: Image.Image) -> Image.Image:
        if img.width <= _MAX_DIMENSION and img.height <= _MAX_DIMENSION:
            return img

        ratio = min(_MAX_DIMENSION / img.width, _MAX_DIMENSION / img.height)
        new_size = (int(img.width * ratio), int(img.height * ratio))
        logger.info(f"Resizing image from {img.size} to {new_size}")
        return img.resize(new_size, Image.LANCZOS)
