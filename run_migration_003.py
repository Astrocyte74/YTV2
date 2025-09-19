#!/usr/bin/env python3
"""
Run migration 003_index_summary_type.sql on PostgreSQL (Render)
- Adds performance index for summary_type filtering
- Works whether the SQL file contains its own BEGIN/COMMIT or not
"""

import os
import sys
from pathlib import Path
from urllib.parse import urlparse

def run_migration() -> bool:
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

    print(f"🔗 Connecting to PostgreSQL host={url.hostname} db={db_name} user={url.username}")

    # ---- Connect (Render requires SSL) ----
    conn = psycopg2.connect(
        host=url.hostname,
        port=url.port or 5432,
        database=db_name,
        user=url.username,
        password=url.password,
        sslmode="require",
    )
    try:
        with conn.cursor() as cur:
            # keep migrations snappy and avoid hangs
            cur.execute("SET statement_timeout = '30s';")
            conn.commit()
    except Exception:
        conn.close()
        raise

    # ---- Load SQL file (relative to this script) ----
    here = Path(__file__).resolve().parent
    migration_path = here / "migrations" / "003_index_summary_type.sql"
    if not migration_path.exists():
        print(f"❌ Migration file not found: {migration_path}")
        conn.close()
        return False

    migration_sql = migration_path.read_text(encoding="utf-8")
    print(f"📦 Running migration: {migration_path.name}")

    # ---- Execute respecting BEGIN/COMMIT in file ----
    contains_txn = ("BEGIN" in migration_sql.upper()) or ("COMMIT" in migration_sql.upper())
    try:
        if contains_txn:
            # Let the file manage its own transaction blocks
            conn.set_session(autocommit=True)
            with conn.cursor() as cur:
                cur.execute(migration_sql)
            print("✅ Migration executed (file contained its own BEGIN/COMMIT)")
        else:
            # Wrap in a single transaction here
            conn.set_session(autocommit=False)
            with conn.cursor() as cur:
                cur.execute(migration_sql)
            conn.commit()
            print("✅ Migration executed (wrapped in single transaction)")
    except Exception as e:
        # helpful debugging
        snippet = migration_sql.strip().replace("\n", " ")[:200]
        print(f"❌ Migration failed: {e}\n   SQL (first 200 chars): {snippet!r}")
        conn.close()
        return False

    # ---- Verify index was created ----
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT indexname, tablename
                FROM pg_indexes
                WHERE tablename = 'content'
                  AND indexname LIKE '%summary_type%'
                ORDER BY indexname;
            """)
            indexes = cur.fetchall()

        if not indexes:
            print("⚠️  No summary_type indexes found after migration.")
        else:
            print("\n📋 Summary type indexes:")
            for index_name, table_name in indexes:
                print(f"   {table_name}.{index_name}")
    finally:
        conn.close()

    return True

if __name__ == "__main__":
    ok = run_migration()
    sys.exit(0 if ok else 1)