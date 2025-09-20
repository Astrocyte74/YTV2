#!/usr/bin/env python3
"""
Analyze summary type fields in the PostgreSQL database (CORRECTED VERSION)
This script examines the actual schema: content + content_summaries + v_latest_summaries
"""

import os
import json
from collections import Counter
from urllib.parse import urlparse

def analyze_summary_types():
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
            # Analyze content.summary_type_latest field
            print("\n📊 Analyzing content.summary_type_latest field...")
            cur.execute("""
                SELECT
                    summary_type_latest,
                    COUNT(*) as count
                FROM content
                GROUP BY summary_type_latest
                ORDER BY count DESC;
            """)

            content_summary_latest = cur.fetchall()
            print("content.summary_type_latest distribution:")
            for row in content_summary_latest:
                value = row['summary_type_latest'] if row['summary_type_latest'] is not None else 'NULL'
                print(f"  {value:<20} {row['count']:>3}")

            # Analyze content_summaries.variant field
            print("\n📊 Analyzing content_summaries.variant field...")
            cur.execute("""
                SELECT
                    variant,
                    COUNT(*) as count
                FROM content_summaries
                GROUP BY variant
                ORDER BY count DESC;
            """)

            variant_data = cur.fetchall()
            print("content_summaries.variant distribution:")
            for row in variant_data:
                value = row['variant'] if row['variant'] is not None else 'NULL'
                print(f"  {value:<20} {row['count']:>3}")

            # Analyze content_summaries.summary_type field
            print("\n📊 Analyzing content_summaries.summary_type field...")
            cur.execute("""
                SELECT
                    summary_type,
                    COUNT(*) as count
                FROM content_summaries
                GROUP BY summary_type
                ORDER BY count DESC;
            """)

            summary_type_data = cur.fetchall()
            print("content_summaries.summary_type distribution:")
            for row in summary_type_data:
                value = row['summary_type'] if row['summary_type'] is not None else 'NULL'
                print(f"  {value:<20} {row['count']:>3}")

            # Analyze v_latest_summaries.variant field
            print("\n📊 Analyzing v_latest_summaries.variant field...")
            cur.execute("""
                SELECT
                    variant,
                    COUNT(*) as count
                FROM v_latest_summaries
                GROUP BY variant
                ORDER BY count DESC;
            """)

            latest_variant_data = cur.fetchall()
            print("v_latest_summaries.variant distribution:")
            for row in latest_variant_data:
                value = row['variant'] if row['variant'] is not None else 'NULL'
                print(f"  {value:<20} {row['count']:>3}")

            # Show relationship between content and summaries
            print("\n📊 Analyzing content with latest summaries...")
            cur.execute("""
                SELECT
                    c.video_id,
                    c.title,
                    c.summary_type_latest,
                    ls.variant as latest_variant,
                    c.indexed_at
                FROM content c
                LEFT JOIN v_latest_summaries ls ON c.video_id = ls.video_id
                ORDER BY c.indexed_at DESC
                LIMIT 10;
            """)

            relationships = cur.fetchall()
            print("Recent 10 content records with their latest summaries:")
            print("Title".ljust(35), "Content.Latest".ljust(15), "View.Variant".ljust(15), "Date")
            print("-" * 80)
            for row in relationships:
                title = row['title'][:30] + '...' if len(row['title']) > 30 else row['title']
                content_latest = row['summary_type_latest'] or 'NULL'
                view_variant = row['latest_variant'] or 'NULL'
                date = str(row['indexed_at'])[:10] if row['indexed_at'] else 'NULL'
                print(
                    title.ljust(35),
                    content_latest[:14].ljust(15),
                    view_variant[:14].ljust(15),
                    date
                )

            # Check for "bullet-points" vs "Key Points" summaries
            print("\n📊 Looking for Key Points / bullet-points summaries...")
            cur.execute("""
                SELECT
                    cs.variant,
                    cs.summary_type,
                    cs.text,
                    c.title
                FROM content_summaries cs
                JOIN content c ON cs.video_id = c.video_id
                WHERE cs.variant ILIKE '%bullet%' OR cs.variant ILIKE '%key%' OR cs.variant ILIKE '%point%'
                   OR cs.text ILIKE '%**Main topic:**%' OR cs.text ILIKE '%**Key points:**%'
                ORDER BY cs.created_at DESC;
            """)

            key_points = cur.fetchall()
            if key_points:
                print(f"Found {len(key_points)} Key Points summaries:")
                for row in key_points:
                    title = row['title'][:40] + '...' if len(row['title']) > 40 else row['title']
                    variant = row['variant'] or 'NULL'
                    summary_type = row['summary_type'] or 'NULL'
                    has_markers = '✓' if '**Main topic:**' in (row['text'] or '') else '✗'
                    print(f"  {title:<45} | variant: {variant:<15} | type: {summary_type:<15} | markers: {has_markers}")
            else:
                print("No Key Points summaries found")

            # Recommendations
            print(f"\n🎯 RECOMMENDATIONS:")
            print(f"1. For filtering: Use content_summaries.variant field")
            print(f"2. Available variants: {', '.join([r['variant'] for r in variant_data if r['variant']])}")
            print(f"3. content.summary_type_latest appears mostly NULL - not useful for filtering")
            print(f"4. Use v_latest_summaries view for latest summary per video")

    finally:
        conn.close()

    return True

if __name__ == "__main__":
    print("🔍 YTV2 Summary Type Analysis (CORRECTED)")
    print("=" * 50)
    success = analyze_summary_types()
    if success:
        print("\n✅ Analysis complete!")
    else:
        print("\n❌ Analysis failed!")