#!/usr/bin/env python3
"""
Discover actual PostgreSQL schema on Render
This script examines all tables and their columns to understand the real structure
"""

import os
from urllib.parse import urlparse

def discover_schema():
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
    except ImportError:
        print("❌ psycopg2 not available - install with: pip install psycopg2-binary")
        return False

    # Get database URL
    database_url = (
        os.getenv("DATABASE_URL")
        or os.getenv("DATABASE_URL_POSTGRES_NEW")
    )
    if not database_url:
        print("❌ No DATABASE_URL found in environment")
        return False

    url = urlparse(database_url)
    db_name = (url.path[1:] if url.path.startswith("/") else url.path) or None

    print(f"🔗 Connecting to PostgreSQL host={url.hostname} db={db_name}")

    # Connect to database
    conn = psycopg2.connect(
        host=url.hostname,
        port=url.port or 5432,
        database=db_name,
        user=url.username,
        password=url.password,
        sslmode="require",
    )

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Discover all tables
            print("\n📋 Discovering all tables...")
            cur.execute("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                ORDER BY table_name;
            """)

            tables = cur.fetchall()
            print(f"Found {len(tables)} tables:")
            for table in tables:
                print(f"  - {table['table_name']}")

            # Get detailed info for each table
            for table in tables:
                table_name = table['table_name']
                print(f"\n🔍 Table: {table_name}")
                print("=" * 50)

                # Get column info
                cur.execute("""
                    SELECT
                        column_name,
                        data_type,
                        is_nullable,
                        column_default
                    FROM information_schema.columns
                    WHERE table_name = %s
                    ORDER BY ordinal_position;
                """, (table_name,))

                columns = cur.fetchall()
                print("Columns:")
                for col in columns:
                    nullable = "NULL" if col['is_nullable'] == 'YES' else "NOT NULL"
                    default = f" DEFAULT {col['column_default']}" if col['column_default'] else ""
                    print(f"  {col['column_name']:<25} {col['data_type']:<15} {nullable}{default}")

                # Get row count
                cur.execute(f"SELECT COUNT(*) as count FROM {table_name}")
                count = cur.fetchone()
                print(f"\nRows: {count['count']}")

                # For summary-related tables, show sample data
                if any(word in table_name.lower() for word in ['content', 'summary', 'report']):
                    print(f"\nSample data (first 3 rows):")
                    cur.execute(f"SELECT * FROM {table_name} LIMIT 3")
                    sample_rows = cur.fetchall()

                    if sample_rows:
                        # Show first row's field names and sample values
                        sample = sample_rows[0]
                        for key, value in sample.items():
                            # Truncate long values
                            if isinstance(value, str) and len(value) > 100:
                                value = value[:100] + "..."
                            print(f"  {key}: {value}")
                    else:
                        print("  (No data)")

    finally:
        conn.close()

    return True

if __name__ == "__main__":
    print("🔍 PostgreSQL Schema Discovery")
    print("=" * 40)
    success = discover_schema()
    if success:
        print("\n✅ Schema discovery complete!")
    else:
        print("\n❌ Schema discovery failed!")