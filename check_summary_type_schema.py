#!/usr/bin/env python3
"""
Check summary_type schema on PostgreSQL database
Useful for verifying migration status before/after running migrations
"""

import os
import sys
from urllib.parse import urlparse

def check_schema() -> bool:
    try:
        import psycopg2
    except ImportError:
        print("❌ psycopg2 not available - install with: pip install psycopg2-binary")
        return False

    # ---- Resolve DB URL (fallback to *_NEW for your env) ----
    database_url = (
        os.getenv("DATABASE_URL")
        or os.getenv("DATABASE_URL_POSTGRES_NEW")
    )
    if not database_url:
        print("❌ No DATABASE_URL (or DATABASE_URL_POSTGRES_NEW) in environment")
        return False

    url = urlparse(database_url)
    db_name = (url.path[1:] if url.path.startswith("/") else url.path) or None

    print(f"🔗 Checking schema on PostgreSQL host={url.hostname} db={db_name}")

    # ---- Connect and check schema ----
    try:
        conn = psycopg2.connect(database_url, sslmode="require")
        cur = conn.cursor()

        cur.execute("""
            SELECT table_name, column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name IN ('content','content_summaries')
              AND column_name LIKE '%summary_type%'
            ORDER BY table_name, column_name;
        """)

        rows = cur.fetchall()

        if rows:
            print("✅ Found summary_type columns:")
            for table, column, dtype, nullable in rows:
                print(f"   - {table}.{column} ({dtype}, nullable={nullable})")
        else:
            print("⚠️  No summary_type columns present yet.")

        # Also check for existing summary data to help with backfill planning
        cur.execute("""
            SELECT COUNT(*) as total_summaries,
                   COUNT(CASE WHEN variant IS NOT NULL THEN 1 END) as with_variant
            FROM content_summaries;
        """)
        summary_stats = cur.fetchone()

        cur.execute("SELECT COUNT(*) FROM content;")
        content_count = cur.fetchone()[0]

        print(f"\n📊 Current data counts:")
        print(f"   - content records: {content_count:,}")
        print(f"   - summary records: {summary_stats[0]:,} (variants: {summary_stats[1]:,})")

        cur.close()
        conn.close()
        return True

    except Exception as e:
        print(f"❌ Schema check failed: {e}")
        return False

if __name__ == "__main__":
    ok = check_schema()
    sys.exit(0 if ok else 1)