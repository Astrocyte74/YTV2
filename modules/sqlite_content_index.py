#!/usr/bin/env python3
"""
SQLite Content Index
High-performance content management using SQLite database.
Replaces the JSON-based content_index.py with proper database queries.
"""

import sqlite3
import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timezone
import os

logger = logging.getLogger(__name__)

class SQLiteContentIndex:
    """SQLite-based content management for YTV2 Dashboard."""
    
    def __init__(self, db_path: str = "ytv2_content.db"):
        """Initialize with database path."""
        self.db_path = Path(db_path)
        self._ensure_database_exists()
        
    def _ensure_database_exists(self):
        """Ensure the database file exists and run migrations."""
        if not self.db_path.exists():
            raise FileNotFoundError(f"SQLite database not found: {self.db_path}")
        
        # Run database migration for subcategory column
        self._run_migrations()
        
        logger.info(f"Using SQLite database: {self.db_path}")
    
    def _run_migrations(self):
        """Run database migrations to ensure schema is up to date."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            
            # Migration: Add subcategory column if it doesn't exist
            try:
                cursor.execute('ALTER TABLE content ADD COLUMN subcategory TEXT')
                logger.info("✅ Migration: Added subcategory column to content table")
                conn.commit()
            except sqlite3.OperationalError as e:
                if "duplicate column name" in str(e).lower():
                    logger.debug("ℹ️ Migration: Subcategory column already exists")
                else:
                    logger.warning(f"Migration warning: Could not add subcategory column: {e}")
            
            # Migration: Add subcategories_json column if it doesn't exist
            try:
                cursor.execute('ALTER TABLE content ADD COLUMN subcategories_json TEXT')
                logger.info("✅ Migration: Added subcategories_json column to content table")
                conn.commit()
            except sqlite3.OperationalError as e:
                if "duplicate column name" in str(e).lower():
                    logger.debug("ℹ️ Migration: Subcategories_json column already exists")
                else:
                    logger.warning(f"Migration warning: Could not add subcategories_json column: {e}")
            
            # Migration: Add analysis column if it doesn't exist (for structured data)
            try:
                cursor.execute('ALTER TABLE content ADD COLUMN analysis TEXT')
                logger.info("✅ Migration: Added analysis column to content table")
                conn.commit()
            except sqlite3.OperationalError as e:
                if "duplicate column name" in str(e).lower():
                    logger.debug("ℹ️ Migration: Analysis column already exists")
                else:
                    logger.warning(f"Migration warning: Could not add analysis column: {e}")
                    
        finally:
            conn.close()
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection with proper configuration."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Enable dict-like access
        return conn
    
    def _parse_json_field(self, value: str) -> List[str]:
        """Parse JSON field safely."""
        if not value:
            return []
        try:
            result = json.loads(value)
            return result if isinstance(result, list) else []
        except:
            return []
    
    def _parse_subcategories_json(self, value: str) -> List[Dict[str, Any]]:
        """Parse subcategories_json field safely."""
        if not value:
            return []
        try:
            result = json.loads(value)
            if isinstance(result, dict) and 'categories' in result:
                return result['categories']
            return []
        except:
            return []
    
    def _format_report_for_api(self, row: sqlite3.Row) -> Dict[str, Any]:
        """Convert database row to API format."""
        return {
            'id': row['id'],
            'title': row['title'] or 'Untitled',
            'thumbnail_url': row['thumbnail_url'] or '',
            'canonical_url': row['canonical_url'] or '',
            'channel': row['channel_name'] or '',
            'published_at': row['published_at'] or '',
            'duration_seconds': row['duration_seconds'] or 0,
            'analysis': {
                'category': self._parse_json_field(row['category']),
                'subcategory': row['subcategory'] if 'subcategory' in row.keys() else None,
                'categories': self._parse_subcategories_json(row['subcategories_json'] if 'subcategories_json' in row.keys() else None),
                'content_type': row['content_type'] or '',
                'complexity_level': row['complexity_level'] or '',
                'language': row['language'] or 'en',
                'key_topics': self._parse_json_field(row['key_topics']),
                'named_entities': self._parse_json_field(row['named_entities'])
            },
            'media': {
                'has_audio': bool(row['has_audio']),
                'audio_duration_seconds': row['audio_duration_seconds'] or 0,
                'has_transcript': bool(row['has_transcript']),
                'transcript_chars': row['transcript_chars'] or 0
            },
            'media_metadata': {
                'video_duration_seconds': row['duration_seconds'] or 0,
                'mp3_duration_seconds': row['audio_duration_seconds'] or 0
            },
            'file_stem': self._generate_file_stem(row['video_id'], row['title']),
            'video_id': row['video_id'] or '',
            # Add new structured subcategories field
            'subcategories_json': row['subcategories_json'] if 'subcategories_json' in row.keys() else None,
            'indexed_at': row['indexed_at'] or '',
            'original_language': row['language'] or 'en',
            'summary_language': row['language'] or 'en', 
            'audio_language': row['language'] or 'en',
            'word_count': row['word_count'] or 0
        }
    
    def _generate_file_stem(self, video_id: str, title: str) -> str:
        """Generate file stem for compatibility."""
        if video_id:
            return f"{video_id}"
        # Fallback to title-based stem
        safe_title = ''.join(c for c in title.lower() if c.isalnum() or c in '-_')[:50]
        return safe_title or 'unknown'
    
    def get_reports(self, 
                   page: int = 1, 
                   size: int = 12, 
                   sort: str = 'added_desc',
                   filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Get paginated and filtered reports."""
        
        conn = self._get_connection()
        try:
            # Build base query
            query = "SELECT * FROM content"
            params = []
            where_conditions = []
            
            # Apply filters
            if filters:
                if 'source' in filters and filters['source']:
                    # For now, assume all content is YouTube
                    pass
                
                if 'language' in filters and filters['language']:
                    lang_conditions = []
                    for lang in filters['language']:
                        lang_conditions.append("language = ?")
                        params.append(lang)
                    if lang_conditions:
                        where_conditions.append(f"({' OR '.join(lang_conditions)})")
                
                if 'category' in filters and filters['category']:
                    cat_conditions = []
                    for cat in filters['category']:
                        # Normalize punctuation (en-dash to hyphen)
                        cat_normalized = cat.replace('–', '-').strip()
                        
                        # Check if this is a subcategory filter (includes parent context)
                        parent_categories = filters.get('parentCategory', [])
                        if isinstance(parent_categories, str):
                            parent_categories = [parent_categories]
                        
                        if parent_categories:
                            # EXACT subcategory match within specific parent categories using JSON1
                            pair_conditions = []
                            for parent_category in parent_categories:
                                parent_normalized = parent_category.replace('–', '-').strip()
                                # Safe JSON1 query with error handling for malformed JSON
                                pair_conditions.append("""(
                                    (content.subcategories_json IS NOT NULL AND json_valid(content.subcategories_json) AND
                                     EXISTS (
                                        SELECT 1 FROM json_each(content.subcategories_json, '$.categories') AS c
                                        LEFT JOIN json_each(c.value, '$.subcategories') AS s
                                        WHERE json_extract(c.value,'$.category') = ? AND s.value = ?
                                    )) OR (
                                        content.subcategory = ? AND
                                        (content.category IS NOT NULL AND json_valid(content.category) AND
                                         EXISTS (SELECT 1 FROM json_each(content.category) AS cat WHERE cat.value = ?))
                                    )
                                )""")
                                params.extend([parent_normalized, cat_normalized, cat_normalized, parent_normalized])
                            cat_conditions.append(f"({' OR '.join(pair_conditions)})")
                        else:
                            # Category-level filter (show all content in this category)
                            cat_conditions.append("""(
                                (content.category IS NOT NULL AND json_valid(content.category) AND
                                 EXISTS (SELECT 1 FROM json_each(content.category) AS cat WHERE cat.value = ?)) OR
                                (content.subcategories_json IS NOT NULL AND json_valid(content.subcategories_json) AND
                                 EXISTS (
                                    SELECT 1 FROM json_each(content.subcategories_json, '$.categories') AS c
                                    WHERE json_extract(c.value,'$.category') = ?
                                ))
                            )""")
                            params.extend([cat_normalized, cat_normalized])
                    
                    if cat_conditions:
                        where_conditions.append(f"({' OR '.join(cat_conditions)})")
                
                # FIXED: OR logic for subcategories (per OpenAI recommendation)
                # Build a single OR group for all selected subcategories (union, not intersection)
                if 'subcategory' in filters and filters['subcategory']:
                    # Normalize inputs
                    subcats = filters['subcategory']
                    if isinstance(subcats, str):
                        subcats = [subcats]
                    subcats = [s.replace('–', '-').strip() for s in subcats if s and str(s).strip()]
                    subcats = sorted(set(subcats))  # Deduplicate to avoid duplicate OR terms
                    
                    parents = filters.get('parentCategory', [])
                    if isinstance(parents, str):
                        parents = [parents]
                    parents = [p.replace('–', '-').strip() for p in parents if p and str(p).strip()]
                    parents = sorted(set(parents))  # Deduplicate parent categories
                    
                    # Guard against empty inputs after normalization
                    if not subcats:
                        logger.debug("No valid subcategories after normalization, skipping subcategory filter")
                    else:
                        # Build a single OR group for all selected subcategories (union)
                        or_clauses = []
                    or_params = []
                    
                    if parents:  # pair each selected subcat with each selected parent
                        for p in parents:
                            for sc in subcats:
                                or_clauses.append("""
                                    (
                                        content.subcategories_json IS NOT NULL AND json_valid(content.subcategories_json) AND
                                        EXISTS (
                                            SELECT 1 FROM json_each(content.subcategories_json, '$.categories') c
                                            JOIN json_each(c.value, '$.subcategories') s ON 1=1
                                            WHERE json_extract(c.value,'$.category') = ? AND s.value = ?
                                        )
                                    )
                                    OR (
                                        content.subcategory = ? AND
                                        content.category IS NOT NULL AND json_valid(content.category) AND
                                        EXISTS (SELECT 1 FROM json_each(content.category) cat WHERE cat.value = ?)
                                    )
                                """)
                                or_params.extend([p, sc, sc, p])
                    else:  # no explicit parent: match any parent that contains the subcat
                        for sc in subcats:
                            or_clauses.append("""
                                (
                                    content.subcategories_json IS NOT NULL AND json_valid(content.subcategories_json) AND
                                    EXISTS (
                                        SELECT 1 FROM json_each(content.subcategories_json, '$.categories') c
                                        JOIN json_each(c.value, '$.subcategories') s ON 1=1
                                        WHERE s.value = ?
                                    )
                                )
                                OR (
                                    content.subcategory = ?
                                )
                            """)
                            or_params.extend([sc, sc])
                    
                        if or_clauses:
                            # Single OR condition for all subcategories (creates union, not intersection)
                            # Note: At scale, could optimize large OR lists with IN (...) temp table if needed
                            where_conditions.append(f"({' OR '.join(or_clauses)})")
                            params.extend(or_params)
                        elif subcats:
                            # Edge case: valid subcats but no OR clauses generated (shouldn't happen)
                            logger.warning(f"Subcategory filter had valid inputs but no OR clauses: {subcats}")
                
                # Apply content type filter
                if 'content_type' in filters and filters['content_type']:
                    type_conditions = []
                    for ctype in filters['content_type']:
                        type_conditions.append("content_type = ?")
                        params.append(ctype)
                    if type_conditions:
                        where_conditions.append(f"({' OR '.join(type_conditions)})")
                
                if 'complexity' in filters and filters['complexity']:
                    comp_conditions = []
                    for comp in filters['complexity']:
                        comp_conditions.append("complexity_level = ?")
                        params.append(comp)
                    if comp_conditions:
                        where_conditions.append(f"({' OR '.join(comp_conditions)})")
                
                if 'channel' in filters and filters['channel']:
                    channel_conditions = []
                    for channel in filters['channel']:
                        channel_conditions.append("channel_name = ?")
                        params.append(channel)
                    if channel_conditions:
                        where_conditions.append(f"({' OR '.join(channel_conditions)})")
                
                if 'has_audio' in filters:
                    where_conditions.append("has_audio = ?")
                    params.append(filters['has_audio'])
            
            # Add WHERE clause if we have conditions
            if where_conditions:
                query += " WHERE " + " AND ".join(where_conditions)
            
            # Add sorting
            sort_mapping = {
                'added_desc': 'indexed_at DESC',
                'added_asc': 'indexed_at ASC',
                'video_newest': 'published_at DESC',
                'video_oldest': 'published_at ASC',
                'title_az': 'title ASC',
                'title_za': 'title DESC',
                'duration_desc': 'duration_seconds DESC',
                'duration_asc': 'duration_seconds ASC',
                # Legacy compatibility
                'newest': 'published_at DESC',
                'oldest': 'published_at ASC',
                'title': 'title ASC',
                'title_asc': 'title ASC',
                'title_desc': 'title DESC',
                'duration': 'duration_seconds DESC'
            }
            
            order_by = sort_mapping.get(sort, 'indexed_at DESC')
            query += f" ORDER BY {order_by}"
            
            # Get total count for pagination
            count_query = query.replace("SELECT *", "SELECT COUNT(*)")
            if " ORDER BY " in count_query:
                count_query = count_query.split(" ORDER BY ")[0]
            
            cursor = conn.execute(count_query, params)
            total_count = cursor.fetchone()[0]
            
            # Add pagination
            offset = (page - 1) * size
            query += " LIMIT ? OFFSET ?"
            params.extend([size, offset])
            
            # Execute main query with error handling (per OpenAI recommendation)
            try:
                cursor = conn.execute(query, params)
                rows = cursor.fetchall()
            except Exception as e:
                logger.exception("Query failed. SQL=%s PARAMS=%s", query, params)
                raise
            
            # Convert to API format
            reports = [self._format_report_for_api(row) for row in rows]
            
            # Calculate pagination info
            total_pages = (total_count + size - 1) // size
            
            return {
                'reports': reports,
                'pagination': {
                    'page': page,
                    'size': size,
                    'total_count': total_count,
                    'total_pages': total_pages,
                    'has_next': page < total_pages,
                    'has_prev': page > 1
                },
                'sort': sort,
                'filters': filters or {}
            }
            
        finally:
            conn.close()
    
    def get_filters(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get available filter options with counts."""
        conn = self._get_connection()
        try:
            filters = {}
            
            # Source filter (always YouTube for now)
            filters['source'] = [{'value': 'youtube', 'count': self.get_report_count()}]
            
            # Language filter
            cursor = conn.execute("""
                SELECT language, COUNT(*) as count 
                FROM content 
                WHERE language IS NOT NULL AND language != ''
                GROUP BY language 
                ORDER BY count DESC
            """)
            filters['language'] = [
                {'value': row['language'], 'count': row['count']} 
                for row in cursor.fetchall()
            ]
            
            # Category filter with subcategory support - use structured data when available
            cursor = conn.execute("""
                SELECT category, subcategory, subcategories_json, COUNT(*) as count
                FROM content 
                WHERE category IS NOT NULL AND category != '' AND category != '[]'
                GROUP BY category, subcategory, subcategories_json
                ORDER BY count DESC
            """)
            
            # Build hierarchical category structure
            category_hierarchy = {}
            for row in cursor.fetchall():
                categories = self._parse_json_field(row['category'])
                legacy_subcategory = row['subcategory'] if 'subcategory' in row.keys() else None
                subcategories_json = row['subcategories_json'] if 'subcategories_json' in row.keys() else None
                count = row['count']
                
                # Parse structured subcategories if available
                structured_categories = self._parse_subcategories_json(subcategories_json) if subcategories_json else []
                
                # Use structured data if available, otherwise fall back to legacy
                if structured_categories:
                    # Use structured format: [{"category": "X", "subcategories": ["Y", "Z"]}]
                    for cat_obj in structured_categories:
                        cat_name = cat_obj.get('category', '')
                        if not cat_name:
                            continue
                            
                        if cat_name not in category_hierarchy:
                            category_hierarchy[cat_name] = {
                                'count': 0,
                                'subcategories': {}
                            }
                        
                        category_hierarchy[cat_name]['count'] += count
                        
                        # Add all subcategories for this category
                        for subcat in cat_obj.get('subcategories', []):
                            if subcat not in category_hierarchy[cat_name]['subcategories']:
                                category_hierarchy[cat_name]['subcategories'][subcat] = 0
                            category_hierarchy[cat_name]['subcategories'][subcat] += count
                else:
                    # Fall back to legacy format for backwards compatibility
                    for cat in categories:
                        if cat not in category_hierarchy:
                            category_hierarchy[cat] = {
                                'count': 0,
                                'subcategories': {}
                            }
                        
                        category_hierarchy[cat]['count'] += count
                        
                        if legacy_subcategory:
                            if legacy_subcategory not in category_hierarchy[cat]['subcategories']:
                                category_hierarchy[cat]['subcategories'][legacy_subcategory] = 0
                            category_hierarchy[cat]['subcategories'][legacy_subcategory] += count
            
            # Convert to API format
            filters['category'] = []
            for cat, data in sorted(category_hierarchy.items(), key=lambda x: x[1]['count'], reverse=True):
                category_item = {
                    'value': cat,
                    'count': data['count']
                }
                
                # Add subcategories if they exist
                if data['subcategories']:
                    category_item['subcategories'] = [
                        {'value': subcat, 'count': subcount}
                        for subcat, subcount in sorted(data['subcategories'].items(), key=lambda x: x[1], reverse=True)
                    ]
                
                filters['category'].append(category_item)
            
            # Content type filter
            cursor = conn.execute("""
                SELECT content_type, COUNT(*) as count
                FROM content 
                WHERE content_type IS NOT NULL AND content_type != ''
                GROUP BY content_type 
                ORDER BY count DESC
            """)
            filters['content_type'] = [
                {'value': row['content_type'], 'count': row['count']}
                for row in cursor.fetchall()
            ]
            
            # Complexity filter
            cursor = conn.execute("""
                SELECT complexity_level, COUNT(*) as count
                FROM content 
                WHERE complexity_level IS NOT NULL AND complexity_level != ''
                GROUP BY complexity_level 
                ORDER BY count DESC
            """)
            filters['complexity_level'] = [
                {'value': row['complexity_level'], 'count': row['count']}
                for row in cursor.fetchall()
            ]
            
            # Channel filter
            cursor = conn.execute("""
                SELECT channel_name, COUNT(*) as count
                FROM content 
                WHERE channel_name IS NOT NULL AND channel_name != ''
                GROUP BY channel_name 
                ORDER BY count DESC
            """)
            filters['channel'] = [
                {'value': row['channel_name'], 'count': row['count']}
                for row in cursor.fetchall()
            ]
            
            # Has audio filter
            cursor = conn.execute("""
                SELECT has_audio, COUNT(*) as count
                FROM content 
                GROUP BY has_audio
            """)
            filters['has_audio'] = [
                {'value': bool(row['has_audio']), 'count': row['count']}
                for row in cursor.fetchall()
            ]
            
            return filters
            
        finally:
            conn.close()
    
    def get_report_count(self) -> int:
        """Get total number of reports."""
        conn = self._get_connection()
        try:
            cursor = conn.execute("SELECT COUNT(*) FROM content")
            return cursor.fetchone()[0]
        finally:
            conn.close()
    
    def get_report_by_id(self, report_id: str) -> Optional[Dict[str, Any]]:
        """Get individual report with full summary data by ID or video_id."""
        conn = self._get_connection()
        try:
            # Query content and summary data with JOIN, search by both id and video_id
            cursor = conn.execute("""
                SELECT c.*, s.summary_text, s.summary_type
                FROM content c
                LEFT JOIN content_summaries s ON c.id = s.content_id
                WHERE c.id = ? OR c.video_id = ?
            """, (report_id, report_id))
            
            row = cursor.fetchone()
            if not row:
                return None
            
            # Convert to full report format
            report = self._format_report_for_api(row)
            
            # Add summary data - support both API format and template format
            if row['summary_text']:
                report['summary'] = {
                    'text': row['summary_text'],
                    'type': row['summary_type'] or 'audio',
                    # Also add nested format for template compatibility
                    'content': {
                        'summary': row['summary_text'],
                        'summary_type': row['summary_type'] or 'audio'
                    }
                }
            else:
                report['summary'] = {
                    'text': 'No summary available.',
                    'type': 'none',
                    'content': {
                        'summary': 'No summary available.',
                        'summary_type': 'none'
                    }
                }
            
            # Add processing metadata for compatibility
            report['processor_info'] = {
                'model': 'sqlite_backend',
                'processing_time': 0,
                'timestamp': report.get('indexed_at', '')
            }
            
            return report
            
        finally:
            conn.close()
    
    def search_reports(self, 
                      filters: Optional[Dict[str, Any]] = None,
                      query: Optional[str] = None,
                      sort: str = 'added_desc',
                      page: int = 1,
                      size: int = 20) -> Dict[str, Any]:
        """Search and filter reports with pagination - matches original API signature."""
        
        # For search queries, use get_reports with filters instead
        if query and len(query.strip()) >= 2:
            # Simple search implementation - could be enhanced later
            conn = self._get_connection()
            try:
                search_term = f"%{query.strip()}%"
                
                # Search in titles and summaries
                cursor = conn.execute("""
                    SELECT c.* FROM content c
                    LEFT JOIN content_summaries s ON c.id = s.content_id
                    WHERE c.title LIKE ? OR s.summary_text LIKE ?
                    ORDER BY 
                        CASE WHEN c.title LIKE ? THEN 1 ELSE 2 END,
                        c.indexed_at DESC
                    LIMIT ?
                """, (search_term, search_term, search_term, min(size, 50)))
                
                rows = cursor.fetchall()
                reports = [self._format_report_for_api(row) for row in rows]
                
                return {
                    'reports': reports,
                    'pagination': {
                        'page': page,
                        'size': size,
                        'total_count': len(reports),
                        'total_pages': 1,
                        'has_next': False,
                        'has_prev': False
                    },
                    'sort': sort,
                    'filters': filters or {}
                }
                
            finally:
                conn.close()
        else:
            # No query, use standard get_reports
            return self.get_reports(page=page, size=size, sort=sort, filters=filters)
    
    def needs_refresh(self) -> bool:
        """SQLite doesn't need refresh like file-based system."""
        return False
    
    def refresh_index(self):
        """No-op for SQLite - data is always current."""
        pass
    
    def force_refresh(self) -> int:
        """Force refresh and return count - for compatibility with JSON version."""
        return self.get_report_count()
    
    def get_facets(self, active_filters: Optional[Dict[str, Any]] = None) -> Dict[str, List[Dict[str, Any]]]:
        """Get facets/filters - alias for get_filters() for compatibility."""
        return self.get_filters()
    
