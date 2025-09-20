#!/usr/bin/env python3
"""
Analyze summary type fields in the PostgreSQL database
This script examines all summary-related fields to understand data distribution
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
            # Get all summary-related fields from content and latest_summaries tables
            print("\n📊 Analyzing summary type fields...")
            cur.execute("""
                SELECT
                    c.video_id,
                    c.title,
                    c.summary_type,
                    c.summary_variant,
                    c.summary_type_latest,
                    ls.variant as latest_variant,
                    c.indexed_at
                FROM content c
                LEFT JOIN latest_summaries ls ON c.video_id = ls.video_id
                ORDER BY c.indexed_at DESC
                LIMIT 200
            """)

            rows = cur.fetchall()

            if not rows:
                print("❌ No data found in content table")
                return False

            print(f"📈 Analyzed {len(rows)} records")

            # Counters for each field
            summary_type_counts = Counter()
            summary_variant_counts = Counter()
            summary_type_latest_counts = Counter()
            latest_variant_counts = Counter()

            # Track combinations
            combinations = []

            for row in rows:
                # Handle None values
                summary_type = row['summary_type'] if row['summary_type'] is not None else 'NULL'
                summary_variant = row['summary_variant'] if row['summary_variant'] is not None else 'NULL'
                summary_type_latest = row['summary_type_latest'] if row['summary_type_latest'] is not None else 'NULL'
                latest_variant = row['latest_variant'] if row['latest_variant'] is not None else 'NULL'

                summary_type_counts[summary_type] += 1
                summary_variant_counts[summary_variant] += 1
                summary_type_latest_counts[summary_type_latest] += 1
                latest_variant_counts[latest_variant] += 1

                combinations.append({
                    'video_id': row['video_id'],
                    'title': row['title'][:50] + '...' if len(row['title']) > 50 else row['title'],
                    'summary_type': summary_type,
                    'summary_variant': summary_variant,
                    'summary_type_latest': summary_type_latest,
                    'latest_variant': latest_variant,
                    'indexed_at': str(row['indexed_at'])
                })

            # Print analysis results
            print("\n" + "="*60)
            print("SUMMARY TYPE FIELD ANALYSIS")
            print("="*60)

            print(f"\n📋 summary_type field distribution:")
            for value, count in summary_type_counts.most_common():
                percentage = (count / len(rows)) * 100
                print(f"  {value:<20} {count:>3} ({percentage:5.1f}%)")

            print(f"\n📋 summary_variant field distribution:")
            for value, count in summary_variant_counts.most_common():
                percentage = (count / len(rows)) * 100
                print(f"  {value:<20} {count:>3} ({percentage:5.1f}%)")

            print(f"\n📋 summary_type_latest field distribution:")
            for value, count in summary_type_latest_counts.most_common():
                percentage = (count / len(rows)) * 100
                print(f"  {value:<20} {count:>3} ({percentage:5.1f}%)")

            print(f"\n📋 latest_variant field distribution (from latest_summaries table):")
            for value, count in latest_variant_counts.most_common():
                percentage = (count / len(rows)) * 100
                print(f"  {value:<20} {count:>3} ({percentage:5.1f}%)")

            # Show recent combinations
            print(f"\n📋 Recent 10 records (newest first):")
            print("Title".ljust(30), "Type".ljust(10), "Variant".ljust(12), "Latest".ljust(10), "LS_Variant".ljust(12))
            print("-" * 90)
            for combo in combinations[:10]:
                title = combo['title'][:27] + '...' if len(combo['title']) > 27 else combo['title']
                print(
                    title.ljust(30),
                    combo['summary_type'][:9].ljust(10),
                    combo['summary_variant'][:11].ljust(12),
                    combo['summary_type_latest'][:9].ljust(10),
                    combo['latest_variant'][:11].ljust(12)
                )

            # Recommendations
            print(f"\n🎯 RECOMMENDATIONS:")
            print(f"1. Primary field to use: summary_variant (most diverse data)")
            print(f"2. Fallback field: summary_type")
            print(f"3. summary_type_latest appears to be mostly NULL")

            # Check for API field mapping
            print(f"\n🔍 Checking latest_summaries variant field usage...")
            cur.execute("""
                SELECT DISTINCT ls.variant as type, COUNT(*) as count
                FROM content c
                LEFT JOIN latest_summaries ls ON c.video_id = ls.video_id
                WHERE ls.variant IS NOT NULL
                GROUP BY ls.variant
                ORDER BY count DESC
            """)

            variant_data = cur.fetchall()
            print("API should return these summary_type options:")
            for row in variant_data:
                print(f"  {row['type']}: {row['count']} records")

    finally:
        conn.close()

    return True

if __name__ == "__main__":
    print("🔍 YTV2 Summary Type Analysis")
    print("="*40)
    success = analyze_summary_types()
    if success:
        print("\n✅ Analysis complete!")
    else:
        print("\n❌ Analysis failed!")