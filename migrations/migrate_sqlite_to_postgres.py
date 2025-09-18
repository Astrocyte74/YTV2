#!/usr/bin/env python3
"""
SQLite to PostgreSQL Migration Script for YTV2
Migrates content from SQLite backup to PostgreSQL with conflict resolution
"""

import argparse
import json
import logging
import sqlite3
import sys
from pathlib import Path
from typing import Dict, Any, Optional

try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    print("Error: psycopg2 not available. Install with: pip install psycopg2-binary")
    sys.exit(1)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class YTV2Migrator:
    """Handles migration from SQLite to PostgreSQL"""

    def __init__(self, sqlite_path: str, postgres_url: str, dry_run: bool = False):
        self.sqlite_path = Path(sqlite_path)
        self.postgres_url = postgres_url
        self.dry_run = dry_run
        self.records_processed = 0
        self.records_migrated = 0
        self.errors = []

    def connect_sqlite(self):
        """Connect to SQLite database"""
        if not self.sqlite_path.exists():
            raise FileNotFoundError(f"SQLite database not found: {self.sqlite_path}")
        return sqlite3.connect(self.sqlite_path)

    def connect_postgres(self):
        """Connect to PostgreSQL database"""
        return psycopg2.connect(
            self.postgres_url,
            cursor_factory=psycopg2.extras.RealDictCursor
        )

    def transform_data(self, row: Dict) -> Dict[str, Any]:
        """Transform SQLite row data for PostgreSQL"""
        transformed = {}

        # Core fields - map directly
        core_fields = [
            'video_id', 'id', 'title', 'channel_name', 'thumbnail_url',
            'canonical_url', 'duration_seconds', 'has_audio'
        ]

        for field in core_fields:
            if field in row and row[field] is not None:
                transformed[field] = row[field]

        # Date fields - convert to proper format
        if row.get('published_at'):
            transformed['published_at'] = row['published_at']
        if row.get('indexed_at'):
            transformed['indexed_at'] = row['indexed_at']

        # JSON fields - handle both new and legacy formats
        if row.get('subcategories_json'):
            try:
                # Parse subcategories_json - this is the 74 sophisticated records
                subcats = json.loads(row['subcategories_json'])
                transformed['subcategories_json'] = subcats
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(f"Invalid subcategories_json for {row.get('video_id')}: {e}")
                transformed['subcategories_json'] = None

        if row.get('analysis'):
            try:
                # Parse analysis field - new format
                analysis = json.loads(row['analysis']) if isinstance(row['analysis'], str) else row['analysis']
                transformed['analysis_json'] = analysis
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(f"Invalid analysis for {row.get('video_id')}: {e}")
                transformed['analysis_json'] = None

        # Handle key_topics as JSON if present
        if row.get('key_topics'):
            try:
                topics = json.loads(row['key_topics']) if isinstance(row['key_topics'], str) else row['key_topics']
                transformed['topics_json'] = topics
            except (json.JSONDecodeError, TypeError) as e:
                # Store as simple text if not valid JSON
                transformed['topics_json'] = {'raw_text': str(row['key_topics'])}

        return transformed

    def migrate_content_table(self):
        """Migrate the main content table"""
        logger.info("Starting content table migration...")

        sqlite_conn = self.connect_sqlite()
        postgres_conn = self.connect_postgres()

        try:
            # Get all records from SQLite
            sqlite_cursor = sqlite_conn.cursor()
            sqlite_cursor.execute("SELECT * FROM content ORDER BY indexed_at DESC")

            # Get column names
            columns = [description[0] for description in sqlite_cursor.description]

            with postgres_conn:
                postgres_cursor = postgres_conn.cursor()

                while True:
                    rows = sqlite_cursor.fetchmany(100)  # Process in batches
                    if not rows:
                        break

                    for row_tuple in rows:
                        self.records_processed += 1

                        # Convert tuple to dict
                        row = dict(zip(columns, row_tuple))

                        if not row.get('video_id'):
                            logger.warning(f"Skipping row without video_id: {row}")
                            continue

                        try:
                            transformed = self.transform_data(row)

                            if self.dry_run:
                                logger.info(f"DRY RUN: Would migrate {transformed['video_id']}")
                                self.records_migrated += 1
                                continue

                            # Insert with conflict resolution
                            self.insert_content_record(postgres_cursor, transformed)
                            self.records_migrated += 1

                            if self.records_processed % 10 == 0:
                                logger.info(f"Processed {self.records_processed} records...")

                        except Exception as e:
                            error_msg = f"Error processing {row.get('video_id', 'unknown')}: {e}"
                            logger.error(error_msg)
                            self.errors.append(error_msg)
                            continue

        finally:
            sqlite_conn.close()
            postgres_conn.close()

    def insert_content_record(self, cursor, data: Dict[str, Any]):
        """Insert a single content record with conflict resolution"""

        # Build INSERT statement dynamically based on available data
        fields = []
        values = []
        placeholders = []

        for field, value in data.items():
            if value is not None:
                fields.append(field)
                values.append(value)
                placeholders.append('%s')

        if not fields:
            raise ValueError("No valid fields to insert")

        # Create the INSERT with ON CONFLICT
        insert_sql = f"""
            INSERT INTO content ({', '.join(fields)})
            VALUES ({', '.join(placeholders)})
            ON CONFLICT (video_id) DO UPDATE SET
                {', '.join(f'{field} = EXCLUDED.{field}' for field in fields if field != 'video_id')},
                updated_at = NOW()
        """

        cursor.execute(insert_sql, values)

    def validate_migration(self):
        """Validate the migration results"""
        logger.info("Validating migration...")

        sqlite_conn = self.connect_sqlite()
        postgres_conn = self.connect_postgres()

        try:
            # Count records
            sqlite_cursor = sqlite_conn.cursor()
            postgres_cursor = postgres_conn.cursor()

            sqlite_cursor.execute("SELECT COUNT(*) FROM content")
            sqlite_count = sqlite_cursor.fetchone()[0]

            postgres_cursor.execute("SELECT COUNT(*) FROM content")
            postgres_count = postgres_cursor.fetchone()[0]

            logger.info(f"SQLite records: {sqlite_count}")
            logger.info(f"PostgreSQL records: {postgres_count}")

            # Check sophisticated categorization records
            sqlite_cursor.execute("SELECT COUNT(*) FROM content WHERE subcategories_json IS NOT NULL")
            sqlite_categorized = sqlite_cursor.fetchone()[0]

            postgres_cursor.execute("SELECT COUNT(*) FROM content WHERE subcategories_json IS NOT NULL")
            postgres_categorized = postgres_cursor.fetchone()[0]

            logger.info(f"SQLite categorized records: {sqlite_categorized}")
            logger.info(f"PostgreSQL categorized records: {postgres_categorized}")

            # Spot check a few records
            postgres_cursor.execute("""
                SELECT video_id, title, subcategories_json IS NOT NULL as has_categories
                FROM content
                ORDER BY indexed_at DESC
                LIMIT 3
            """)

            logger.info("Sample migrated records:")
            for record in postgres_cursor.fetchall():
                logger.info(f"  {record['video_id']}: {record['title'][:50]}... (categorized: {record['has_categories']})")

        finally:
            sqlite_conn.close()
            postgres_conn.close()

    def run_migration(self):
        """Execute the full migration process"""
        logger.info(f"Starting YTV2 migration: {self.sqlite_path} -> PostgreSQL")
        logger.info(f"Dry run: {self.dry_run}")

        try:
            self.migrate_content_table()

            if not self.dry_run:
                self.validate_migration()

            logger.info(f"Migration completed!")
            logger.info(f"Records processed: {self.records_processed}")
            logger.info(f"Records migrated: {self.records_migrated}")

            if self.errors:
                logger.warning(f"Errors encountered: {len(self.errors)}")
                for error in self.errors[:5]:  # Show first 5 errors
                    logger.warning(f"  {error}")

        except Exception as e:
            logger.error(f"Migration failed: {e}")
            raise

def main():
    parser = argparse.ArgumentParser(description='Migrate YTV2 data from SQLite to PostgreSQL')
    parser.add_argument('--sqlite-path', required=True, help='Path to SQLite database file')
    parser.add_argument('--postgres-url', required=True, help='PostgreSQL connection URL')
    parser.add_argument('--dry-run', action='store_true', help='Test mode - no actual writes')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose logging')

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    migrator = YTV2Migrator(
        sqlite_path=args.sqlite_path,
        postgres_url=args.postgres_url,
        dry_run=args.dry_run
    )

    migrator.run_migration()

if __name__ == '__main__':
    main()