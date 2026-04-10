import datetime
import json
import io
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from PIL import Image
from sqlalchemy import select

from bot.pipeline import Pipeline
from bot.models import RawMessage, Deal, PublishQueueItem
from bot.parser import DealParser
from bot.dedup import DuplicateChecker
from bot.resolver import LinkResolver
from bot.rewriter import ContentRewriter, RewriteResult
from bot.image_processor import ImageProcessor


def _make_test_image() -> bytes:
    img = Image.new("RGB", (200, 200), (0, 0, 255))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


@pytest.fixture
def pipeline_deps(db_session, tmp_path):
    """Create pipeline with mocked external deps."""
    parser = DealParser(min_message_length=20, supported_domains=["aliexpress.com", "s.click.aliexpress.com"])

    dedup = DuplicateChecker(session=db_session, window_hours=24, image_hash_threshold=5)

    resolver = LinkResolver()
    resolver.resolve = AsyncMock(return_value="1005003091506814")

    rewriter = ContentRewriter(api_key="test", model="test")
    rewriter.rewrite = AsyncMock(
        return_value=RewriteResult(
            rewritten_text="🔥 מוצר מעולה!",
            category="tech",
            product_name_clean="test product",
        )
    )

    # Create logo for image processor
    logo_path = tmp_path / "logo.png"
    logo = Image.new("RGBA", (50, 50), (255, 0, 0, 200))
    logo.save(str(logo_path), "PNG")
    image_proc = ImageProcessor(logo_path=str(logo_path))

    target_groups = {"default": "@my_channel"}
    notifier = MagicMock()
    notifier.notify_error = AsyncMock()

    return {
        "parser": parser,
        "dedup": dedup,
        "resolver": resolver,
        "rewriter": rewriter,
        "image_processor": image_proc,
        "session": db_session,
        "target_groups": target_groups,
        "notifier": notifier,
    }


@pytest.fixture
def pipeline(pipeline_deps, tmp_path) -> Pipeline:
    return Pipeline(**pipeline_deps, image_dir=str(tmp_path / "images"))


@pytest.mark.asyncio
class TestPipeline:
    async def test_full_pipeline_creates_deal_and_queue_item(
        self, pipeline: Pipeline, db_session
    ):
        text = "Amazing earbuds! https://s.click.aliexpress.com/e/_abc123 only ₪45 free shipping"
        images = [_make_test_image()]

        await pipeline.process(
            text=text,
            images=images,
            source_group="@deals_il",
            telegram_message_id=12345,
        )

        # Should create a raw message
        raw = db_session.execute(select(RawMessage)).scalar_one()
        assert raw.status == "processed"

        # Should create a deal
        deal = db_session.execute(select(Deal)).scalar_one()
        assert deal.rewritten_text == "🔥 מוצר מעולה!"
        assert deal.category == "tech"
        assert deal.price == 45.0

        # Should enqueue for publishing
        queue = db_session.execute(select(PublishQueueItem)).scalar_one()
        assert queue.status == "queued"
        assert queue.target_group == "@my_channel"

    async def test_duplicate_deal_skips_publishing(
        self, pipeline: Pipeline, db_session
    ):
        text = "Deal! https://s.click.aliexpress.com/e/_abc ₪45 great product"
        images = [_make_test_image()]

        # Process first time
        await pipeline.process(text=text, images=images, source_group="@g1", telegram_message_id=1)
        # Process same deal again
        await pipeline.process(text=text, images=images, source_group="@g2", telegram_message_id=2)

        # Should have 2 raw messages
        raws = db_session.execute(select(RawMessage)).scalars().all()
        assert len(raws) == 2

        # But only 1 deal and 1 queue item
        deals = db_session.execute(select(Deal)).scalars().all()
        assert len(deals) == 1

    async def test_no_link_message_skips(self, pipeline: Pipeline, db_session):
        text = "This is a general message without any deal link at all"

        await pipeline.process(text=text, images=[], source_group="@g1", telegram_message_id=3)

        raw = db_session.execute(select(RawMessage)).scalar_one()
        assert raw.status == "processed"

        deals = db_session.execute(select(Deal)).scalars().all()
        assert len(deals) == 0

    async def test_resolver_failure_continues_without_product_id(
        self, pipeline: Pipeline, pipeline_deps, db_session
    ):
        pipeline_deps["resolver"].resolve = AsyncMock(return_value=None)

        text = "Good deal https://s.click.aliexpress.com/e/_fail ₪30 cheap"

        await pipeline.process(text=text, images=[], source_group="@g1", telegram_message_id=4)

        deal = db_session.execute(select(Deal)).scalar_one()
        assert deal.product_id is None
        assert deal.price == 30.0
