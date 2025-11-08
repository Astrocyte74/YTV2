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

    SUMMARY_VARIANT_ORDER: List[str] = [
        'key-insights',
        'bullet-points',
        'comprehensive',
        'key-points',
        'executive',
        'audio',
        'audio-fr',
        'audio-es',
        'language'
    ]

    SOURCE_LABELS = {
        'youtube': 'YouTube',
        'reddit': 'Reddit',
        'wikipedia': 'Wikipedia',
        'lds': 'Gospel Library',
        'web': 'Web',
        'other': 'Other'
    }

    @classmethod
    def _variant_order_expression(cls, alias: str = 'vs') -> str:
        clauses = []
        for idx, variant in enumerate(cls.SUMMARY_VARIANT_ORDER):
            if variant == 'language':
                continue
            clauses.append(f"WHEN {alias}.variant = '{variant}' THEN {idx}")

        default_rank = len(clauses) + 1
        case_expression = "CASE " + " ".join(clauses) + f" ELSE {default_rank} END"
        return case_expression

    def __init__(self, postgres_url: str = None):
        """Initialize with PostgreSQL connection."""
        if not PSYCOPG2_AVAILABLE:
            raise ImportError("psycopg2 not available. Install with: pip install psycopg2-binary")

        self.postgres_url = postgres_url or os.getenv('DATABASE_URL_POSTGRES_NEW')
        if not self.postgres_url:
            raise ValueError("PostgreSQL URL not provided and DATABASE_URL_POSTGRES_NEW not set")

        logger.info(f"Using PostgreSQL database")
        self._content_source_column_present: Optional[bool] = None

    def _get_connection(self):
        """Get PostgreSQL connection with RealDictCursor."""
        return psycopg2.connect(
            self.postgres_url,
            cursor_factory=psycopg2.extras.RealDictCursor
        )

    def _has_content_source_column(self, conn=None) -> bool:
        """Detect whether the content table exposes an explicit content_source column."""
        if self._content_source_column_present is None:
            close_conn = False
            cursor = None
            try:
                if conn is None:
                    conn = self._get_connection()
                    close_conn = True
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_name = %s AND column_name = %s
                    LIMIT 1
                    """,
                    ('content', 'content_source')
                )
                self._content_source_column_present = cursor.fetchone() is not None
            except Exception:
                logger.exception("Failed to detect content.content_source column")
                self._content_source_column_present = False
            finally:
                if cursor:
                    cursor.close()
                if close_conn and conn:
                    conn.close()
        return bool(self._content_source_column_present)

    def _source_case_expression(self, alias: str = 'c', conn=None) -> str:
        """Build SQL CASE expression that normalizes source slugs without schema assumptions."""
        clauses = ["CASE"]
        if self._has_content_source_column(conn):
            clauses.append(
                f"WHEN TRIM(COALESCE({alias}.content_source, '')) <> '' "
                f"THEN LOWER(TRIM({alias}.content_source))"
            )

        canonical = f"LOWER(COALESCE({alias}.canonical_url::text, ''))"
        video_id = f"LOWER(COALESCE({alias}.video_id::text, ''))"
        record_id = f"LOWER(COALESCE({alias}.id::text, ''))"

        # Double percent signs to avoid psycopg2 placeholder parsing
        clauses.append(
            f"WHEN {canonical} LIKE '%%wikipedia.org%%' THEN 'wikipedia'"
        )
        clauses.append(
            f"WHEN {canonical} LIKE '%%churchofjesuschrist.org%%' "
            f"OR {canonical} LIKE '%%lds.org%%' THEN 'lds'"
        )
        clauses.append(
            f"WHEN {canonical} LIKE '%%reddit.com%%' "
            f"OR {video_id} LIKE 'reddit:%%' "
            f"OR {record_id} LIKE 'reddit:%%' THEN 'reddit'"
        )
        clauses.append(
            f"WHEN {canonical} LIKE '%%youtube.com%%' "
            f"OR {canonical} LIKE '%%youtu.be%%' "
            f"OR {video_id} ~ '^[a-z0-9_-]{{11}}$' THEN 'youtube'"
        )
        clauses.append("WHEN TRIM(COALESCE({0}.canonical_url::text, '')) = '' THEN 'other'".format(alias))
        clauses.append("ELSE 'web'")
        clauses.append("END")
        return " ".join(clauses)

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

    @classmethod
    def _infer_content_source(
        cls,
        explicit: Optional[str],
        canonical_url: Optional[str],
        video_id: Optional[str],
        record_id: Optional[str]
    ) -> str:
        """Infer a normalized content source slug."""
        known = set(cls.SOURCE_LABELS.keys())

        def _clean(value: Optional[str]) -> str:
            return str(value or '').strip().lower()

        explicit_slug = _clean(explicit)
        if explicit_slug in known:
            return explicit_slug

        canonical = _clean(canonical_url)
        vid = _clean(video_id)
        rec = _clean(record_id)

        if not canonical and not vid and not rec:
            return 'other'

        # Domain-based detection
        if 'wikipedia.org' in canonical:
            return 'wikipedia'
        if 'churchofjesuschrist.org' in canonical or 'lds.org' in canonical:
            return 'lds'
        if 'reddit.com' in canonical:
            return 'reddit'
        if 'youtube.com' in canonical or 'youtu.be' in canonical:
            return 'youtube'

        # Identifier-based detection
        if vid.startswith('reddit:') or rec.startswith('reddit:'):
            return 'reddit'
        if len(vid) == 11 and all(ch.isalnum() or ch in '-_' for ch in vid):
            return 'youtube'

        return 'web'

    def _format_report_for_api(
        self,
        row: Dict[str, Any]
    ) -> Dict[str, Any]:
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

        normalized_source = row.get('normalized_source')
        inferred_source = self._infer_content_source(
            normalized_source or row.get('content_source'),
            row.get('canonical_url'),
            row.get('video_id'),
            row.get('id')
        )
        source_label = self.SOURCE_LABELS.get(inferred_source, inferred_source.title())

        # Pass through audio/media flags from content row
        has_audio = bool(row.get('has_audio'))
        media_json = row.get('media') or {}
        if isinstance(media_json, str):
            try:
                media_json = json.loads(media_json)
            except json.JSONDecodeError:
                media_json = {}
        media_metadata_json = row.get('media_metadata') or {}
        if isinstance(media_metadata_json, str):
            try:
                media_metadata_json = json.loads(media_metadata_json)
            except json.JSONDecodeError:
                media_metadata_json = {}

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
            # New: secondary, model-generated illustration URL if present
            'summary_image_url': row.get('summary_image_url') or None,
            'canonical_url': row.get('canonical_url') or '',
            'channel': row.get('channel_name') or '',
            'channel_name': row.get('channel_name') or '',
            'content_source': inferred_source,
            'source': inferred_source,
            'source_label': source_label,
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
                'named_entities': named_entities,
                # Image prompt + variants pass-through for UI
                'summary_image_prompt': analysis_json.get('summary_image_prompt'),
                'summary_image_prompt_last_used': analysis_json.get('summary_image_prompt_last_used'),
                'summary_image_selected_url': analysis_json.get('summary_image_selected_url'),
                'summary_image_variants': analysis_json.get('summary_image_variants'),
                # AI2 support: expose explicit AI2 URL when present
                'summary_image_ai2_url': analysis_json.get('summary_image_ai2_url')
            },
            'media': {
                'has_audio': bool(row.get('has_audio', False)),
                'audio_duration_seconds': analysis_json.get('audio_duration_seconds', 0),
                'has_transcript': analysis_json.get('has_transcript', False),
                'transcript_chars': analysis_json.get('transcript_chars', 0),
                # Surface audio_url from content.media when available
                'audio_url': (media_json.get('audio_url') if isinstance(media_json, dict) else None),
                # Mirror image URL inside media for convenience (optional consumer)
                'summary_image_url': row.get('summary_image_url') or None
            },
            'media_metadata': {
                'video_duration_seconds': row.get('duration_seconds') or 0,
                # Prefer authoritative mp3 duration from media_metadata, fallback to analysis_json
                'mp3_duration_seconds': (
                    (int(media_metadata_json.get('mp3_duration_seconds')) if isinstance(media_metadata_json, dict) and str(media_metadata_json.get('mp3_duration_seconds', '')).strip() not in ('', 'None') else None)
                ) or analysis_json.get('audio_duration_seconds', 0)
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

        # If backend stored an explicit audio_url in analysis_json, surface it in media
        try:
            audio_url_in_analysis = analysis_json.get('audio_url')
            if isinstance(audio_url_in_analysis, str) and audio_url_in_analysis.strip():
                content_dict['media']['audio_url'] = audio_url_in_analysis.strip()
                # Ensure has_audio reflects presence of a concrete URL
                content_dict['media']['has_audio'] = True
        except Exception:
            pass

        # Attach summary payload for downstream consumers when available
        if summary_text or summary_html:
            content_dict['summary_text'] = summary_text or ''
            content_dict['summary_html'] = summary_html or ''
            content_dict['summary_variant'] = summary_variant

        summary_variants_raw = row.get('summary_variants')
        parsed_variants = self._parse_json_field(summary_variants_raw)
        variant_order = {name: idx for idx, name in enumerate(self.SUMMARY_VARIANT_ORDER)}
        cleaned_variants: List[Dict[str, Any]] = []

        if isinstance(parsed_variants, list):
            for item in parsed_variants:
                if not isinstance(item, dict):
                    continue

                variant_id = str(item.get('variant', '')).strip().lower()
                if not variant_id or variant_id == 'language':
                    continue

                text_value = item.get('text') or ''
                html_value = item.get('html') or ''
                if not text_value and not html_value:
                    continue

                summary_type_value = item.get('summary_type') or variant_id
                if isinstance(summary_type_value, str):
                    summary_type_value = summary_type_value.strip().lower() or variant_id

                kind_value = item.get('kind') or ('audio' if variant_id.startswith('audio') else 'text')
                generated_at_value = self._normalize_datetime(item.get('generated_at')) if item.get('generated_at') else ''

                cleaned_entry: Dict[str, Any] = {
                    'variant': variant_id,
                    'summary_type': summary_type_value,
                    'text': text_value,
                    'html': html_value,
                    'kind': kind_value
                }

                if generated_at_value:
                    cleaned_entry['generated_at'] = generated_at_value

                language_value = item.get('language')
                if language_value:
                    cleaned_entry['language'] = str(language_value)

                headline_value = item.get('headline')
                if headline_value:
                    cleaned_entry['headline'] = str(headline_value)

                # Pass through audio enrichment when present on the source item
                try:
                    if kind_value == 'audio':
                        au = item.get('audio_url')
                        if isinstance(au, str) and au.strip():
                            cleaned_entry['audio_url'] = au.strip()
                        dur = item.get('duration')
                        # Accept both str and int; coerce to int when possible
                        if isinstance(dur, str) and dur.isdigit():
                            cleaned_entry['duration'] = int(dur)
                        elif isinstance(dur, (int, float)):
                            cleaned_entry['duration'] = int(dur)
                except Exception:
                    pass

                cleaned_variants.append(cleaned_entry)

        cleaned_variants.sort(
            key=lambda item: (
                variant_order.get(item['variant'], len(variant_order)),
                item.get('generated_at') or ''
            )
        )

        content_dict['summary_variants'] = cleaned_variants

        # Hint has_audio=true when an audio variant exists even if c.has_audio is false.
        # This enables the Listen button without requiring a separate backfill.
        try:
            media_dict = content_dict.get('media') or {}
            if not bool(media_dict.get('has_audio')):
                if any(
                    isinstance(v, dict) and (
                        v.get('kind') == 'audio' or str(v.get('variant', '')).startswith('audio')
                    ) for v in cleaned_variants
                ):
                    media_dict['has_audio'] = True
                    content_dict['media'] = media_dict
        except Exception:
            pass

        return content_dict

    def get_reports(self, filters: Dict[str, Any] = None, sort: str = "newest",
                   page: int = 1, size: int = 20) -> Tuple[List[Dict[str, Any]], int]:
        """Get paginated and filtered reports with variant precedence fallback."""

        conn = self._get_connection()
        try:
            variant_order_sql = self._variant_order_expression('vs')
            source_case = self._source_case_expression('c', conn)

            # Build base query with summary fallback plus variant aggregation
            query = f"""
                SELECT
                    c.*,
                    {source_case} AS normalized_source,
                    ls.variant as summary_variant,
                    ls.text as summary_text,
                    ls.html as summary_html,
                    ls.revision as summary_revision,
                    ls.created_at as summary_created_at,
                    variants.summary_variants AS summary_variants
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
                LEFT JOIN LATERAL (
                    SELECT json_agg(
                        json_build_object(
                            'variant', lower(trim(vs.variant)),
                            'summary_type', lower(trim(vs.variant)),
                            'text', vs.text,
                            'html', vs.html,
                            'generated_at', vs.created_at,
                            'kind', CASE WHEN vs.variant LIKE 'audio%%' THEN 'audio' ELSE 'text' END,
                            'language', CASE WHEN vs.variant LIKE 'audio-%%' THEN split_part(vs.variant, '-', 2) ELSE NULL END,
                            -- Surface audio_url and duration alongside audio variants using content JSONB
                            'audio_url', CASE WHEN vs.variant LIKE 'audio%%'
                                              THEN COALESCE(c.media->>'audio_url', c.analysis_json->>'audio_url')
                                              ELSE NULL END,
                            'duration', CASE WHEN vs.variant LIKE 'audio%%'
                                             THEN NULLIF((c.media_metadata->>'mp3_duration_seconds'), '')::int
                                             ELSE NULL END
                        )
                        ORDER BY {variant_order_sql}, vs.created_at DESC
                    ) AS summary_variants
                    FROM v_latest_summaries vs
                    WHERE vs.video_id = c.video_id
                      AND (vs.text IS NOT NULL OR vs.html IS NOT NULL)
                      AND vs.variant <> 'language'
                ) variants ON true
                WHERE ls.html IS NOT NULL
            """
            params: List[Any] = []
            where_conditions: List[str] = []

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

                # Source filters
                if 'source' in filters and filters['source']:
                    sources = filters['source'] if isinstance(filters['source'], list) else [filters['source']]
                    normalized_sources = [
                        str(source).strip().lower()
                        for source in sources
                        if str(source).strip()
                    ]
                    if normalized_sources:
                        logger.info("Applying source filters: %s", normalized_sources)
                        placeholders = ','.join(['%s'] * len(normalized_sources))
                        where_conditions.append(f"({source_case}) IN ({placeholders})")
                        params.extend(normalized_sources)

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

                # Summary type filter - convert user-friendly names to database variants
                if 'summary_type' in filters and filters['summary_type']:
                    summary_types = filters['summary_type'] if isinstance(filters['summary_type'], list) else [filters['summary_type']]
                    # Convert user-friendly names to database variants
                    database_variants = [self._get_database_variant(st) for st in summary_types]
                    where_conditions.append("COALESCE(ls.variant, 'unknown') = ANY(%s)")
                    params.append(database_variants)

            where_clause = ""
            if where_conditions:
                where_clause = " AND " + " AND ".join(where_conditions)

            base_count_query = """
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
            count_query = base_count_query + where_clause

            cursor = conn.cursor()
            count_params = list(params)
            try:
                placeholder_count = count_query.count('%s')
                logger.info(
                    "Count placeholders=%s param_count=%s where_clause=%s",
                    placeholder_count,
                    len(count_params),
                    where_clause
                )
                bound_params = count_params[:placeholder_count]
                if placeholder_count != len(count_params):
                    logger.debug(
                        "Trimming count params to match placeholders: was %s now %s",
                        len(count_params),
                        len(bound_params)
                    )
                if bound_params:
                    cursor.execute(count_query, bound_params)
                else:
                    cursor.execute(count_query)
            except Exception:
                logger.exception(
                    "Count query failed for get_reports",
                    extra={
                        "sql": count_query,
                        "param_length": len(count_params),
                        "params_snapshot": list(count_params)[:10]
                    }
                )
                raise
            total_count = cursor.fetchone()['total']

            sort_clause = " ORDER BY c.indexed_at DESC"
            if sort == "video_newest":
                sort_clause = " ORDER BY c.published_at DESC"
            elif sort == "title_az":
                sort_clause = " ORDER BY c.title ASC"
            elif sort == "title_za":
                sort_clause = " ORDER BY c.title DESC"
            elif sort == "channel_az":
                sort_clause = " ORDER BY c.channel_name ASC"
            elif sort == "channel_za":
                sort_clause = " ORDER BY c.channel_name DESC"

            size = int(size or 20)
            offset = (page - 1) * size
            final_query = query + where_clause + sort_clause + f" LIMIT {size} OFFSET {offset}"

            try:
                placeholder_count = final_query.count('%s')
                logger.info(
                    "Main placeholders=%s param_count=%s sql_ordered=%s",
                    placeholder_count,
                    len(params),
                    sort_clause
                )
                bound_params = params[:placeholder_count]
                if placeholder_count != len(params):
                    logger.debug(
                        "Trimming main params to match placeholders: was %s now %s",
                        len(params),
                        len(bound_params)
                    )
                if bound_params:
                    cursor.execute(final_query, bound_params)
                else:
                    cursor.execute(final_query)
            except Exception:
                logger.error(
                    "Main query failed for get_reports: params=%s count=%s placeholders=%s sql=%s",
                    params,
                    len(params),
                    final_query.count('%s'),
                    final_query,
                    exc_info=True
                )
                raise
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
            variant_order_sql = self._variant_order_expression('vs')
            cursor.execute(
                f"""
                SELECT
                    c.*,
                    ls.variant as summary_variant,
                    ls.text as summary_text,
                    ls.html as summary_html,
                    ls.revision as summary_revision,
                    ls.created_at as summary_created_at,
                    variants.summary_variants AS summary_variants
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
                LEFT JOIN LATERAL (
                    SELECT json_agg(
                        json_build_object(
                            'variant', lower(trim(vs.variant)),
                            'summary_type', lower(trim(vs.variant)),
                            'text', vs.text,
                            'html', vs.html,
                            'generated_at', vs.created_at,
                            'kind', CASE WHEN vs.variant LIKE 'audio%%' THEN 'audio' ELSE 'text' END,
                            'language', CASE WHEN vs.variant LIKE 'audio-%%' THEN split_part(vs.variant, '-', 2) ELSE NULL END,
                            'audio_url', CASE WHEN vs.variant LIKE 'audio%%'
                                              THEN COALESCE(c.media->>'audio_url', c.analysis_json->>'audio_url')
                                              ELSE NULL END,
                            'duration', CASE WHEN vs.variant LIKE 'audio%%'
                                             THEN NULLIF((c.media_metadata->>'mp3_duration_seconds'), '')::int
                                             ELSE NULL END
                        )
                        ORDER BY {variant_order_sql}, vs.created_at DESC
                    ) AS summary_variants
                    FROM v_latest_summaries vs
                    WHERE vs.video_id = c.video_id
                      AND (vs.text IS NOT NULL OR vs.html IS NOT NULL)
                      AND vs.variant <> 'language'
                ) variants ON true
                WHERE (c.video_id = %s OR c.id = %s) AND ls.html IS NOT NULL
                """,
                [report_id, report_id]
            )

            row = cursor.fetchone()
            if not row:
                return None

            row_dict = dict(row)

            formatted = self._format_report_for_api(row_dict)

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
            variant_order_sql = self._variant_order_expression('vs')
            source_case = self._source_case_expression('c', conn)
            base_query = f"""
                SELECT
                    c.*,
                    {source_case} AS normalized_source,
                    ls.variant as summary_variant,
                    ls.text as summary_text,
                    ls.html as summary_html,
                    ls.revision as summary_revision,
                    ls.created_at as summary_created_at,
                    variants.summary_variants AS summary_variants
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
                LEFT JOIN LATERAL (
                    SELECT json_agg(
                        json_build_object(
                            'variant', lower(trim(vs.variant)),
                            'summary_type', lower(trim(vs.variant)),
                            'text', vs.text,
                            'html', vs.html,
                            'generated_at', vs.created_at,
                            'kind', CASE WHEN vs.variant LIKE 'audio%%' THEN 'audio' ELSE 'text' END,
                            'language', CASE WHEN vs.variant LIKE 'audio-%%' THEN split_part(vs.variant, '-', 2) ELSE NULL END
                        )
                        ORDER BY {variant_order_sql}, vs.created_at DESC
                    ) AS summary_variants
                    FROM v_latest_summaries vs
                    WHERE vs.video_id = c.video_id
                      AND (vs.text IS NOT NULL OR vs.html IS NOT NULL)
                      AND vs.variant <> 'language'
                ) variants ON true
                WHERE ls.html IS NOT NULL
                  AND (c.title ILIKE %s OR ls.text ILIKE %s)
            """

            params: List[Any] = [search_term, search_term]
            where_conditions: List[str] = []

            # Apply additional filters if provided
            if filters:
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

                if 'source' in filters and filters['source']:
                    sources = filters['source'] if isinstance(filters['source'], list) else [filters['source']]
                    normalized_sources = [
                        str(source).strip().lower()
                        for source in sources
                        if str(source).strip()
                    ]
                    if normalized_sources:
                        where_conditions.append(f"({source_case}) = ANY(%s)")
                        params.append(normalized_sources)

                if 'channel' in filters and filters['channel']:
                    channels = filters['channel'] if isinstance(filters['channel'], list) else [filters['channel']]
                    channel_placeholders = ','.join(['%s'] * len(channels))
                    where_conditions.append(f"c.channel_name IN ({channel_placeholders})")
                    params.extend(channels)

                if 'language' in filters and filters['language']:
                    languages = filters['language'] if isinstance(filters['language'], list) else [filters['language']]
                    lang_placeholders = ','.join(['%s'] * len(languages))
                    where_conditions.append(f"c.language IN ({lang_placeholders})")
                    params.extend(languages)

                if 'has_audio' in filters:
                    where_conditions.append("c.has_audio = %s")
                    params.append(filters['has_audio'])

                if 'summary_type' in filters and filters['summary_type']:
                    summary_types = filters['summary_type'] if isinstance(filters['summary_type'], list) else [filters['summary_type']]
                    database_variants = [self._get_database_variant(st) for st in summary_types]
                    where_conditions.append("COALESCE(ls.variant, 'unknown') = ANY(%s)")
                    params.append(database_variants)

            if where_conditions:
                base_query += " AND " + " AND ".join(where_conditions)

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

            if where_conditions:
                count_query += " AND " + " AND ".join(where_conditions)

            cursor = conn.cursor()
            count_params = list(params)
            try:
                if count_params:
                    cursor.execute(count_query, count_params)
                else:
                    cursor.execute(count_query)
            except Exception:
                logger.exception(
                    "Count query failed for search",
                    extra={
                        "sql": count_query,
                        "param_length": len(count_params),
                        "params_snapshot": list(count_params)[:10]
                    }
                )
                raise
            total_count = cursor.fetchone()['total']

            # Add sorting and pagination
            query = base_query + """
                ORDER BY
                    CASE WHEN c.title ILIKE %s THEN 1 ELSE 2 END,
                    c.indexed_at DESC
            """

            size = int(size or 20)
            offset = (page - 1) * size
            query += f"""
                LIMIT {size} OFFSET {offset}
            """

            try:
                combined_params = params + [search_term]
                if combined_params:
                    cursor.execute(query, combined_params)
                else:
                    cursor.execute(query)
            except Exception:
                logger.error(
                    "Main query failed for search: params=%s count=%s placeholders=%s sql=%s",
                    combined_params,
                    len(combined_params),
                    query.count('%s'),
                    query,
                    exc_info=True
                )
                raise
            rows = cursor.fetchall()

            reports = [self._format_report_for_api(dict(row)) for row in rows]
            return reports, total_count

        finally:
            conn.close()

    def _get_user_friendly_summary_type(self, variant: str) -> str:
        """Map database variants to user-friendly Telegram interface names."""
        mapping = {
            'bullet-points': 'Key Points',
            'audio': 'Audio Summary',
            'audio-fr': 'Audio français',
            'audio-es': 'Audio español',
            'comprehensive': 'Comprehensive',
            'key-points': 'Key Points',  # Handle both variants
            'executive': 'Executive Summary',
            'key-insights': 'Insights',
            'insights': 'Insights',
            'unknown': 'Unknown'
        }
        return mapping.get(variant, variant.title())  # Fallback to title case

    def _get_database_variant(self, user_friendly_name: str) -> str:
        """Map user-friendly names back to database variants for filtering."""
        reverse_mapping = {
            'Key Points': 'bullet-points',
            'Audio Summary': 'audio',
            'Audio français': 'audio-fr',
            'Audio español': 'audio-es',
            'Comprehensive': 'comprehensive',
            'Executive Summary': 'executive',
            'Insights': 'key-insights',
            'Unknown': 'unknown'
        }
        return reverse_mapping.get(user_friendly_name, user_friendly_name.lower())

    def get_filters(self, active_filters: Optional[Dict[str, Any]] = None) -> Dict[str, List[Dict[str, Any]]]:
        """Build filter payload matching legacy SQLite structure."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            source_case = self._source_case_expression('c', conn)

            # Aggregate sources using normalized slug expression
            try:
                cursor.execute(
                    f"""
                    SELECT {source_case} AS slug, COUNT(*) AS count
                    FROM content c
                    GROUP BY slug
                    ORDER BY COUNT(*) DESC
                    """
                )
                source_rows = cursor.fetchall()
            except Exception:
                logger.exception("Failed to compute source facet counts")
                source_rows = []

            source_items = []
            total_count = 0
            for row in source_rows:
                slug = (row.get('slug') or 'other').strip().lower() or 'other'
                count = int(row.get('count') or 0)
                total_count += count
                source_items.append({
                    'value': slug,
                    'label': self.SOURCE_LABELS.get(slug, slug.title()),
                    'count': count
                })

            # Optimized SQL query for summary_type facet counts
            cursor.execute("""
                SELECT COALESCE(ls.variant, 'unknown') AS t, COUNT(*) AS c
                FROM content c
                LEFT JOIN v_latest_summaries ls ON c.video_id = ls.video_id
                GROUP BY 1
                ORDER BY COUNT(*) DESC
            """)
            summary_type_rows = cursor.fetchall()

            cursor.execute("""
                SELECT channel_name,
                       COALESCE(has_audio, FALSE) AS has_audio,
                       analysis_json,
                       subcategories_json,
                       canonical_url,
                       video_id
                FROM content
            """)
            rows = cursor.fetchall()

            language_counter: Counter[str] = Counter()
            content_type_counter: Counter[str] = Counter()
            complexity_counter: Counter[str] = Counter()
            channel_counter: Counter[str] = Counter()
            has_audio_counter: Counter[bool] = Counter()
            category_hierarchy: Dict[str, Dict[str, Any]] = {}
            source_counter: Counter[str] = Counter()

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

                inferred_source = self._infer_content_source(
                    None,
                    row.get('canonical_url'),
                    row.get('video_id'),
                    None
                )
                source_counter[inferred_source] += 1

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
            if source_items:
                filters['source'] = [
                    {
                        'value': item['value'],
                        'label': item.get('label') or self.SOURCE_LABELS.get(item['value'], item['value'].title()),
                        'count': item['count']
                    }
                    for item in source_items
                ]
            else:
                # Fallback to counts derived from in-memory iteration
                filters['source'] = [
                    {
                        'value': slug,
                        'label': self.SOURCE_LABELS.get(slug, slug.title()),
                        'count': count
                    }
                    for slug, count in sorted(source_counter.items(), key=lambda x: (-x[1], x[0]))
                ] or [{
                    'value': 'youtube',
                    'label': self.SOURCE_LABELS.get('youtube', 'YouTube'),
                    'count': sum(source_counter.values())
                }]
            filters['content_source'] = filters['source']

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

            filters['summary_type'] = [
                {'value': self._get_user_friendly_summary_type(r['t']), 'count': int(r['c'])}
                for r in summary_type_rows
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

    def get_latest_report_metadata(self) -> Optional[Dict[str, Any]]:
        """Return minimal metadata for the most recently indexed report."""
        conn = None
        try:
            conn = self._get_connection()
            cur = conn.cursor()
            cur.execute(
                """
                SELECT video_id, summary_type_latest, indexed_at
                FROM content
                WHERE indexed_at IS NOT NULL
                ORDER BY indexed_at DESC
                LIMIT 1
                """
            )
            row = cur.fetchone()
            if not row:
                return None

            if isinstance(row, dict):
                data = row
            else:
                data = {
                    "video_id": row[0],
                    "summary_type_latest": row[1],
                    "indexed_at": row[2],
                }

            return {
                "video_id": data.get("video_id"),
                "summary_type": data.get("summary_type_latest"),
                "indexed_at": self._normalize_datetime(data.get("indexed_at")),
            }
        except Exception:
            logger.exception("Failed to fetch latest report metadata")
            return None
        finally:
            if conn:
                conn.close()

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

    def update_summary_image_prompt(self, video_id: str, prompt: str) -> None:
        """Set analysis_json.summary_image_prompt for a content row.

        NAS will read this field to override its image-generation prompt.
        """
        conn = None
        try:
            conn = self._get_connection()
            cur = conn.cursor()
            update_sql = """
            UPDATE content
            SET analysis_json = jsonb_set(
                COALESCE(analysis_json, '{}'::jsonb),
                '{summary_image_prompt}',
                to_jsonb(%s::text),
                true
            ),
            updated_at = NOW()
            WHERE video_id = %s
            """
            cur.execute(update_sql, [prompt or '', video_id])
            conn.commit()
        except Exception as e:
            logger.error(f"Error updating summary_image_prompt for %s: %s", video_id, e)
        finally:
            if conn:
                conn.close()

    def update_selected_image_url(self, video_id: str, url: str) -> None:
        """Set the selected image URL for a content row and mirror to summary_image_url."""
        conn = None
        try:
            conn = self._get_connection()
            cur = conn.cursor()
            update_sql = """
            UPDATE content
            SET analysis_json = jsonb_set(
                    COALESCE(analysis_json, '{}'::jsonb),
                    '{summary_image_selected_url}',
                    to_jsonb(%s::text),
                    true
                ),
                summary_image_url = %s,
                updated_at = NOW()
            WHERE video_id = %s
            """
            cur.execute(update_sql, [url or '', url or '', video_id])
            conn.commit()
        except Exception as e:
            logger.error("Error updating selected image for %s: %s", video_id, e)
        finally:
            if conn:
                conn.close()

    def delete_content(self, video_id: str) -> dict:
        """Delete a video and its summaries by YouTube video_id."""
        conn = None
        try:
            conn = self._get_connection()
            cur = conn.cursor()
            # Delete summaries first (FK or not, it's safe)
            cur.execute("""
                DELETE FROM content_summaries
                WHERE video_id = %s
            """, (video_id,))
            summaries_deleted = cur.rowcount

            # Delete the content row
            cur.execute("""
                DELETE FROM content
                WHERE video_id = %s
            """, (video_id,))
            content_deleted = cur.rowcount

            conn.commit()
            return {
                "success": True,
                "content_deleted": int(content_deleted),
                "summaries_deleted": int(summaries_deleted),
            }
        except Exception as e:
            if conn: conn.rollback()
            logger.error(f"PostgreSQL deletion error for {video_id}: {e}")
            return {"success": False, "error": str(e), "content_deleted": 0, "summaries_deleted": 0}
        finally:
            if conn: conn.close()
