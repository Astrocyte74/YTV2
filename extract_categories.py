#!/usr/bin/env python3
"""
Extract all categories and subcategories from YTV2 PostgreSQL database
This will help us understand the category structure for quiz integration
"""

import os
import json
from collections import defaultdict, Counter
from urllib.parse import urlparse

def extract_categories():
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
            print("\n📊 Extracting categories and subcategories...")
            cur.execute("""
                SELECT
                    video_id,
                    title,
                    analysis_json,
                    subcategories_json
                FROM content
                ORDER BY indexed_at DESC;
            """)

            rows = cur.fetchall()
            print(f"📈 Analyzing {len(rows)} records...")

            # Storage for categories
            category_structure = defaultdict(lambda: defaultdict(int))
            category_counts = Counter()
            subcategory_counts = Counter()

            # Track different data sources
            analysis_categories = []
            subcategories_categories = []

            for row in rows:
                video_id = row['video_id']
                title = row['title'][:50] + '...' if len(row['title']) > 50 else row['title']

                # Parse analysis_json
                analysis_json = row.get('analysis_json') or {}
                if isinstance(analysis_json, str):
                    try:
                        analysis_json = json.loads(analysis_json)
                    except json.JSONDecodeError:
                        analysis_json = {}

                # Parse subcategories_json
                subcategories_json = row.get('subcategories_json') or {}
                if isinstance(subcategories_json, str):
                    try:
                        subcategories_json = json.loads(subcategories_json)
                    except json.JSONDecodeError:
                        subcategories_json = {}

                # Extract from analysis_json.categories (rich format)
                if 'categories' in analysis_json:
                    for cat_obj in analysis_json['categories']:
                        if isinstance(cat_obj, dict):
                            category = cat_obj.get('category')
                            subcategories = cat_obj.get('subcategories', [])

                            if category:
                                category_counts[category] += 1
                                analysis_categories.append({
                                    'category': category,
                                    'subcategories': subcategories,
                                    'source': 'analysis_json.categories'
                                })

                                for subcat in subcategories:
                                    if subcat:
                                        category_structure[category][subcat] += 1
                                        subcategory_counts[subcat] += 1

                # Extract from analysis_json.category (legacy array format)
                elif 'category' in analysis_json:
                    categories = analysis_json['category']
                    if isinstance(categories, str):
                        categories = [categories]
                    if isinstance(categories, list):
                        for category in categories:
                            if category:
                                category_counts[category] += 1
                                analysis_categories.append({
                                    'category': category,
                                    'subcategories': [],
                                    'source': 'analysis_json.category'
                                })

                # Extract from subcategories_json.categories
                if 'categories' in subcategories_json:
                    for cat_obj in subcategories_json['categories']:
                        if isinstance(cat_obj, dict):
                            category = cat_obj.get('category')
                            subcategories = cat_obj.get('subcategories', [])

                            if category:
                                category_counts[category] += 1
                                subcategories_categories.append({
                                    'category': category,
                                    'subcategories': subcategories,
                                    'source': 'subcategories_json.categories'
                                })

                                for subcat in subcategories:
                                    if subcat:
                                        category_structure[category][subcat] += 1
                                        subcategory_counts[subcat] += 1

            # Print results
            print("\n" + "="*70)
            print("📋 CATEGORY & SUBCATEGORY ANALYSIS")
            print("="*70)

            print(f"\n🏷️ MAIN CATEGORIES ({len(category_counts)} unique):")
            print("-" * 50)
            for category, count in category_counts.most_common():
                print(f"  {category:<35} ({count:>3} videos)")

            print(f"\n📑 SUBCATEGORIES BY CATEGORY:")
            print("-" * 50)
            for category in sorted(category_structure.keys()):
                print(f"\n📂 {category}:")
                subcats = category_structure[category]
                for subcat, count in sorted(subcats.items(), key=lambda x: x[1], reverse=True):
                    print(f"   └── {subcat:<45} ({count:>2})")

            print(f"\n📊 TOP SUBCATEGORIES (across all categories):")
            print("-" * 50)
            for subcat, count in subcategory_counts.most_common(20):
                print(f"  {subcat:<45} ({count:>3} videos)")

            print(f"\n🎯 QUIZ INTEGRATION RECOMMENDATIONS:")
            print("-" * 50)
            print("For quiz JSON metadata, use these category combinations:")
            print()

            # Generate recommended combinations
            recommendations = []
            for category in category_counts.most_common(10):  # Top 10 categories
                cat_name = category[0]
                if cat_name in category_structure:
                    top_subcats = [sub for sub, count in
                                 sorted(category_structure[cat_name].items(),
                                       key=lambda x: x[1], reverse=True)[:3]]
                    recommendations.append({
                        'category': cat_name,
                        'popular_subcategories': top_subcats
                    })

            for rec in recommendations:
                print(f"📁 {rec['category']}:")
                for subcat in rec['popular_subcategories']:
                    print(f"   └── {subcat}")
                print()

            # Generate JSON structure for easy copy-paste
            print(f"\n📋 JSON STRUCTURE FOR QUIZ METADATA:")
            print("-" * 50)
            example_structure = {
                "meta": {
                    "topic": "Your Quiz Topic",
                    "difficulty": "beginner|intermediate|advanced",
                    "category": recommendations[0]['category'] if recommendations else "Technology",
                    "subcategory": recommendations[0]['popular_subcategories'][0] if recommendations and recommendations[0]['popular_subcategories'] else "Programming & Software Development",
                    "available_categories": [rec['category'] for rec in recommendations[:5]],
                    "available_subcategories": {
                        rec['category']: rec['popular_subcategories']
                        for rec in recommendations[:5]
                    }
                }
            }

            print(json.dumps(example_structure, indent=2))

    finally:
        conn.close()

    return True

if __name__ == "__main__":
    print("🏷️ YTV2 Category & Subcategory Extractor")
    print("=" * 50)
    success = extract_categories()
    if success:
        print("\n✅ Category extraction complete!")
        print("\n💡 Use this data to align quiz categories with your video content!")
    else:
        print("\n❌ Category extraction failed!")