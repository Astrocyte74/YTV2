"""
Content Index Module for YTV2 Dashboard

In-memory indexing system for fast filtering, faceted search, and pagination.
Provides the foundation for Phase 2 API infrastructure with universal schema support.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set, Any, Tuple
from collections import defaultdict, Counter
import re

logger = logging.getLogger(__name__)


class ContentIndex:
    """
    High-performance in-memory content index for YTV2 Dashboard.
    
    Features:
    - Fast faceted search with counts
    - Universal schema support
    - Text search across titles and content
    - Sorting by multiple criteria
    - Pagination support
    - Automatic cache invalidation
    """
    
    def __init__(self, reports_dir: str = "data/reports"):
        """Initialize content index with reports directory"""
        self.reports_dir = Path(reports_dir)
        self.reports = {}  # id -> report data
        self.facets = {}   # facet_name -> {value: count}
        self.search_index = {}  # for text search
        self.last_refresh = None
        self._file_mtimes = {}  # track file modification times
        self._refresh_threshold = 5   # minimum seconds between refresh checks (reduced for faster updates)
        self._last_check_time = 0  # last time we checked for file changes
        
        # Initialize facet structure
        self.facets = {
            'content_source': defaultdict(int),
            'language': defaultdict(int), 
            'category': defaultdict(int),
            'content_type': defaultdict(int),
            'complexity_level': defaultdict(int),
            'key_topics': defaultdict(int),
            'has_audio': defaultdict(int),
            'year': defaultdict(int)
        }
        
        # Load initial data
        self.refresh_index()
    
    def force_refresh(self) -> int:
        """Force immediate index refresh regardless of throttling"""
        self._last_check_time = 0  # Reset throttle
        return self.refresh_index()
    
    def needs_refresh(self) -> bool:
        """Check if index needs to be refreshed based on file changes with throttling"""
        import time
        
        if not self.last_refresh:
            return True
            
        # Throttle refresh checks to avoid file system spam
        current_time = time.time()
        if current_time - self._last_check_time < self._refresh_threshold:
            return False
            
        if not self.reports_dir.exists():
            return False
            
        try:
            # Only check directory modification time first (faster than scanning all files)
            dir_mtime = self.reports_dir.stat().st_mtime
            if hasattr(self, '_last_dir_mtime') and dir_mtime <= self._last_dir_mtime:
                self._last_check_time = current_time
                return False
            
            # If directory changed, do detailed file scan
            changed = False
            current_files = {}
            
            for json_file in self.reports_dir.glob('*.json'):
                if json_file.name.startswith('.'):
                    continue
                    
                try:
                    current_mtime = json_file.stat().st_mtime
                    current_files[str(json_file)] = current_mtime
                    
                    last_known_mtime = self._file_mtimes.get(str(json_file), 0)
                    if current_mtime > last_known_mtime:
                        changed = True
                        break  # Early exit on first change
                        
                except (OSError, IOError):
                    # File might have been deleted or is inaccessible
                    continue
            
            # Check for new/deleted files only if no modifications found
            if not changed:
                known_files = set(self._file_mtimes.keys())
                current_file_set = set(current_files.keys())
                changed = current_file_set != known_files
            
            # Update tracking
            self._last_check_time = current_time
            self._last_dir_mtime = dir_mtime
            
            return changed
            
        except Exception as e:
            logger.warning(f"Error checking file changes: {e}")
            self._last_check_time = current_time
            return True
    
    def refresh_index(self) -> int:
        """Rebuild the entire index from files"""
        logger.info("Refreshing content index...")
        start_time = datetime.now()
        
        # Clear current data
        self.reports.clear()
        for facet in self.facets:
            self.facets[facet].clear()
        self.search_index.clear()
        self._file_mtimes.clear()
        
        processed_count = 0
        
        if not self.reports_dir.exists():
            logger.warning(f"Reports directory not found: {self.reports_dir}")
            return 0
        
        # Process all JSON files
        for json_file in self.reports_dir.glob('*.json'):
            if json_file.name.startswith('.'):
                continue
                
            try:
                # Track file modification time
                self._file_mtimes[str(json_file)] = json_file.stat().st_mtime
                
                with open(json_file, 'r', encoding='utf-8') as f:
                    report_data = json.load(f)
                
                # Process and index the report
                self._index_report(report_data, json_file.stem)
                processed_count += 1
                
            except Exception as e:
                logger.error(f"Error processing {json_file}: {e}")
                continue
        
        self.last_refresh = datetime.now()
        elapsed = (datetime.now() - start_time).total_seconds()
        
        logger.info(f"Index refreshed: {processed_count} reports in {elapsed:.2f}s")
        return processed_count
    
    def _index_report(self, report_data: Dict[str, Any], file_stem: str) -> None:
        """Index a single report into the search structures"""
        
        # Detect legacy vs universal schema format
        is_legacy = not ('metadata' in report_data and 'schema_version' in report_data.get('metadata', {}))
        
        if is_legacy:
            # Legacy format - extract from old structure
            video_info = report_data.get('video', {})
            summary_info = report_data.get('summary', {})
            
            report_id = f"legacy:{file_stem}"
            title = video_info.get('title', file_stem.replace('_', ' '))
            content_source = 'youtube'
            duration_seconds = video_info.get('duration', 0)
            published_at = video_info.get('upload_date', '')
            channel = video_info.get('channel', '')
            
            # Legacy analysis - use defaults
            category = ['General']
            content_type = 'Discussion'  
            complexity_level = 'Intermediate'
            language = 'en'
            key_topics = []
            
        else:
            # Universal schema format
            report_id = report_data.get('id', f"legacy:{file_stem}")
            # Prefer explicit top-level title; fall back to video.title; then metadata; finally file stem
            title = str(report_data.get('title', '')).strip()
            if not title:
                video_block = report_data.get('video', {}) or {}
                title = str(video_block.get('title', '')).strip()
            if not title:
                metadata = report_data.get('metadata', {})
                title = str(metadata.get('title', '')).strip()
            if not title:
                title = file_stem.replace('_', ' ')
            
            content_source = report_data.get('content_source', 'youtube')
            published_at = report_data.get('published_at', '')
            duration_seconds = report_data.get('duration_seconds', 0)
            if not duration_seconds:
                # Fallback to original video duration if provided
                try:
                    duration_seconds = int((report_data.get('video') or {}).get('duration') or 0)
                except Exception:
                    duration_seconds = 0
            channel = (report_data.get('video') or {}).get('channel', '')
            # Fallbacks for published date
            if not published_at:
                vid = report_data.get('video') or {}
                upload_date = vid.get('upload_date', '')
                if upload_date and len(upload_date) == 8:
                    # Convert YYYYMMDD to ISO
                    published_at = f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:8]}T00:00:00"
            if not published_at:
                gen = (report_data.get('metadata') or {}).get('generated_at', '')
                if gen:
                    published_at = gen
        
            # Universal schema - extract analysis data
            analysis = report_data.get('analysis', {})
            category = analysis.get('category', ['General'])
            if isinstance(category, str):
                category = [category]
            
            content_type = analysis.get('content_type', 'Discussion')
            complexity_level = analysis.get('complexity_level', 'Intermediate')
            language = analysis.get('language', 'en')
            key_topics = analysis.get('key_topics', [])
            if isinstance(key_topics, str):
                key_topics = [key_topics]
        
        # Media information
        media = report_data.get('media', {})
        has_audio = media.get('has_audio', True)  # YouTube default
        
        # Extract year from published date
        year = None
        if published_at:
            try:
                if published_at.endswith('Z'):
                    dt = datetime.fromisoformat(published_at[:-1])
                else:
                    dt = datetime.fromisoformat(published_at)
                year = str(dt.year)
            except (ValueError, AttributeError):
                pass
        
        if not year:
            year = str(datetime.now().year)  # fallback to current year
        
        # Create indexed report structure (without raw data to save memory)
        # Pull common video fields for thumbnails/urls/video_id
        video_block = report_data.get('video', {}) or {}
        thumbnail_url = report_data.get('thumbnail_url') or video_block.get('thumbnail', '')
        canonical_url = report_data.get('canonical_url') or video_block.get('url', '')
        video_id = video_block.get('video_id', '')

        indexed_report = {
            'id': report_id,
            'title': title[:300],  # Limit title length
            'content_source': content_source,
            'published_at': published_at,
            'duration_seconds': duration_seconds,
            'thumbnail_url': thumbnail_url,
            'canonical_url': canonical_url,
            'channel': channel,
            'analysis': {
                'language': language,
                'category': category[:3],  # Limit to 3 categories
                'content_type': content_type,
                'complexity_level': complexity_level,
                'key_topics': key_topics[:5]  # Limit to 5 topics
            },
            'media': {
                'has_audio': has_audio,
                'audio_duration_seconds': media.get('audio_duration_seconds', duration_seconds)
            },
            'year': year,
            'file_stem': file_stem,
            'video_id': video_id,
        }
        
        # Store in main index
        self.reports[report_id] = indexed_report
        
        # Update facet counts
        self.facets['content_source'][content_source] += 1
        self.facets['language'][language] += 1
        self.facets['content_type'][content_type] += 1
        self.facets['complexity_level'][complexity_level] += 1
        self.facets['has_audio'][has_audio] += 1
        self.facets['year'][year] += 1
        
        # Index categories
        for cat in category:
            self.facets['category'][cat] += 1
        
        # Index topics
        for topic in key_topics:
            if topic and isinstance(topic, str):
                self.facets['key_topics'][topic] += 1
        
        # Build search index (title + key topics)
        search_text = f"{title} {' '.join(key_topics)}".lower()
        self.search_index[report_id] = search_text
    
    def get_facets(self, active_filters: Optional[Dict[str, Any]] = None) -> Dict[str, List[Dict[str, Any]]]:
        """Get facet counts, optionally filtered by active filters"""
        
        if active_filters:
            # Calculate masked facet counts (respecting other active filters)
            filtered_reports = self._apply_filters(active_filters)
            return self._calculate_facets_from_reports(filtered_reports)
        else:
            # Return all facet counts
            result = {}
            for facet_name, counts in self.facets.items():
                result[facet_name] = [
                    {'value': value, 'count': count}
                    for value, count in sorted(counts.items(), key=lambda x: -x[1])
                ]
            return result
    
    def _calculate_facets_from_reports(self, reports: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """Calculate facet counts from a filtered set of reports"""
        facet_counts = {
            'content_source': defaultdict(int),
            'language': defaultdict(int),
            'category': defaultdict(int),
            'content_type': defaultdict(int),
            'complexity_level': defaultdict(int),
            'key_topics': defaultdict(int),
            'has_audio': defaultdict(int),
            'year': defaultdict(int)
        }
        
        for report in reports:
            facet_counts['content_source'][report['content_source']] += 1
            facet_counts['language'][report['analysis']['language']] += 1
            facet_counts['content_type'][report['analysis']['content_type']] += 1
            facet_counts['complexity_level'][report['analysis']['complexity_level']] += 1
            facet_counts['has_audio'][report['media']['has_audio']] += 1
            facet_counts['year'][report['year']] += 1
            
            for cat in report['analysis']['category']:
                facet_counts['category'][cat] += 1
                
            for topic in report['analysis']['key_topics']:
                if topic:
                    facet_counts['key_topics'][topic] += 1
        
        # Convert to API format
        result = {}
        for facet_name, counts in facet_counts.items():
            result[facet_name] = [
                {'value': value, 'count': count}
                for value, count in sorted(counts.items(), key=lambda x: -x[1])
                if count > 0
            ]
        
        return result
    
    def search_reports(self, 
                      filters: Optional[Dict[str, Any]] = None,
                      query: Optional[str] = None,
                      sort: str = 'newest',
                      page: int = 1,
                      size: int = 20) -> Dict[str, Any]:
        """Search and filter reports with pagination and input validation"""
        
        # Input validation
        query = self._validate_search_query(query)
        sort = self._validate_sort_param(sort)
        page = max(1, min(page, 1000))  # Limit page range
        size = max(1, min(size, 100))   # Limit page size
        
        # Auto-refresh if needed
        if self.needs_refresh():
            self.refresh_index()
        
        # Start with all reports
        filtered_reports = list(self.reports.values())
        
        # Apply filters with validation
        if filters:
            filters = self._validate_filters(filters)
            filtered_reports = self._apply_filters(filters, filtered_reports)
        
        # Apply text search
        if query:
            filtered_reports = self._apply_text_search(query, filtered_reports)
        
        # Apply sorting
        filtered_reports = self._apply_sorting(sort, filtered_reports)
        
        # Calculate pagination
        total_count = len(filtered_reports)
        total_pages = (total_count + size - 1) // size  # Ceiling division
        start_idx = (page - 1) * size
        end_idx = start_idx + size
        
        paginated_reports = filtered_reports[start_idx:end_idx]
        
        return {
            'data': [self._format_report_for_api(report) for report in paginated_reports],
            'pagination': {
                'page': page,
                'size': size,
                'total': total_count,
                'pages': total_pages
            }
        }
    
    def _validate_search_query(self, query: Optional[str]) -> Optional[str]:
        """Validate and sanitize search query"""
        if not query or not isinstance(query, str):
            return None
        
        # Strip and limit length
        query = query.strip()
        if len(query) > 200:  # Reasonable search term limit
            query = query[:200]
        
        # Remove potential XSS characters
        query = query.replace('<', '').replace('>', '').replace('&', '')
        
        return query.lower() if query else None
    
    def _validate_sort_param(self, sort: str) -> str:
        """Validate sort parameter"""
        valid_sorts = {'newest', 'title', 'duration'}
        return sort if sort in valid_sorts else 'newest'
    
    def _validate_filters(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and sanitize filter parameters"""
        if not isinstance(filters, dict):
            return {}
        
        validated = {}
        
        # Validate each filter type
        for key, value in filters.items():
            if key in ['source', 'language', 'category', 'content_type', 'complexity', 'topics']:
                if isinstance(value, list):
                    # Limit array size and sanitize strings
                    validated[key] = [str(v)[:50] for v in value[:10]]
            elif key == 'has_audio':
                if isinstance(value, bool):
                    validated[key] = value
            elif key in ['date_from', 'date_to']:
                if isinstance(value, str) and len(value) <= 25:  # ISO date length
                    validated[key] = value
        
        return validated
    
    def _apply_filters(self, filters: Dict[str, Any], reports: Optional[List[Dict]] = None) -> List[Dict[str, Any]]:
        """Apply filters to reports"""
        if reports is None:
            reports = list(self.reports.values())
        
        filtered = []
        
        for report in reports:
            match = True
            
            # Source filter
            if 'source' in filters and filters['source']:
                if report['content_source'] not in filters['source']:
                    match = False
            
            # Language filter
            if 'language' in filters and filters['language']:
                if report['analysis']['language'] not in filters['language']:
                    match = False
            
            # Category filter
            if 'category' in filters and filters['category']:
                if not any(cat in filters['category'] for cat in report['analysis']['category']):
                    match = False
            
            # Content type filter
            if 'content_type' in filters and filters['content_type']:
                if report['analysis']['content_type'] not in filters['content_type']:
                    match = False
            
            # Complexity filter
            if 'complexity' in filters and filters['complexity']:
                if report['analysis']['complexity_level'] not in filters['complexity']:
                    match = False
            
            # Topics filter
            if 'topics' in filters and filters['topics']:
                if not any(topic in filters['topics'] for topic in report['analysis']['key_topics']):
                    match = False
            
            # Audio filter
            if 'has_audio' in filters and filters['has_audio'] is not None:
                if report['media']['has_audio'] != filters['has_audio']:
                    match = False
            
            # Date range filters
            if 'date_from' in filters or 'date_to' in filters:
                published_at = report.get('published_at')
                if published_at:
                    try:
                        if published_at.endswith('Z'):
                            dt = datetime.fromisoformat(published_at[:-1])
                        else:
                            dt = datetime.fromisoformat(published_at)
                        
                        if 'date_from' in filters and filters['date_from']:
                            from_dt = datetime.fromisoformat(filters['date_from'])
                            if dt < from_dt:
                                match = False
                        
                        if 'date_to' in filters and filters['date_to']:
                            to_dt = datetime.fromisoformat(filters['date_to'])
                            if dt > to_dt:
                                match = False
                                
                    except (ValueError, AttributeError):
                        pass
            
            if match:
                filtered.append(report)
        
        return filtered
    
    def _apply_text_search(self, query: str, reports: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Apply text search to reports"""
        if not query:
            return reports
        
        # Simple text search across title and topics
        query_terms = query.split()
        filtered = []
        
        for report in reports:
            report_id = report['id']
            search_text = self.search_index.get(report_id, '')
            
            # Also search directly in title if not in index (fallback)
            if not search_text:
                title = report.get('title', '').lower()
                topics = ' '.join(report.get('analysis', {}).get('key_topics', [])).lower()
                search_text = f"{title} {topics}"
            
            # Check if all query terms are present
            if all(term in search_text for term in query_terms):
                filtered.append(report)
        
        return filtered
    
    def _apply_sorting(self, sort: str, reports: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Apply sorting to reports"""
        
        if sort == 'newest':
            return sorted(reports, key=lambda r: r.get('published_at', ''), reverse=True)
        elif sort == 'oldest':
            return sorted(reports, key=lambda r: r.get('published_at', ''))
        elif sort == 'title' or sort == 'title_asc':
            return sorted(reports, key=lambda r: r.get('title', '').lower())
        elif sort == 'title_desc':
            return sorted(reports, key=lambda r: r.get('title', '').lower(), reverse=True)
        elif sort == 'duration' or sort == 'duration_desc':
            return sorted(reports, key=lambda r: r.get('duration_seconds', 0), reverse=True)
        elif sort == 'duration_asc':
            return sorted(reports, key=lambda r: r.get('duration_seconds', 0))
        else:
            # Default to newest
            return sorted(reports, key=lambda r: r.get('published_at', ''), reverse=True)
    
    def _format_report_for_api(self, report: Dict[str, Any]) -> Dict[str, Any]:
        """Format report for API response"""
        return {
            'id': report['id'],
            'title': report['title'],
            'thumbnail_url': report['thumbnail_url'],
            'canonical_url': report['canonical_url'],
            'channel': report.get('channel', ''),
            'published_at': report['published_at'],
            'duration_seconds': report['duration_seconds'],
            'analysis': report['analysis'],
            'media': report['media'],
            'file_stem': report['file_stem'],
            'video_id': report.get('video_id', ''),
        }
    
    def get_report_count(self) -> int:
        """Get total number of indexed reports"""
        if self.needs_refresh():
            self.refresh_index()
        return len(self.reports)
    
    def get_report_by_id(self, report_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific report by ID"""
        if self.needs_refresh():
            self.refresh_index()
        return self.reports.get(report_id)
