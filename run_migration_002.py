#!/usr/bin/env python3
"""
Run migration 002_add_summary_type.sql on PostgreSQL (Render)
- Works whether the SQL file contains its own BEGIN/COMMIT or not
- Prints clear verification of new columns
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
    migration_path = here / "migrations" / "002_add_summary_type.sql"
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

    # ---- Verify new columns exist ----
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT table_name, column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name IN ('content', 'content_summaries')
                  AND column_name LIKE '%summary_type%'
                ORDER BY table_name, column_name;
            """)
            rows = cur.fetchall()

        if not rows:
            print("⚠️  No summary_type columns found after migration.")
        else:
            print("\n📋 New/updated columns:")
            for table, col, dtype, nullable in rows:
                print(f"   {table}.{col} ({dtype}, nullable={nullable})")
    finally:
        conn.close()

    return True

if __name__ == "__main__":
    ok = run_migration()
    sys.exit(0 if ok else 1)