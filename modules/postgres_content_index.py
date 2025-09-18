#!/usr/bin/env python3
"""
PostgreSQL Content Index
High-performance content management using PostgreSQL database.
Designed for parallel PostgreSQL system with variant fallback support.
"""

import os
import json
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timezone

try:
    import psycopg2
    import psycopg2.extras
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False

logger = logging.getLogger(__name__)

class PostgreSQLContentIndex:
    """PostgreSQL-based content management for YTV2 Dashboard with variant fallback."""

    def __init__(self, postgres_url: str = None):
        """Initialize with PostgreSQL connection."""
        if not PSYCOPG2_AVAILABLE:
            raise ImportError("psycopg2 not available. Install with: pip install psycopg2-binary")

        self.postgres_url = postgres_url or os.getenv('DATABASE_URL_POSTGRES_NEW')
        if not self.postgres_url:
            raise ValueError("PostgreSQL URL not provided and DATABASE_URL_POSTGRES_NEW not set")

        logger.info(f"Using PostgreSQL database")

    def _get_connection(self):
        """Get PostgreSQL connection with RealDictCursor."""
        return psycopg2.connect(
            self.postgres_url,
            cursor_factory=psycopg2.extras.RealDictCursor
        )

    def get_reports(self, filters: Dict[str, Any] = None, sort: str = "newest",
                   page: int = 1, size: int = 20) -> Tuple[List[Dict[str, Any]], int]:
        """Get paginated and filtered reports with variant precedence fallback."""

        conn = self._get_connection()
        try:
            # Build base query with LEFT JOIN LATERAL for variant fallback
            query = """
                SELECT
                    c.*,
                    ls.variant as summary_variant,
                    ls.text as summary_text,
                    ls.html as summary_html,
                    ls.revision as summary_revision,
                    ls.created_at as summary_created_at
                FROM content c
                LEFT JOIN LATERAL (
                    SELECT s.*
                    FROM v_latest_summaries s
                    WHERE s.video_id = c.video_id
                      AND s.variant IN (
                        'comprehensive','key-points','bullet-points',
                        'executive','key-insights','audio','audio-fr','audio-es'
                      )
                    ORDER BY array_position(
                      ARRAY[
                        'comprehensive','key-points','bullet-points',
                        'executive','key-insights','audio','audio-fr','audio-es'
                      ]::text[],
                      s.variant
                    )
                    LIMIT 1
                ) ls ON true
                WHERE ls.html IS NOT NULL
            """
            params = []
            where_conditions = []

            # Apply filters
            if filters:
                # Category filters
                if 'category' in filters and filters['category']:
                    categories = filters['category'] if isinstance(filters['category'], list) else [filters['category']]
                    cat_conditions = []
                    for cat in categories:
                        cat_conditions.append("""(
                            (c.subcategories_json IS NOT NULL AND
                             c.subcategories_json->'categories' @> %s::jsonb) OR
                            (c.analysis_json->'categories' IS NOT NULL AND
                             c.analysis_json->'categories' @> %s::jsonb)
                        )""")
                        cat_json = json.dumps([{"category": cat}])
                        params.extend([cat_json, cat_json])

                    if cat_conditions:
                        where_conditions.append(f"({' OR '.join(cat_conditions)})")

                # Channel filters
                if 'channel' in filters and filters['channel']:
                    channels = filters['channel'] if isinstance(filters['channel'], list) else [filters['channel']]
                    channel_placeholders = ','.join(['%s'] * len(channels))
                    where_conditions.append(f"c.channel_name IN ({channel_placeholders})")
                    params.extend(channels)

                # Content type filters
                if 'content_type' in filters and filters['content_type']:
                    content_types = filters['content_type'] if isinstance(filters['content_type'], list) else [filters['content_type']]
                    type_placeholders = ','.join(['%s'] * len(content_types))
                    where_conditions.append(f"c.content_type IN ({type_placeholders})")
                    params.extend(content_types)

                # Complexity filters
                if 'complexity' in filters and filters['complexity']:
                    complexities = filters['complexity'] if isinstance(filters['complexity'], list) else [filters['complexity']]
                    complexity_placeholders = ','.join(['%s'] * len(complexities))
                    where_conditions.append(f"c.complexity_level IN ({complexity_placeholders})")
                    params.extend(complexities)

                # Language filters
                if 'language' in filters and filters['language']:
                    languages = filters['language'] if isinstance(filters['language'], list) else [filters['language']]
                    lang_placeholders = ','.join(['%s'] * len(languages))
                    where_conditions.append(f"c.language IN ({lang_placeholders})")
                    params.extend(languages)

                # Has audio filter
                if 'has_audio' in filters:
                    where_conditions.append("c.has_audio = %s")
                    params.append(filters['has_audio'])

            # Add WHERE clause
            if where_conditions:
                query += " AND " + " AND ".join(where_conditions)

            # Add sorting
            if sort == "added_desc":
                query += " ORDER BY c.indexed_at DESC"
            elif sort == "video_newest":
                query += " ORDER BY c.published_at DESC"
            elif sort == "title_az":
                query += " ORDER BY c.title ASC"
            elif sort == "title_za":
                query += " ORDER BY c.title DESC"
            elif sort == "channel_az":
                query += " ORDER BY c.channel_name ASC"
            elif sort == "channel_za":
                query += " ORDER BY c.channel_name DESC"
            else:  # Default to newest
                query += " ORDER BY c.indexed_at DESC"

            # Count total results for pagination
            count_query = f"""
                SELECT COUNT(*) as total
                FROM content c
                LEFT JOIN LATERAL (
                    SELECT s.*
                    FROM v_latest_summaries s
                    WHERE s.video_id = c.video_id
                      AND s.variant IN (
                        'comprehensive','key-points','bullet-points',
                        'executive','key-insights','audio','audio-fr','audio-es'
                      )
                    ORDER BY array_position(
                      ARRAY[
                        'comprehensive','key-points','bullet-points',
                        'executive','key-insights','audio','audio-fr','audio-es'
                      ]::text[],
                      s.variant
                    )
                    LIMIT 1
                ) ls ON true
                WHERE ls.html IS NOT NULL
            """

            if where_conditions:
                count_query += " AND " + " AND ".join(where_conditions)

            cursor = conn.cursor()
            cursor.execute(count_query, params)
            total_count = cursor.fetchone()['total']

            # Add pagination
            offset = (page - 1) * size
            query += f" LIMIT %s OFFSET %s"
            params.extend([size, offset])

            # Execute main query
            cursor.execute(query, params)
            rows = cursor.fetchall()

            # Convert to list of dicts
            reports = []
            for row in rows:
                report = dict(row)
                reports.append(report)

            return reports, total_count

        finally:
            conn.close()

    def get_report_count(self) -> int:
        """Get total number of reports with available summaries."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) as total
                FROM content c
                LEFT JOIN LATERAL (
                    SELECT s.*
                    FROM v_latest_summaries s
                    WHERE s.video_id = c.video_id
                      AND s.variant IN (
                        'comprehensive','key-points','bullet-points',
                        'executive','key-insights','audio','audio-fr','audio-es'
                      )
                    ORDER BY array_position(
                      ARRAY[
                        'comprehensive','key-points','bullet-points',
                        'executive','key-insights','audio','audio-fr','audio-es'
                      ]::text[],
                      s.variant
                    )
                    LIMIT 1
                ) ls ON true
                WHERE ls.html IS NOT NULL
            """)
            return cursor.fetchone()['total']
        finally:
            conn.close()

    def get_report_by_id(self, report_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific report by video_id with variant fallback."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    c.*,
                    ls.variant as summary_variant,
                    ls.text as summary_text,
                    ls.html as summary_html,
                    ls.revision as summary_revision,
                    ls.created_at as summary_created_at
                FROM content c
                LEFT JOIN LATERAL (
                    SELECT s.*
                    FROM v_latest_summaries s
                    WHERE s.video_id = c.video_id
                      AND s.variant IN (
                        'comprehensive','key-points','bullet-points',
                        'executive','key-insights','audio','audio-fr','audio-es'
                      )
                    ORDER BY array_position(
                      ARRAY[
                        'comprehensive','key-points','bullet-points',
                        'executive','key-insights','audio','audio-fr','audio-es'
                      ]::text[],
                      s.variant
                    )
                    LIMIT 1
                ) ls ON true
                WHERE c.video_id = %s AND ls.html IS NOT NULL
            """, [report_id])

            row = cursor.fetchone()
            return dict(row) if row else None

        finally:
            conn.close()

    def search(self, query: str, filters: Dict[str, Any] = None,
               page: int = 1, size: int = 20) -> Tuple[List[Dict[str, Any]], int]:
        """Search reports by title and summary content with variant fallback."""
        if not query or not query.strip():
            return self.get_reports(filters, page=page, size=size)

        conn = self._get_connection()
        try:
            search_term = f"%{query.strip()}%"

            # Search in titles and summaries with variant fallback
            base_query = """
                SELECT
                    c.*,
                    ls.variant as summary_variant,
                    ls.text as summary_text,
                    ls.html as summary_html,
                    ls.revision as summary_revision,
                    ls.created_at as summary_created_at
                FROM content c
                LEFT JOIN LATERAL (
                    SELECT s.*
                    FROM v_latest_summaries s
                    WHERE s.video_id = c.video_id
                      AND s.variant IN (
                        'comprehensive','key-points','bullet-points',
                        'executive','key-insights','audio','audio-fr','audio-es'
                      )
                    ORDER BY array_position(
                      ARRAY[
                        'comprehensive','key-points','bullet-points',
                        'executive','key-insights','audio','audio-fr','audio-es'
                      ]::text[],
                      s.variant
                    )
                    LIMIT 1
                ) ls ON true
                WHERE ls.html IS NOT NULL
                  AND (c.title ILIKE %s OR ls.text ILIKE %s)
            """

            params = [search_term, search_term]

            # Apply additional filters if provided
            if filters:
                # Add filtering logic similar to get_reports
                # (simplified for now - can be expanded)
                pass

            # Count query
            count_query = f"""
                SELECT COUNT(*) as total
                FROM content c
                LEFT JOIN LATERAL (
                    SELECT s.*
                    FROM v_latest_summaries s
                    WHERE s.video_id = c.video_id
                      AND s.variant IN (
                        'comprehensive','key-points','bullet-points',
                        'executive','key-insights','audio','audio-fr','audio-es'
                      )
                    ORDER BY array_position(
                      ARRAY[
                        'comprehensive','key-points','bullet-points',
                        'executive','key-insights','audio','audio-fr','audio-es'
                      ]::text[],
                      s.variant
                    )
                    LIMIT 1
                ) ls ON true
                WHERE ls.html IS NOT NULL
                  AND (c.title ILIKE %s OR ls.text ILIKE %s)
            """

            cursor = conn.cursor()
            cursor.execute(count_query, params)
            total_count = cursor.fetchone()['total']

            # Add sorting and pagination
            query = base_query + """
                ORDER BY
                    CASE WHEN c.title ILIKE %s THEN 1 ELSE 2 END,
                    c.indexed_at DESC
                LIMIT %s OFFSET %s
            """

            offset = (page - 1) * size
            params.extend([search_term, size, offset])

            cursor.execute(query, params)
            rows = cursor.fetchall()

            reports = [dict(row) for row in rows]
            return reports, total_count

        finally:
            conn.close()

    def get_filters(self, active_filters: Optional[Dict[str, Any]] = None) -> Dict[str, List[Dict[str, Any]]]:
        """Get available filter options with counts."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            # Categories (from JSONB analysis)
            cursor.execute("""
                SELECT
                    cat->>'category' as category,
                    COUNT(*) as count
                FROM content c
                CROSS JOIN LATERAL jsonb_array_elements(
                    COALESCE(
                        c.analysis_json->'categories',
                        c.subcategories_json->'categories',
                        '[]'::jsonb
                    )
                ) AS cat
                WHERE cat->>'category' IS NOT NULL
                GROUP BY cat->>'category'
                ORDER BY count DESC, cat->>'category'
                LIMIT 100
            """)
            categories = [{"value": row["category"], "count": row["count"]} for row in cursor.fetchall()]

            # Channels
            cursor.execute("""
                SELECT channel_name AS value, COUNT(*) AS count
                FROM content
                WHERE channel_name IS NOT NULL AND channel_name <> ''
                GROUP BY channel_name
                ORDER BY count DESC
                LIMIT 50
            """)
            channels = [{"value": row["value"], "count": row["count"]} for row in cursor.fetchall()]

            # Years (derived from indexed_at)
            cursor.execute("""
                SELECT CAST(date_part('year', indexed_at) AS INT) AS value, COUNT(*) AS count
                FROM content
                WHERE indexed_at IS NOT NULL
                GROUP BY value
                ORDER BY value DESC
            """)
            years = [{"value": row["value"], "count": row["count"]} for row in cursor.fetchall()]

            # Has Audio
            cursor.execute("""
                SELECT has_audio AS value, COUNT(*) AS count
                FROM content
                GROUP BY has_audio
                ORDER BY count DESC
            """)
            has_audio = [{"value": bool(row["value"]), "count": row["count"]} for row in cursor.fetchall()]

            # Variants (from latest summaries)
            cursor.execute("""
                SELECT variant AS value, COUNT(*) AS count
                FROM v_latest_summaries
                GROUP BY variant
                ORDER BY count DESC
            """)
            variants = [{"value": row["value"], "count": row["count"]} for row in cursor.fetchall()]

            # Languages (if the column exists)
            try:
                cursor.execute("""
                    SELECT language AS value, COUNT(*) AS count
                    FROM content
                    WHERE language IS NOT NULL
                    GROUP BY language
                    ORDER BY count DESC
                """)
                languages = [{"value": row["value"], "count": row["count"]} for row in cursor.fetchall()]
            except:
                languages = []

            return {
                'categories': categories,
                'channels': channels,
                'years': years,
                'has_audio': has_audio,
                'variants': variants,
                'languages': languages
            }

        finally:
            conn.close()

    def search_reports(self,
                      filters: Optional[Dict[str, Any]] = None,
                      query: Optional[str] = None,
                      sort: str = 'newest',
                      page: int = 1,
                      size: int = 20) -> Tuple[List[Dict[str, Any]], int]:
        """Search reports with filters - compatibility method for API."""
        if query and query.strip():
            return self.search(query, filters, page, size)
        else:
            return self.get_reports(filters, sort, page, size)

    def get_facets(self, active_filters: Optional[Dict[str, Any]] = None) -> Dict[str, List[Dict[str, Any]]]:
        """Alias for get_filters() for compatibility with existing API."""
        return self.get_filters(active_filters)