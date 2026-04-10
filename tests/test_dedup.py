import datetime
import hashlib
import pytest

from bot.dedup import DuplicateChecker
from bot.models import Deal


@pytest.fixture
def dedup(db_session):
    return DuplicateChecker(session=db_session, window_hours=24, image_hash_threshold=5)


def _make_deal(db_session, **overrides) -> Deal:
    defaults = dict(
        raw_message_id=1,
        product_name="Test Product",
        original_text="orig",
        rewritten_text="new",
        price=10.0,
        currency="ILS",
        category="tech",
        product_link="https://aliexpress.com/item/123.html",
        text_hash=hashlib.md5(b"test product").hexdigest(),
        source_group="@test",
        created_at=datetime.datetime.now(datetime.UTC),
    )
    defaults.update(overrides)
    deal = Deal(**defaults)
    db_session.add(deal)
    db_session.commit()
    return deal


class TestProductIdDedup:
    def test_same_product_id_is_duplicate(self, dedup: DuplicateChecker, db_session):
        _make_deal(db_session, product_id="12345")
        assert dedup.is_duplicate(product_id="12345") is True

    def test_different_product_id_not_duplicate(self, dedup: DuplicateChecker, db_session):
        _make_deal(db_session, product_id="12345")
        assert dedup.is_duplicate(product_id="99999") is False

    def test_none_product_id_skips_check(self, dedup: DuplicateChecker):
        assert dedup.is_duplicate(product_id=None) is False


class TestTextHashDedup:
    def test_same_text_hash_is_duplicate(self, dedup: DuplicateChecker, db_session):
        text_hash = hashlib.md5(b"wireless earbuds bluetooth").hexdigest()
        _make_deal(db_session, product_id=None, text_hash=text_hash)
        assert dedup.is_duplicate(text_hash=text_hash) is True

    def test_different_text_hash_not_duplicate(self, dedup: DuplicateChecker, db_session):
        _make_deal(db_session, product_id=None, text_hash="aaa")
        assert dedup.is_duplicate(text_hash="bbb") is False


class TestImageHashDedup:
    def test_similar_image_hash_is_duplicate(self, dedup: DuplicateChecker, db_session):
        # dhash values with small hamming distance
        _make_deal(db_session, product_id=None, image_hash="0a1b2c3d4e5f6a7b")
        assert dedup.is_duplicate(image_hash="0a1b2c3d4e5f6a7c") is True

    def test_very_different_image_hash_not_duplicate(self, dedup: DuplicateChecker, db_session):
        _make_deal(db_session, product_id=None, image_hash="0000000000000000")
        assert dedup.is_duplicate(image_hash="ffffffffffffffff") is False


class TestWindowExpiry:
    def test_old_deal_outside_window_not_duplicate(self, dedup: DuplicateChecker, db_session):
        old_time = datetime.datetime.now(datetime.UTC) - datetime.timedelta(hours=25)
        _make_deal(db_session, product_id="old_deal", created_at=old_time)
        assert dedup.is_duplicate(product_id="old_deal") is False


class TestCleanup:
    def test_cleanup_removes_old_entries(self, dedup: DuplicateChecker, db_session):
        old_time = datetime.datetime.now(datetime.UTC) - datetime.timedelta(hours=25)
        _make_deal(db_session, product_id="old1", created_at=old_time)
        _make_deal(db_session, product_id="new1", created_at=datetime.datetime.now(datetime.UTC))

        from sqlalchemy import select, func
        from bot.models import Deal
        count_before = db_session.execute(select(func.count()).select_from(Deal)).scalar()
        assert count_before == 2

        dedup.cleanup_old()

        count_after = db_session.execute(select(func.count()).select_from(Deal)).scalar()
        assert count_after == 1
