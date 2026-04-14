import io
import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from PIL import Image
from sqlalchemy import select

from bot.category_resolver import CategoryResolution
from bot.aliexpress_client import ProductDetails, PromoCode
from bot.dedup import DuplicateChecker
from bot.image_processor import ImageProcessor
from bot.models import Deal, PublishQueueItem, RawMessage
from bot.parser import DealParser
from bot.pipeline import Pipeline
from bot.quality import QualityDecision
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

    quality_gate = MagicMock()
    quality_gate.evaluate_pipeline.return_value = QualityDecision(
        accepted=True,
        score=82,
        priority=82,
        reason="quality_pass",
    )
    quality_gate.idle_destination_hours = 6

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
        "quality_gate": quality_gate,
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
        assert deal.rewritten_text == "🔥 מוצר מעולה!\n💰 מחיר: ₪45\n🚚 משלוח חינם"
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
        assert queue.priority == 82

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

    async def test_duplicate_integrity_error_rolls_back_cleanly(
        self, pipeline: Pipeline, pipeline_deps, db_session
    ):
        pipeline_deps["dedup"].is_duplicate = MagicMock(return_value=False)
        duplicate = Deal(
            raw_message_id=0,
            product_id="1005003091506814",
            product_name="existing product",
            original_text="existing",
            rewritten_text="existing",
            price=10.0,
            original_price=None,
            currency="USD",
            shipping=None,
            category="tech",
            ali_category_raw="Consumer Electronics",
            category_source="api",
            affiliate_account_key="primary",
            affiliate_link="https://aff.link/existing",
            product_link="https://www.aliexpress.com/item/1005003091506814.html",
            image_hash=None,
            image_path=None,
            text_hash="existing-hash",
            source_group="@seed",
            created_at=datetime.datetime.now(datetime.UTC),
        )
        db_session.add(duplicate)
        db_session.commit()

        fresh_pipeline = Pipeline(**pipeline_deps)
        result = await fresh_pipeline.process(
            text="Deal! https://s.click.aliexpress.com/e/_abc ₪45 great product",
            images=[_make_test_image()],
            source_group="@g1",
            telegram_message_id=99,
        )

        assert result is None
        raws = db_session.execute(select(RawMessage)).scalars().all()
        assert len(raws) == 1
        assert raws[0].status == "skipped_duplicate"
        assert len(db_session.execute(select(Deal)).scalars().all()) == 1
        assert len(db_session.execute(select(PublishQueueItem)).scalars().all()) == 0

    async def test_low_quality_external_deal_is_skipped(
        self, pipeline_deps, db_session
    ):
        pipeline_deps["quality_gate"].evaluate_pipeline.return_value = QualityDecision(
            accepted=False,
            score=20,
            priority=20,
            reason="quality_below_threshold",
        )

        fresh_pipeline = Pipeline(**pipeline_deps)
        result = await fresh_pipeline.process(
            text="Deal! https://s.click.aliexpress.com/e/_abc ₪45 great product",
            images=[],
            source_group="@g1",
            telegram_message_id=100,
        )

        assert result is None
        assert db_session.execute(select(Deal)).scalars().all() == []
        raw = db_session.execute(select(RawMessage)).scalar_one()
        assert raw.status == "processed"

    async def test_manual_deal_gets_high_priority(
        self, pipeline_deps, db_session
    ):
        pipeline_deps["quality_gate"].evaluate_pipeline.return_value = QualityDecision(
            accepted=True,
            score=100,
            priority=1000,
            reason="manual_source",
            is_manual=True,
        )

        fresh_pipeline = Pipeline(**pipeline_deps)
        await fresh_pipeline.process(
            text="Deal! https://s.click.aliexpress.com/e/_abc ₪45 great product",
            images=[],
            source_group="הכנסת דילים ידנית",
            telegram_message_id=101,
        )

        queue = db_session.execute(select(PublishQueueItem)).scalar_one()
        assert queue.priority == 1000

    async def test_idle_destination_override_accepts_low_score(
        self, pipeline_deps, db_session
    ):
        pipeline_deps["quality_gate"].evaluate_pipeline.return_value = QualityDecision(
            accepted=True,
            score=25,
            priority=175,
            reason="idle_destination_override",
        )

        fresh_pipeline = Pipeline(**pipeline_deps)
        await fresh_pipeline.process(
            text="Deal! https://s.click.aliexpress.com/e/_abc ₪45 great product",
            images=[],
            source_group="@g1",
            telegram_message_id=102,
        )

        queue = db_session.execute(select(PublishQueueItem)).scalar_one()
        assert queue.priority == 175

    async def test_pipeline_merges_source_and_api_coupons_and_prefers_app_price(
        self, pipeline_deps, db_session
    ):
        ali_client = MagicMock()
        ali_client.is_enabled = True
        ali_client.get_product_details.return_value = ProductDetails(
            title="Smart Camera",
            price=82.13,
            sale_price=38.6,
            app_sale_price=30.94,
            currency="USD",
            images=[],
            rating=4.9,
            orders_count=1000,
            commission_rate=8.0,
            category="Security & Protection",
            promo_codes=[PromoCode(code="SAVE7", value="On order over USD 10, get USD 7 off")],
        )

        fresh_pipeline = Pipeline(**pipeline_deps, aliexpress_client=ali_client)
        await fresh_pipeline.process(
            text=(
                "מצלמה מעולה https://www.aliexpress.com/item/1005006904717349.html\n"
                "קוד הנחה: ILAPR2 או DSB2\n"
                "משלוח מהיר"
            ),
            images=[],
            source_group="@g1",
            telegram_message_id=103,
        )

        deal = db_session.execute(select(Deal)).scalar_one()
        assert deal.price == 30.94
        assert "🎟️ קוד הנחה: SAVE7 - On order over USD 10, get USD 7 off" in deal.rewritten_text
        assert "🎟️ קוד הנחה: ILAPR2, DSB2" in deal.rewritten_text
        assert "🚚 משלוח מהיר" in deal.rewritten_text
