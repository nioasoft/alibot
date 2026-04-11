"""One-time SQLite migration for destination routing and affiliate metadata."""

from __future__ import annotations

import sqlite3
from pathlib import Path


DB_PATH = Path("data/deals.db")


def _column_exists(cursor: sqlite3.Cursor, table: str, column: str) -> bool:
    rows = cursor.execute(f"PRAGMA table_info({table})").fetchall()
    return any(row[1] == column for row in rows)


def main() -> None:
    if not DB_PATH.exists():
        print(f"Database not found: {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    deal_columns = {
        "ali_category_raw": "ALTER TABLE deals ADD COLUMN ali_category_raw TEXT",
        "category_source": "ALTER TABLE deals ADD COLUMN category_source TEXT",
        "affiliate_account_key": "ALTER TABLE deals ADD COLUMN affiliate_account_key TEXT",
    }
    for column, ddl in deal_columns.items():
        if not _column_exists(cur, "deals", column):
            cur.execute(ddl)

    queue_columns = {
        "destination_key": "ALTER TABLE publish_queue ADD COLUMN destination_key TEXT DEFAULT 'legacy_default'",
        "platform": "ALTER TABLE publish_queue ADD COLUMN platform TEXT DEFAULT 'telegram'",
        "target_ref": "ALTER TABLE publish_queue ADD COLUMN target_ref TEXT DEFAULT ''",
    }
    for column, ddl in queue_columns.items():
        if not _column_exists(cur, "publish_queue", column):
            cur.execute(ddl)

    cur.execute(
        "UPDATE publish_queue "
        "SET destination_key = COALESCE(destination_key, 'legacy_default'), "
        "platform = COALESCE(platform, 'telegram'), "
        "target_ref = CASE "
        "WHEN target_ref IS NULL OR target_ref = '' THEN target_group "
        "ELSE target_ref END"
    )

    cur.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_queue_deal_destination "
        "ON publish_queue(deal_id, destination_key)"
    )
    conn.commit()
    conn.close()
    print("Migration completed.")


if __name__ == "__main__":
    main()
