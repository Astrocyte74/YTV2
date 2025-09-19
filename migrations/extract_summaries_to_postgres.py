#!/usr/bin/env python3
"""
T-Y007: Extract and migrate summaries from SQLite to PostgreSQL content_summaries
Creates 'comprehensive' variant records with properly formatted HTML
"""

import argparse
import logging
import sqlite3
import sys
import re
import html
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

class SummaryMigrator:
    """Handles summary extraction from SQLite to PostgreSQL content_summaries"""

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

    def format_key_points(self, raw_text: str) -> str:
        """Format Key Points with structured markers - extracted from telegram_bot.py"""
        if not raw_text or not isinstance(raw_text, str):
            return '<p class="mb-6 leading-relaxed">No summary available.</p>'

        # Normalize line breaks and trim
        text = raw_text.replace('\r\n', '\n').replace('\r', '\n').strip()

        # Check for structured markers
        has_main_topic = bool(re.search(r'^(?:•\s*)?\*\*Main topic:\*\*\s*.+$', text, re.MULTILINE | re.IGNORECASE))
        has_key_points = bool(re.search(r'\*\*Key points:\*\*', text, re.IGNORECASE))

        # If we have structured markers, use special formatting
        if has_main_topic or has_key_points:
            return self._render_structured_key_points(text)

        # Fallback to normal paragraph formatting
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        formatted_lines = []

        for line in lines:
            # Handle bullet points
            if re.match(r'^(?:•|-|–|—)\s+', line):
                bullet_content = re.sub(r'^(?:•|-|–|—)\s+', '', line).strip()
                bullet_content = html.escape(bullet_content)
                formatted_lines.append(f'<li class="mb-2">{bullet_content}</li>')
            else:
                # Regular paragraph
                line = html.escape(line)
                formatted_lines.append(f'<p class="mb-4 leading-relaxed">{line}</p>')

        # Wrap consecutive <li> elements in <ul>
        result = []
        in_list = False

        for line in formatted_lines:
            if line.startswith('<li'):
                if not in_list:
                    result.append('<ul class="kp-list list-disc pl-6 space-y-1 mb-4">')
                    in_list = True
                result.append(line)
            else:
                if in_list:
                    result.append('</ul>')
                    in_list = False
                result.append(line)

        if in_list:
            result.append('</ul>')

        return '\n'.join(result)

    def _render_structured_key_points(self, text: str) -> str:
        """Render structured Key Points with proper formatting - extracted from telegram_bot.py"""
        parts = []

        # 1) Extract main topic
        main_topic_match = re.search(r'^(?:•\s*)?\*\*Main topic:\*\*\s*(.+)$', text, re.MULTILINE | re.IGNORECASE)
        main_topic = main_topic_match.group(1).strip() if main_topic_match else None

        # 2) Extract takeaway if present
        takeaway_match = re.search(r'\*\*Takeaway:\*\*\s*(.+?)(?=\*\*|$)', text, re.IGNORECASE | re.DOTALL)
        takeaway = takeaway_match.group(1).strip() if takeaway_match else None

        # 3) Find content after "**Key points:**" marker
        key_start_match = re.search(r'\*\*Key points:\*\*', text, re.IGNORECASE)
        bullet_block = ''

        if key_start_match:
            bullet_text = text[key_start_match.end():].strip()
            if takeaway_match:
                bullet_text = bullet_text[:takeaway_match.start() - key_start_match.end()].strip()
            bullet_block = bullet_text
        elif main_topic_match:
            bullet_block = text.replace(main_topic_match.group(0), '').strip()
            if takeaway_match:
                bullet_block = bullet_block.replace(takeaway_match.group(0), '').strip()
        else:
            bullet_block = text
            if takeaway_match:
                bullet_block = bullet_block.replace(takeaway_match.group(0), '').strip()

        # Strip takeaway lines from bullet block
        bullet_block = re.sub(r'^\s*(?:[•\-–—]\s*)?\*\*takeaway:\*\*.*$', '', bullet_block,
                             flags=re.IGNORECASE | re.MULTILINE).strip()

        # 4) Process bullet points
        lines = [line.strip() for line in bullet_block.split('\n') if line.strip()]
        takeaway_bullet_re = re.compile(r'^\s*(?:[•\-–—]\s*)?\*\*takeaway:\*\*', re.IGNORECASE)

        bullets = []
        for line in lines:
            if re.match(r'^(?:•|-|–|—)\s+', line):
                bullet_content = re.sub(r'^(?:•|-|–|—)\s+', '', line).strip()
                # Skip takeaway bullets
                if not takeaway_bullet_re.match(bullet_content):
                    bullet_content = html.escape(bullet_content)
                    bullets.append(f'<li class="mb-2">{bullet_content}</li>')

        # 5) Build final HTML
        if main_topic:
            main_topic_escaped = html.escape(main_topic)
            parts.append(f'<div class="kp-heading font-semibold text-lg mb-3">{main_topic_escaped}</div>')

        if bullets:
            bullet_html = '\n'.join(bullets)
            parts.append(f'<ul class="kp-list list-disc pl-6 space-y-1 mb-4">\n{bullet_html}\n</ul>')

        if takeaway:
            takeaway_escaped = html.escape(takeaway.strip())
            parts.append(f'<div class="kp-takeaway font-medium text-gray-800 bg-gray-50 p-3 rounded mt-4">{takeaway_escaped}</div>')

        if not parts:
            # Fallback if no structured content found
            escaped_text = html.escape(text)
            parts.append(f'<div class="kp-fallback">{escaped_text}</div>')

        return '\n'.join(parts)

    def extract_summaries(self):
        """Extract summaries from SQLite content_summaries and insert into PostgreSQL content_summaries"""
        logger.info("Starting summary extraction...")

        sqlite_conn = self.connect_sqlite()
        postgres_conn = self.connect_postgres()

        try:
            # Get all records from SQLite content_summaries table
            sqlite_cursor = sqlite_conn.cursor()
            sqlite_cursor.execute("""
                SELECT cs.content_id, cs.summary_text, cs.summary_type, c.video_id
                FROM content_summaries cs
                JOIN content c ON cs.content_id = c.id
                WHERE cs.summary_text IS NOT NULL AND cs.summary_text != ''
                ORDER BY cs.created_at DESC
            """)

            rows = sqlite_cursor.fetchall()
            logger.info(f"Found {len(rows)} records with summaries")

            with postgres_conn:
                postgres_cursor = postgres_conn.cursor()

                for content_id, summary_text, summary_type, video_id in rows:
                    self.records_processed += 1

                    if not video_id:
                        logger.warning(f"Skipping record {content_id} - no video_id found")
                        continue

                    try:
                        # Format the summary using the dashboard formatter
                        formatted_html = self.format_key_points(summary_text)

                        if self.dry_run:
                            logger.info(f"DRY RUN: Would create summary for {video_id} (type: {summary_type})")
                            self.records_migrated += 1
                            continue

                        # Insert into content_summaries with conflict resolution
                        # Map summary_type to variant (default to 'comprehensive')
                        variant = 'comprehensive' if summary_type == 'comprehensive' else summary_type

                        self.insert_summary_record(postgres_cursor, video_id, summary_text, formatted_html, variant)
                        self.records_migrated += 1

                        if self.records_processed % 10 == 0:
                            logger.info(f"Processed {self.records_processed} summaries...")

                    except Exception as e:
                        error_msg = f"Error processing summary for {video_id}: {e}"
                        logger.error(error_msg)
                        self.errors.append(error_msg)
                        continue

        finally:
            sqlite_conn.close()
            postgres_conn.close()

    def insert_summary_record(self, cursor, video_id: str, text: str, html: str, variant: str = 'comprehensive'):
        """Insert a summary record with conflict resolution"""

        insert_sql = """
            INSERT INTO content_summaries (video_id, variant, text, html, revision, is_latest)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (video_id, variant, revision) DO UPDATE SET
                text = EXCLUDED.text,
                html = EXCLUDED.html,
                updated_at = NOW()
        """

        cursor.execute(insert_sql, (video_id, variant, text, html, 1, True))

    def validate_migration(self):
        """Validate the summary migration results"""
        logger.info("Validating summary migration...")

        sqlite_conn = self.connect_sqlite()
        postgres_conn = self.connect_postgres()

        try:
            sqlite_cursor = sqlite_conn.cursor()
            postgres_cursor = postgres_conn.cursor()

            # Count source summaries
            sqlite_cursor.execute("SELECT COUNT(*) as count FROM content_summaries WHERE summary_text IS NOT NULL AND summary_text != ''")
            sqlite_count = sqlite_cursor.fetchone()[0]

            # Count migrated summaries
            postgres_cursor.execute("SELECT COUNT(*) as count FROM content_summaries WHERE variant = 'comprehensive'")
            postgres_result = postgres_cursor.fetchone()
            postgres_count = postgres_result['count'] if isinstance(postgres_result, dict) else postgres_result[0]

            logger.info(f"SQLite summaries: {sqlite_count}")
            logger.info(f"PostgreSQL summaries: {postgres_count}")

            # Check latest summaries view
            postgres_cursor.execute("SELECT COUNT(*) as count FROM v_latest_summaries WHERE variant = 'comprehensive'")
            postgres_result = postgres_cursor.fetchone()
            latest_count = postgres_result['count'] if isinstance(postgres_result, dict) else postgres_result[0]

            logger.info(f"Latest summaries view: {latest_count}")

            # Sample check
            postgres_cursor.execute("""
                SELECT video_id, LEFT(html, 100) || '...' as html_preview
                FROM content_summaries
                WHERE variant = 'comprehensive' AND is_latest = true
                ORDER BY created_at DESC
                LIMIT 3
            """)

            logger.info("Sample migrated summaries:")
            for record in postgres_cursor.fetchall():
                logger.info(f"  {record['video_id']}: {record['html_preview']}")

        finally:
            sqlite_conn.close()
            postgres_conn.close()

    def run_migration(self):
        """Execute the full summary migration process"""
        logger.info(f"Starting T-Y007 summary migration: {self.sqlite_path} -> PostgreSQL")
        logger.info(f"Dry run: {self.dry_run}")

        try:
            self.extract_summaries()

            if not self.dry_run:
                self.validate_migration()

            logger.info(f"Summary migration completed!")
            logger.info(f"Records processed: {self.records_processed}")
            logger.info(f"Records migrated: {self.records_migrated}")

            if self.errors:
                logger.warning(f"Errors encountered: {len(self.errors)}")
                for error in self.errors[:5]:  # Show first 5 errors
                    logger.warning(f"  {error}")

        except Exception as e:
            logger.error(f"Summary migration failed: {e}")
            raise

def main():
    parser = argparse.ArgumentParser(description='Migrate summaries from SQLite to PostgreSQL content_summaries')
    parser.add_argument('--sqlite-path', required=True, help='Path to SQLite database file')
    parser.add_argument('--postgres-url', required=True, help='PostgreSQL connection URL')
    parser.add_argument('--dry-run', action='store_true', help='Test mode - no actual writes')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose logging')

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    migrator = SummaryMigrator(
        sqlite_path=args.sqlite_path,
        postgres_url=args.postgres_url,
        dry_run=args.dry_run
    )

    migrator.run_migration()

if __name__ == '__main__':
    main()