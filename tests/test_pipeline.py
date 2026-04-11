import io
from unittest.mock import AsyncMock, MagicMock

import pytest
from PIL import Image
from sqlalchemy import select

from bot.category_resolver import CategoryResolution
from bot.dedup import DuplicateChecker
from bot.image_processor import ImageProcessor
from bot.models import Deal, PublishQueueItem, RawMessage
from bot.parser import DealParser
from bot.pipeline import Pipeline
from bot.resolver import LinkResolver
from bot.rewriter import ContentRewriter, RewriteResult


def _make_test_image() -> bytes:
    img = Image.new("RGB", (200, 200), (0, 0, 255))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


@pytest.fixture
def pipeline_deps(db_session, tmp_path):
    parser = DealParser(
        min_message_length=20,
        supported_domains=["aliexpress.com", "s.click.aliexpress.com"],
    )
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

    logo_path = tmp_path / "logo.png"
    Image.new("RGBA", (50, 50), (255, 0, 0, 200)).save(str(logo_path), "PNG")
    image_proc = ImageProcessor(logo_path=str(logo_path))

    router = MagicMock()
    router.resolve.return_value = [
        MagicMock(key="tg_main", platform="telegram", target="@my_channel")
    ]

    category_resolver = MagicMock()
    category_resolver.resolve = AsyncMock(
        return_value=CategoryResolution(
            category="tech",
            source="api",
            ali_category_raw="Consumer Electronics",
        )
    )

    affiliate_pool = MagicMock()
    affiliate_pool.get_affiliate_link.return_value = ("https://aff.link", "primary")

    notifier = MagicMock()
    notifier.notify_error = AsyncMock()

    return {
        "parser": parser,
        "dedup": dedup,
        "resolver": resolver,
        "rewriter": rewriter,
        "image_processor": image_proc,
        "session": db_session,
        "router": router,
        "category_resolver": category_resolver,
        "notifier": notifier,
        "affiliate_pool": affiliate_pool,
    }


@pytest.fixture
def pipeline(pipeline_deps, tmp_path) -> Pipeline:
    return Pipeline(**pipeline_deps, image_dir=str(tmp_path / "images"))


@pytest.mark.asyncio
class TestPipeline:
    async def test_full_pipeline_creates_deal_and_queue_item(self, pipeline: Pipeline, db_session):
        text = "Amazing earbuds! https://s.click.aliexpress.com/e/_abc123 only ₪45 free shipping"

        await pipeline.process(
            text=text,
            images=[_make_test_image()],
            source_group="@deals_il",
            telegram_message_id=12345,
        )

        raw = db_session.execute(select(RawMessage)).scalar_one()
        assert raw.status == "processed"

        deal = db_session.execute(select(Deal)).scalar_one()
        assert deal.rewritten_text == "🔥 מוצר מעולה!"
        assert deal.category == "tech"
        assert deal.price == 45.0
        assert deal.ali_category_raw == "Consumer Electronics"
        assert deal.category_source == "api"
        assert deal.affiliate_account_key == "primary"
        assert deal.affiliate_link == "https://aff.link"

        queue = db_session.execute(select(PublishQueueItem)).scalar_one()
        assert queue.status == "queued"
        assert queue.target_group == "@my_channel"
        assert queue.platform == "telegram"
        assert queue.destination_key == "tg_main"

    async def test_duplicate_deal_skips_publishing(self, pipeline: Pipeline, db_session):
        text = "Deal! https://s.click.aliexpress.com/e/_abc ₪45 great product"
        image = _make_test_image()

        await pipeline.process(text=text, images=[image], source_group="@g1", telegram_message_id=1)
        await pipeline.process(text=text, images=[image], source_group="@g2", telegram_message_id=2)

        raws = db_session.execute(select(RawMessage)).scalars().all()
        assert len(raws) == 2
        assert len(db_session.execute(select(Deal)).scalars().all()) == 1
        assert len(db_session.execute(select(PublishQueueItem)).scalars().all()) == 1

    async def test_no_link_message_skips(self, pipeline: Pipeline, db_session):
        await pipeline.process(
            text="This is a general message without any deal link at all",
            images=[],
            source_group="@g1",
            telegram_message_id=3,
        )

        raw = db_session.execute(select(RawMessage)).scalar_one()
        assert raw.status == "processed"
        assert db_session.execute(select(Deal)).scalars().all() == []

    async def test_resolver_failure_continues_without_product_id(
        self, pipeline: Pipeline, pipeline_deps, db_session
    ):
        pipeline_deps["resolver"].resolve = AsyncMock(return_value=None)
        pipeline_deps["category_resolver"].resolve = AsyncMock(
            return_value=CategoryResolution(category="other", source="llm_fallback")
        )
        pipeline_deps["affiliate_pool"].get_affiliate_link.return_value = (None, None)

        fresh_pipeline = Pipeline(**pipeline_deps)
        await fresh_pipeline.process(
            text="Good deal https://s.click.aliexpress.com/e/_fail ₪30 cheap",
            images=[],
            source_group="@g1",
            telegram_message_id=4,
        )

        deal = db_session.execute(select(Deal)).scalar_one()
        assert deal.product_id is None
        assert deal.price == 30.0
        assert deal.category == "other"
