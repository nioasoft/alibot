import io
import pytest
from PIL import Image

from bot.image_processor import ImageProcessor, compute_image_hash


@pytest.fixture
def logo_bytes() -> bytes:
    """Create a small test logo (red square with transparency)."""
    logo = Image.new("RGBA", (100, 100), (255, 0, 0, 200))
    buf = io.BytesIO()
    logo.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def sample_image_bytes() -> bytes:
    """Create a sample product image (blue rectangle)."""
    img = Image.new("RGB", (800, 600), (0, 0, 255))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


@pytest.fixture
def processor(tmp_path, logo_bytes) -> ImageProcessor:
    logo_path = tmp_path / "logo.png"
    logo_path.write_bytes(logo_bytes)
    return ImageProcessor(
        logo_path=str(logo_path),
        position="bottom-right",
        opacity=0.4,
        scale=0.15,
    )


class TestWatermark:
    def test_add_watermark_returns_valid_image(
        self, processor: ImageProcessor, sample_image_bytes: bytes
    ):
        result = processor.add_watermark(sample_image_bytes)
        assert result is not None
        img = Image.open(io.BytesIO(result))
        assert img.size == (800, 600)

    def test_watermark_changes_image(
        self, processor: ImageProcessor, sample_image_bytes: bytes
    ):
        result = processor.add_watermark(sample_image_bytes)
        assert result != sample_image_bytes

    def test_watermark_bottom_right_position(
        self, processor: ImageProcessor, sample_image_bytes: bytes
    ):
        result = processor.add_watermark(sample_image_bytes)
        img = Image.open(io.BytesIO(result))
        # Bottom-right corner should no longer be pure blue
        pixel = img.getpixel((790, 590))
        assert pixel != (0, 0, 255), "Watermark should modify bottom-right area"

    def test_output_is_jpeg(self, processor: ImageProcessor, sample_image_bytes: bytes):
        result = processor.add_watermark(sample_image_bytes)
        img = Image.open(io.BytesIO(result))
        assert img.format == "JPEG"

    def test_large_image_gets_resized(self, processor: ImageProcessor):
        """Images over max dimension should be resized."""
        big_img = Image.new("RGB", (10000, 10000), (0, 255, 0))
        buf = io.BytesIO()
        big_img.save(buf, format="JPEG", quality=95)
        big_bytes = buf.getvalue()

        result = processor.add_watermark(big_bytes)
        result_img = Image.open(io.BytesIO(result))
        assert result_img.width <= 4096
        assert len(result) < 10_000_000


class TestImageHash:
    def test_same_image_same_hash(self, sample_image_bytes: bytes):
        hash1 = compute_image_hash(sample_image_bytes)
        hash2 = compute_image_hash(sample_image_bytes)
        assert hash1 == hash2

    def test_different_images_different_hash(self, sample_image_bytes: bytes):
        # Use an image with actual visual structure (gradient) so dhash produces
        # meaningful non-zero hashes. Uniform-color images always hash to
        # all-zeros with dhash because there are no pixel-to-pixel differences.
        import numpy as np

        arr = np.arange(800 * 600, dtype=np.uint8).reshape((600, 800))
        other = Image.fromarray(arr, mode="L").convert("RGB")
        buf = io.BytesIO()
        other.save(buf, format="JPEG")

        hash1 = compute_image_hash(sample_image_bytes)
        hash2 = compute_image_hash(buf.getvalue())
        assert hash1 != hash2

    def test_hash_is_hex_string(self, sample_image_bytes: bytes):
        h = compute_image_hash(sample_image_bytes)
        assert isinstance(h, str)
        int(h, 16)  # Should not raise
