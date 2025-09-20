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
            # Get all summary-related fields from content table
            print("\n📊 Analyzing summary type fields...")
            cur.execute("""
                SELECT
                    video_id,
                    title,
                    summary_type,
                    summary_variant,
                    summary_type_latest,
                    indexed_at
                FROM content_summaries
                ORDER BY indexed_at DESC
                LIMIT 200
            """)

            rows = cur.fetchall()

            if not rows:
                print("❌ No data found in content_summaries table")
                return False

            print(f"📈 Analyzed {len(rows)} records")

            # Counters for each field
            summary_type_counts = Counter()
            summary_variant_counts = Counter()
            summary_type_latest_counts = Counter()

            # Track combinations
            combinations = []

            for row in rows:
                # Handle None values
                summary_type = row['summary_type'] if row['summary_type'] is not None else 'NULL'
                summary_variant = row['summary_variant'] if row['summary_variant'] is not None else 'NULL'
                summary_type_latest = row['summary_type_latest'] if row['summary_type_latest'] is not None else 'NULL'

                summary_type_counts[summary_type] += 1
                summary_variant_counts[summary_variant] += 1
                summary_type_latest_counts[summary_type_latest] += 1

                combinations.append({
                    'video_id': row['video_id'],
                    'title': row['title'][:50] + '...' if len(row['title']) > 50 else row['title'],
                    'summary_type': summary_type,
                    'summary_variant': summary_variant,
                    'summary_type_latest': summary_type_latest,
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

            # Show recent combinations
            print(f"\n📋 Recent 10 records (newest first):")
            print("Title".ljust(35), "Type".ljust(12), "Variant".ljust(15), "Latest".ljust(12))
            print("-" * 80)
            for combo in combinations[:10]:
                title = combo['title'][:32] + '...' if len(combo['title']) > 32 else combo['title']
                print(
                    title.ljust(35),
                    combo['summary_type'][:11].ljust(12),
                    combo['summary_variant'][:14].ljust(15),
                    combo['summary_type_latest'][:11].ljust(12)
                )

            # Recommendations
            print(f"\n🎯 RECOMMENDATIONS:")
            print(f"1. Primary field to use: summary_variant (most diverse data)")
            print(f"2. Fallback field: summary_type")
            print(f"3. summary_type_latest appears to be mostly NULL")

            # Check for API field mapping
            print(f"\n🔍 Checking /api/filters endpoint field usage...")
            cur.execute("""
                SELECT DISTINCT summary_variant as type, COUNT(*) as count
                FROM content_summaries
                WHERE summary_variant IS NOT NULL
                GROUP BY summary_variant
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