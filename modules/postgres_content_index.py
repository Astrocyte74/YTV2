#!/usr/bin/env python3
"""
PostgreSQL Content Index
High-performance content management using PostgreSQL database.
Designed for parallel PostgreSQL system with variant fallback support.
"""

import os
import json
import logging
from collections import defaultdict, Counter
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

    # ------------------------------------------------------------------
    # Helper utilities (parity with legacy SQLite implementation)
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_datetime(value: Any) -> str:
        """Convert timestamp to ISO string (UTC) for API responses."""
        if not value:
            return ""

        if isinstance(value, datetime):
            dt = value
        else:
            try:
                dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            except ValueError:
                return str(value)

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        return dt.isoformat().replace("+00:00", "Z")

    @staticmethod
    def _parse_json_field(value: Any) -> Any:
        """Parse JSON fields handling strings, dicts, and lists safely."""
        if value is None or value == "":
            return []

        if isinstance(value, (list, dict)):
            return value

        try:
            return json.loads(value)
        except (TypeError, json.JSONDecodeError):
            return value

    def _parse_subcategories_json(self, value: Any) -> List[Dict[str, Any]]:
        """Normalize subcategory payloads to canonical structure."""
        if not value:
            return []

        data = value
        if isinstance(value, str):
            try:
                data = json.loads(value)
            except (TypeError, json.JSONDecodeError):
                return []

        if isinstance(data, dict):
            categories = data.get('categories') or []
        else:
            categories = data

        results: List[Dict[str, Any]] = []
        if not isinstance(categories, list):
            return results

        for item in categories:
            if isinstance(item, dict):
                category = item.get('category') or item.get('name')
                if not category:
                    continue
                subcats = item.get('subcategories') or []
                if isinstance(subcats, list):
                    subcat_list = [str(sub) for sub in subcats]
                elif subcats:
                    subcat_list = [str(subcats)]
                else:
                    subcat_list = []
                results.append({
                    'category': category,
                    'subcategories': subcat_list
                })
            elif isinstance(item, str):
                results.append({
                    'category': item,
                    'subcategories': []
                })

        return results

    @staticmethod
    def _generate_file_stem(video_id: Optional[str], title: Optional[str]) -> str:
        """Generate deterministic file stem used by legacy dashboard routes."""
        if video_id:
            return video_id
        title = title or "unknown"
        safe_title = ''.join(c for c in title.lower() if c.isalnum() or c in '-_')
        return safe_title[:50] or 'unknown'

    def _format_report_for_api(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """Match the legacy SQLite API contract for dashboard consumption."""

        analysis_json = row.get('analysis_json') or {}
        if isinstance(analysis_json, str):
            try:
                analysis_json = json.loads(analysis_json)
            except json.JSONDecodeError:
                analysis_json = {}

        structured_categories = (
            self._parse_subcategories_json(row.get('subcategories_json'))
            or self._parse_subcategories_json(analysis_json.get('categories'))
        )

        primary_categories = [
            item.get('category') for item in structured_categories if item.get('category')
        ]
        first_subcategory = None
        for item in structured_categories:
            subs = item.get('subcategories') or []
            if subs:
                first_subcategory = subs[0]
                break

        topics = analysis_json.get('key_topics')
        if not topics:
            parsed_topics = self._parse_json_field(row.get('topics_json'))
            topics = parsed_topics if isinstance(parsed_topics, list) else []

        named_entities = analysis_json.get('named_entities')
        if not isinstance(named_entities, list):
            named_entities = []

        language = analysis_json.get('language') or 'en'

        # Summary metadata (only attached for detailed view, but we pass through here)
        summary_variant = row.get('summary_variant') or 'comprehensive'
        summary_text = row.get('summary_text')
        summary_html = row.get('summary_html')

        subcategories_raw = row.get('subcategories_json')
        if isinstance(subcategories_raw, str):
            subcategories_json = subcategories_raw
        elif subcategories_raw is not None:
            subcategories_json = json.dumps(subcategories_raw, ensure_ascii=False)
        else:
            subcategories_json = None

        content_dict = {
            'id': row.get('id') or row.get('video_id') or '',
            'title': row.get('title') or 'Untitled',
            'thumbnail_url': row.get('thumbnail_url') or '',
            'canonical_url': row.get('canonical_url') or '',
            'channel': row.get('channel_name') or '',
            'channel_name': row.get('channel_name') or '',
            'published_at': self._normalize_datetime(row.get('published_at')),
            'duration_seconds': row.get('duration_seconds') or 0,
            'analysis': {
                'category': primary_categories,
                'subcategory': first_subcategory,
                'categories': structured_categories,
                'content_type': analysis_json.get('content_type') or '',
                'complexity_level': analysis_json.get('complexity_level')
                                       or analysis_json.get('complexity')
                                       or '',
                'language': language,
                'key_topics': topics,
                'named_entities': named_entities
            },
            'media': {
                'has_audio': bool(row.get('has_audio', False)),  # Explicit default to False
                'audio_duration_seconds': analysis_json.get('audio_duration_seconds', 0),
                'has_transcript': analysis_json.get('has_transcript', False),
                'transcript_chars': analysis_json.get('transcript_chars', 0)
            },
            'media_metadata': {
                'video_duration_seconds': row.get('duration_seconds') or 0,
                'mp3_duration_seconds': analysis_json.get('audio_duration_seconds', 0)
            },
            'file_stem': self._generate_file_stem(row.get('video_id'), row.get('title')),
            'video_id': row.get('video_id') or '',
            'subcategories_json': subcategories_json,
            'indexed_at': self._normalize_datetime(row.get('indexed_at')),
            'original_language': language,
            'summary_language': language,
            'audio_language': language,
            'word_count': analysis_json.get('word_count', 0)
        }

        # Attach summary payload for downstream consumers when available
        if summary_text or summary_html:
            content_dict['summary_text'] = summary_text or ''
            content_dict['summary_html'] = summary_html or ''
            content_dict['summary_variant'] = summary_variant

        return content_dict

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

                # Content type filters - REMOVED (column doesn't exist in PostgreSQL schema)
                # if 'content_type' in filters and filters['content_type']:
                #     content_types = filters['content_type'] if isinstance(filters['content_type'], list) else [filters['content_type']]
                #     type_placeholders = ','.join(['%s'] * len(content_types))
                #     where_conditions.append(f"c.content_type IN ({type_placeholders})")
                #     params.extend(content_types)

                # Complexity filters - REMOVED (complexity_level column doesn't exist in PostgreSQL schema)
                # if 'complexity' in filters and filters['complexity']:
                #     complexities = filters['complexity'] if isinstance(filters['complexity'], list) else [filters['complexity']]
                #     complexity_placeholders = ','.join(['%s'] * len(complexities))
                #     where_conditions.append(f"c.complexity_level IN ({complexity_placeholders})")
                #     params.extend(complexities)

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

            formatted_reports = [self._format_report_for_api(dict(row)) for row in rows]

            return formatted_reports, total_count

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
                WHERE (c.video_id = %s OR c.id = %s) AND ls.html IS NOT NULL
            """, [report_id, report_id])

            row = cursor.fetchone()
            if not row:
                return None

            formatted = self._format_report_for_api(dict(row))

            summary_text = row.get('summary_text') or ''
            summary_html = row.get('summary_html') or ''
            summary_variant = row.get('summary_variant') or 'comprehensive'

            if summary_text or summary_html:
                formatted['summary'] = {
                    'text': summary_text or 'No summary available.',
                    'html': summary_html or '',
                    'type': summary_variant,
                    'content': {
                        'summary': summary_text or 'No summary available.',
                        'summary_type': summary_variant
                    }
                }
            else:
                formatted['summary'] = {
                    'text': 'No summary available.',
                    'html': '',
                    'type': 'none',
                    'content': {
                        'summary': 'No summary available.',
                        'summary_type': 'none'
                    }
                }

            formatted['processor_info'] = {
                'model': 'postgres_backend',
                'processing_time': 0,
                'timestamp': formatted.get('indexed_at', '')
            }

            return formatted

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

            reports = [self._format_report_for_api(dict(row)) for row in rows]
            return reports, total_count

        finally:
            conn.close()

    def get_filters(self, active_filters: Optional[Dict[str, Any]] = None) -> Dict[str, List[Dict[str, Any]]]:
        """Build filter payload matching legacy SQLite structure."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT channel_name,
                       COALESCE(has_audio, FALSE) AS has_audio,
                       analysis_json,
                       subcategories_json
                FROM content
            """)
            rows = cursor.fetchall()

            total_count = len(rows)

            language_counter: Counter[str] = Counter()
            content_type_counter: Counter[str] = Counter()
            complexity_counter: Counter[str] = Counter()
            channel_counter: Counter[str] = Counter()
            has_audio_counter: Counter[bool] = Counter()
            category_hierarchy: Dict[str, Dict[str, Any]] = {}

            for row in rows:
                analysis_json = row.get('analysis_json') or {}
                if isinstance(analysis_json, str):
                    try:
                        analysis_json = json.loads(analysis_json)
                    except json.JSONDecodeError:
                        analysis_json = {}

                language = analysis_json.get('language')
                if language:
                    language_counter[language] += 1

                content_type = analysis_json.get('content_type')
                if content_type:
                    content_type_counter[content_type] += 1

                complexity = analysis_json.get('complexity_level') or analysis_json.get('complexity')
                if complexity:
                    complexity_counter[complexity] += 1

                channel = row.get('channel_name') or ''
                if channel:
                    channel_counter[channel] += 1

                has_audio_counter[bool(row.get('has_audio'))] += 1

                structured_categories = (
                    self._parse_subcategories_json(row.get('subcategories_json'))
                    or self._parse_subcategories_json(analysis_json.get('categories'))
                )

                if structured_categories:
                    for cat_obj in structured_categories:
                        cat_name = cat_obj.get('category')
                        if not cat_name:
                            continue
                        entry = category_hierarchy.setdefault(cat_name, {
                            'count': 0,
                            'subcategories': defaultdict(int)
                        })
                        entry['count'] += 1
                        for subcat in cat_obj.get('subcategories', []):
                            if subcat:
                                entry['subcategories'][subcat] += 1
                else:
                    fallback_categories = analysis_json.get('category')
                    if isinstance(fallback_categories, str):
                        fallback_categories = [fallback_categories]
                    if isinstance(fallback_categories, list):
                        for cat_name in fallback_categories:
                            if not cat_name:
                                continue
                            entry = category_hierarchy.setdefault(cat_name, {
                                'count': 0,
                                'subcategories': defaultdict(int)
                            })
                            entry['count'] += 1

            filters: Dict[str, List[Dict[str, Any]]] = {}
            filters['source'] = [{'value': 'youtube', 'count': total_count}]

            filters['languages'] = [  # Changed to plural for JS compatibility
                {'value': lang, 'count': count}
                for lang, count in language_counter.most_common()
            ]

            category_items: List[Dict[str, Any]] = []
            for cat, data in sorted(category_hierarchy.items(), key=lambda x: x[1]['count'], reverse=True):
                item = {
                    'value': cat,
                    'count': data['count']
                }
                if data['subcategories']:
                    item['subcategories'] = [
                        {'value': subcat, 'count': subcount}
                        for subcat, subcount in sorted(data['subcategories'].items(), key=lambda x: x[1], reverse=True)
                    ]
                category_items.append(item)
            filters['categories'] = category_items  # Changed to plural for JS compatibility

            filters['content_type'] = [
                {'value': value, 'count': count}
                for value, count in content_type_counter.most_common()
            ]

            filters['complexity_level'] = [
                {'value': value, 'count': count}
                for value, count in complexity_counter.most_common()
            ]

            filters['channels'] = [  # Changed to plural for JS compatibility
                {'value': value, 'count': count}
                for value, count in channel_counter.most_common()
            ]

            filters['has_audio'] = [
                {'value': bool_val, 'count': count}
                for bool_val, count in sorted(has_audio_counter.items(), key=lambda x: (-x[1], not x[0]))
            ]

            return filters

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

    # ------------------------------------------------------------------
    # Ingest methods for NAS sync (T-Y020C)
    # ------------------------------------------------------------------

    def _ensure_unique_constraints(self):
        """Ensure required unique constraints exist for upsert operations."""
        conn = None
        try:
            conn = self._get_connection()
            cur = conn.cursor()

            # Ensure unique index on video_id for ON CONFLICT clause
            cur.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS ux_content_video_id
                ON content (video_id)
            """)
            conn.commit()
            logger.info("Ensured unique constraint on content.video_id")

        except Exception:
            logger.exception("Error ensuring unique constraints")
        finally:
            if conn:
                conn.close()

    def _as_json_string(self, v):
        """Normalize input to JSON string for PostgreSQL JSONB columns."""
        if v is None:
            return None
        if isinstance(v, (dict, list)):
            return json.dumps(v)
        if isinstance(v, str):
            # If it's already JSON, keep it; if it's plain text, store as JSON string
            try:
                json.loads(v)
                return v
            except:
                return json.dumps(v)
        return None

    def upsert_content(self, data: dict) -> bool:
        """Insert or update content record with ON CONFLICT handling."""
        # Ensure unique constraints exist (idempotent)
        self._ensure_unique_constraints()

        conn = None
        try:
            conn = self._get_connection()
            cur = conn.cursor()

            # Normalize JSON fields with robust helper
            subcategories_json = self._as_json_string(data.get("subcategories_json"))
            analysis_json = self._as_json_string(data.get("analysis_json"))
            topics_json = self._as_json_string(data.get("topics_json"))

            # Prepare media JSONB (preserve existing media data)
            media_data = data.get("media", {})
            if isinstance(media_data, str):
                try:
                    media_data = json.loads(media_data)
                except:
                    media_data = {}

            upsert_sql = """
            INSERT INTO content (
                video_id, title, channel_name, indexed_at, duration_seconds,
                thumbnail_url, canonical_url, subcategories_json, analysis_json, topics_json, has_audio
            ) VALUES (
                %(video_id)s, %(title)s, %(channel_name)s, %(indexed_at)s, %(duration_seconds)s,
                %(thumbnail_url)s, %(canonical_url)s, %(subcategories_json)s, %(analysis_json)s, %(topics_json)s, %(has_audio)s
            )
            ON CONFLICT (video_id) DO UPDATE SET
                title = EXCLUDED.title,
                channel_name = EXCLUDED.channel_name,
                indexed_at = EXCLUDED.indexed_at,
                duration_seconds = EXCLUDED.duration_seconds,
                thumbnail_url = EXCLUDED.thumbnail_url,
                canonical_url = EXCLUDED.canonical_url,
                subcategories_json = EXCLUDED.subcategories_json,
                analysis_json = EXCLUDED.analysis_json,
                topics_json = EXCLUDED.topics_json,
                has_audio = EXCLUDED.has_audio,
                updated_at = NOW()
            RETURNING video_id;
            """

            # Safe has_audio detection
            has_audio = False
            if media_data:
                has_audio = bool(media_data.get('has_audio')) or bool(media_data.get('audio_url'))

            # Safe defaults for NOT NULL columns (per OpenAI debugging guidance)
            params = {
                'video_id': data.get('video_id'),
                'title': data.get('title') or '(untitled)',
                'channel_name': data.get('channel_name') or '(unknown)',
                'indexed_at': data.get('indexed_at') or datetime.now(timezone.utc).isoformat(),
                'duration_seconds': data.get('duration_seconds'),
                'thumbnail_url': data.get('thumbnail_url'),
                'canonical_url': data.get('canonical_url'),
                'subcategories_json': subcategories_json,
                'analysis_json': analysis_json,
                'topics_json': topics_json,
                'has_audio': has_audio
            }

            logger.info(f"Executing upsert for {data.get('video_id')} with params: {list(params.keys())}")
            cur.execute(upsert_sql, params)

            # Must have at least one row RETURNED
            returned = cur.fetchone()
            if not returned:
                logger.error("Upsert returned no row for %s", data.get('video_id'))
                conn.rollback()
                return False

            # rowcount should be 1 for INSERT or UPDATE
            if cur.rowcount != 1:
                logger.error("Unexpected rowcount %s for %s", cur.rowcount, data.get('video_id'))
                conn.rollback()
                return False

            conn.commit()

            # Post-commit verification in the same connection string/role
            cur = conn.cursor()
            cur.execute("SELECT 1 FROM content WHERE video_id=%s", (data.get('video_id'),))
            ok = cur.fetchone() is not None
            logger.info("Post-upsert verify for %s: %s", data.get('video_id'), ok)
            return bool(ok)

        except Exception:
            logger.exception("Error upserting content %s", data.get('video_id', 'unknown'))
            if conn:
                try:
                    conn.rollback()
                except:
                    pass
            return False
        finally:
            if conn:
                conn.close()

    def get_by_video_id(self, video_id: str):
        """Get a single content record by video_id for verification."""
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT video_id, title, channel_name, indexed_at
                FROM content WHERE video_id=%s
            """, (video_id,))
            r = cur.fetchone()
            if not r:
                return None
            # RealDictCursor returns dict
            if isinstance(r, dict):
                return r
            # Fallback for tuple cursor
            return {
                "video_id": r[0],
                "title": r[1],
                "channel_name": r[2],
                "indexed_at": r[3].isoformat() if r[3] else None
            }
        finally:
            conn.close()

    def upsert_summaries(self, video_id: str, variants: list) -> int:
        """Insert summary variants with automatic latest-pointer management."""
        if not variants:
            return 0

        conn = None
        try:
            conn = self._get_connection()
            cur = conn.cursor()
            count = 0
            for variant in variants:
                insert_sql = """
                INSERT INTO content_summaries (
                    video_id, variant, text, html, revision, is_latest, created_at
                ) VALUES (
                    %s, %s, %s, %s, %s, true, NOW()
                )
                """

                # Note: Triggers will automatically set is_latest=false for older rows
                cur.execute(insert_sql, [
                    video_id,
                    variant.get('variant', 'comprehensive'),
                    variant.get('text', ''),
                    variant.get('html', ''),
                    variant.get('revision', 1)
                ])
                count += 1

            conn.commit()
            return count

        except Exception as e:
            logger.error(f"Error upserting summaries for {video_id}: {e}")
            return 0
        finally:
            if conn:
                conn.close()

    def update_media_audio_url(self, video_id: str, audio_url: str) -> None:
        """Update content.analysis_json with audio_url field and set has_audio=true."""
        conn = None
        try:
            conn = self._get_connection()
            cur = conn.cursor()
            update_sql = """
            UPDATE content
            SET analysis_json = jsonb_set(
                COALESCE(analysis_json, '{}'::jsonb),
                '{audio_url}',
                to_jsonb(%s::text),
                true
            ),
            has_audio = true,
            updated_at = NOW()
            WHERE video_id = %s
            """

            cur.execute(update_sql, [audio_url, video_id])
            conn.commit()

        except Exception as e:
            logger.error(f"Error updating audio URL for {video_id}: {e}")
        finally:
            if conn:
                conn.close()
