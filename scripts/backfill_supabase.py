"""One-time script to backfill existing deals from SQLite to Supabase.

Usage:
    python scripts/backfill_supabase.py [--days 7] [--dry-run]
"""

from __future__ import annotations

import argparse
import datetime
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from loguru import logger
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from bot.exchange_rate import get_cached_rate
from bot.models import Base, Deal


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill deals to Supabase")
    parser.add_argument("--days", type=int, default=7, help="Days of history to backfill")
    parser.add_argument("--dry-run", action="store_true", help="Print without uploading")
    args = parser.parse_args()

    load_dotenv()

    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not supabase_url or not supabase_key:
        logger.error("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in .env")
        sys.exit(1)

    from supabase import create_client

    sb = create_client(supabase_url, supabase_key)
    bucket = "deal-images"

    engine = create_engine("sqlite:///data/deals.db")
    session_factory = sessionmaker(bind=engine)
    session: Session = session_factory()

    cutoff = datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=args.days)
    deals = session.execute(
        select(Deal)
        .where(Deal.created_at >= cutoff)
        .order_by(Deal.created_at.desc())
    ).scalars().all()

    logger.info(f"Found {len(deals)} deals from the last {args.days} days")

    rate = get_cached_rate()
    uploaded = 0
    skipped = 0
    errors = 0

    for deal in deals:
        if not deal.product_id:
            skipped += 1
            continue

        if args.dry_run:
            logger.info(f"[DRY RUN] Would upload: {deal.product_id} - {deal.product_name}")
            uploaded += 1
            continue

        try:
            image_url = None
            if deal.image_path:
                image_file = Path(deal.image_path)
                if image_file.exists():
                    storage_path = f"{deal.product_id}.jpg"
                    try:
                        sb.storage.from_(bucket).remove([storage_path])
                    except Exception:
                        pass
                    sb.storage.from_(bucket).upload(
                        storage_path,
                        image_file.read_bytes(),
                        file_options={"content-type": "image/jpeg"},
                    )
                    image_url = sb.storage.from_(bucket).get_public_url(storage_path)

            price_ils = None
            if deal.currency == "USD" and deal.price:
                price_ils = round(deal.price * rate, 2)
            elif deal.currency == "ILS" and deal.price:
                price_ils = deal.price

            row = {
                "product_id": deal.product_id,
                "product_name": deal.product_name,
                "rewritten_text": deal.rewritten_text,
                "price": float(deal.price) if deal.price else 0,
                "original_price": float(deal.original_price) if deal.original_price else None,
                "currency": deal.currency,
                "price_ils": price_ils,
                "category": deal.category or "other",
                "affiliate_link": deal.affiliate_link,
                "product_link": deal.product_link,
                "image_url": image_url,
                "is_active": True,
                "published_at": deal.created_at.isoformat() if deal.created_at else None,
            }

            sb.table("deals").upsert(row, on_conflict="product_id").execute()
            uploaded += 1
            logger.info(f"Uploaded: {deal.product_id} - {deal.product_name[:40]}")

        except Exception as e:
            errors += 1
            logger.error(f"Failed to upload {deal.product_id}: {e}")

    session.close()
    logger.info(f"Backfill complete: {uploaded} uploaded, {skipped} skipped, {errors} errors")


if __name__ == "__main__":
    main()
