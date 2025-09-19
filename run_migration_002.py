#!/usr/bin/env python3
"""
Run migration 002_add_summary_type.sql on PostgreSQL database
This script can be run from the Render dashboard environment
"""

import os
import sys
from pathlib import Path

# Add current directory to path for imports
sys.path.append('.')

def run_migration():
    """Run the summary_type migration on PostgreSQL"""
    try:
        import psycopg2
        from urllib.parse import urlparse

        # Get database URL from environment
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            print("❌ DATABASE_URL environment variable not found")
            return False

        print(f"🔗 Connecting to PostgreSQL...")

        # Parse the URL to handle SSL requirements for Render
        url = urlparse(database_url)

        # Connect with SSL for Render PostgreSQL
        conn = psycopg2.connect(
            host=url.hostname,
            port=url.port or 5432,
            database=url.path[1:],  # Remove leading slash
            user=url.username,
            password=url.password,
            sslmode='require'  # Required for Render PostgreSQL
        )

        cursor = conn.cursor()

        print('📦 Running migration: 002_add_summary_type.sql')

        # Read and execute migration
        migration_path = Path('migrations/002_add_summary_type.sql')
        if not migration_path.exists():
            print(f"❌ Migration file not found: {migration_path}")
            return False

        with open(migration_path, 'r') as f:
            migration_sql = f.read()

        cursor.execute(migration_sql)
        conn.commit()

        print('✅ Migration completed successfully')

        # Verify the new columns exist
        cursor.execute("""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_name IN ('content', 'content_summaries')
          AND column_name LIKE '%summary_type%'
        ORDER BY table_name, column_name;
        """)

        results = cursor.fetchall()
        print('\n📋 New summary_type columns:')
        for row in results:
            table = 'content' if 'latest' in row[0] else 'content_summaries'
            print(f'   {table}.{row[0]} ({row[1]}, nullable={row[2]})')

        cursor.close()
        conn.close()

        return True

    except ImportError:
        print("❌ psycopg2 not available - install with: pip install psycopg2-binary")
        return False
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        return False

if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)