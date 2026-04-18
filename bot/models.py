"""SQLAlchemy ORM models for the deal pipeline."""

import datetime

from sqlalchemy import Index, ForeignKey, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker, Session


class Base(DeclarativeBase):
    pass


class RawMessage(Base):
    __tablename__ = "raw_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_group: Mapped[str]
    telegram_message_id: Mapped[int]
    raw_text: Mapped[str]
    has_images: Mapped[bool]
    received_at: Mapped[datetime.datetime]
    status: Mapped[str]  # pending / processed / failed
    error_message: Mapped[str | None]


class Deal(Base):
    __tablename__ = "deals"

    id: Mapped[int] = mapped_column(primary_key=True)
    raw_message_id: Mapped[int] = mapped_column(ForeignKey("raw_messages.id"))
    product_id: Mapped[str | None] = mapped_column(unique=True)
    product_name: Mapped[str]
    original_text: Mapped[str]
    rewritten_text: Mapped[str]
    price: Mapped[float]
    original_price: Mapped[float | None]
    currency: Mapped[str]
    shipping: Mapped[str | None]
    category: Mapped[str]
    ali_category_raw: Mapped[str | None]
    category_source: Mapped[str | None]
    affiliate_account_key: Mapped[str | None]
    affiliate_link: Mapped[str | None]
    product_link: Mapped[str]
    image_hash: Mapped[str | None]
    image_path: Mapped[str | None]  # path to processed watermarked image on disk
    text_hash: Mapped[str]
    source_group: Mapped[str]
    created_at: Mapped[datetime.datetime]

    __table_args__ = (
        Index("idx_deals_image_hash", "image_hash"),
        Index("idx_deals_text_hash", "text_hash"),
        Index("idx_deals_created_at", "created_at"),
    )


class PublishQueueItem(Base):
    __tablename__ = "publish_queue"

    id: Mapped[int] = mapped_column(primary_key=True)
    deal_id: Mapped[int] = mapped_column(ForeignKey("deals.id"))
    target_group: Mapped[str]
    destination_key: Mapped[str] = mapped_column(default="legacy_default")
    platform: Mapped[str] = mapped_column(default="telegram")
    target_ref: Mapped[str] = mapped_column(default="")
    status: Mapped[str]  # queued / publishing / published / failed
    priority: Mapped[int] = mapped_column(default=0)
    scheduled_after: Mapped[datetime.datetime]
    published_at: Mapped[datetime.datetime | None]
    message_id: Mapped[int | None]
    error_message: Mapped[str | None]

    __table_args__ = (
        Index("idx_queue_status_scheduled", "status", "scheduled_after"),
        Index("idx_queue_deal_destination", "deal_id", "destination_key", unique=True),
    )


class DailyStat(Base):
    __tablename__ = "daily_stats"

    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[datetime.date] = mapped_column(unique=True)
    deals_seen: Mapped[int] = mapped_column(default=0)
    deals_processed: Mapped[int] = mapped_column(default=0)
    deals_published: Mapped[int] = mapped_column(default=0)
    deals_skipped_dup: Mapped[int] = mapped_column(default=0)
    deals_skipped_error: Mapped[int] = mapped_column(default=0)
    api_calls: Mapped[int] = mapped_column(default=0)


class AffiliateLinkToken(Base):
    __tablename__ = "affiliate_link_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    token: Mapped[str] = mapped_column(unique=True)
    deal_id: Mapped[int] = mapped_column(ForeignKey("deals.id"))
    queue_item_id: Mapped[int] = mapped_column(ForeignKey("publish_queue.id"), unique=True)
    destination_key: Mapped[str]
    platform: Mapped[str]
    source_group: Mapped[str]
    affiliate_account_key: Mapped[str | None]
    tracking_id: Mapped[str | None]
    custom_parameters: Mapped[str | None]
    target_url: Mapped[str]
    created_at: Mapped[datetime.datetime]

    __table_args__ = (
        Index("idx_affiliate_link_tokens_queue_item", "queue_item_id"),
        Index("idx_affiliate_link_tokens_deal", "deal_id"),
    )


class AffiliateClickEvent(Base):
    __tablename__ = "affiliate_click_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    token_id: Mapped[int] = mapped_column(ForeignKey("affiliate_link_tokens.id"))
    deal_id: Mapped[int] = mapped_column(ForeignKey("deals.id"))
    queue_item_id: Mapped[int] = mapped_column(ForeignKey("publish_queue.id"))
    destination_key: Mapped[str]
    platform: Mapped[str]
    source_group: Mapped[str]
    clicked_at: Mapped[datetime.datetime]
    ip_hash: Mapped[str | None]
    user_agent: Mapped[str | None]
    referer: Mapped[str | None]

    __table_args__ = (
        Index("idx_affiliate_click_events_clicked_at", "clicked_at"),
        Index("idx_affiliate_click_events_token_id", "token_id"),
        Index("idx_affiliate_click_events_queue_item_id", "queue_item_id"),
    )


def init_db(db_path: str) -> sessionmaker[Session]:
    """Create engine, ensure tables exist, return session factory.

    @param db_path - Path to the SQLite database file
    @returns Session factory bound to the created engine
    """
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)
