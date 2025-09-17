# 🗄️ YTV2 PostgreSQL Migration Plan - Production-Ready Implementation

## 🚨 CRITICAL CONTEXT

### **Current Problem:**
- **Dual SQLite architecture** causing data disasters via auto-sync overwrites
- **Race conditions** between deleting (Dashboard) and processing (NAS)
- **Loss of sophisticated categorization** (67 subcategory records) due to sync conflicts

### **Solution:**
Single PostgreSQL database as source of truth for both NAS and Dashboard components, eliminating all sync complexity.

## 📋 **Scoped Migration Strategy**

### **Scope: YTV2 → PostgreSQL Only**
- ✅ **No frontend changes** - preserve existing UI/UX
- ✅ **No new endpoints** - maintain API compatibility
- ✅ **Zero data loss** - preserve all 67 sophisticated categorization records
- ✅ **Eliminate sync disasters** - single source of truth
- ❌ **No unified platform features yet** - keep laser-focused on YTV2 stability

## 🗃️ **Minimal PostgreSQL Schema**

### **Core Tables**
```sql
-- Main content metadata (replaces current content table structure)
CREATE TABLE content (
    id TEXT PRIMARY KEY,                    -- "yt:<video_id>"
    video_id TEXT NOT NULL UNIQUE,         -- "<video_id>"
    title TEXT NOT NULL,
    channel_name TEXT,
    canonical_url TEXT,
    thumbnail_url TEXT,
    duration_seconds INTEGER,
    indexed_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),

    -- Preserve existing JSON structures Dashboard expects
    analysis_json JSONB,                   -- categories/subcategories, analysis data
    topics_json JSONB,                     -- key_topics, named_entities, etc.

    -- Metadata fields Dashboard currently uses
    language TEXT,
    content_type TEXT,
    complexity_level TEXT,
    has_audio BOOLEAN DEFAULT false,

    -- Constraints for data quality
    CONSTRAINT valid_video_id CHECK (video_id ~ '^[A-Za-z0-9_-]{11}$'),
    CONSTRAINT valid_language CHECK (language ~ '^[a-z]{2}$' OR language IS NULL)
);

-- Renderable summaries (what inline cards actually read from)
CREATE TABLE content_summaries (
    id BIGSERIAL PRIMARY KEY,
    video_id TEXT NOT NULL REFERENCES content(video_id) ON DELETE CASCADE,

    -- Support multiple summary variants and versions
    variant TEXT NOT NULL DEFAULT 'comprehensive',  -- 'clinical', 'patient', 'comprehensive'
    revision INTEGER NOT NULL DEFAULT 1,

    -- Pre-rendered content for frontend
    html TEXT NOT NULL,                     -- Fully formatted HTML for reader
    raw_json JSONB,                         -- Optional: source data for future use

    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),

    -- Ensure unique variants per video
    UNIQUE(video_id, variant, revision)
);

-- Performance indexes
CREATE INDEX idx_content_indexed_at ON content(indexed_at DESC);
CREATE INDEX idx_content_channel ON content(channel_name);
CREATE INDEX idx_content_language ON content(language);
CREATE INDEX idx_summaries_video_variant ON content_summaries(video_id, variant);

-- Prefer "latest revision" via index + lateral join (no materialized view)
CREATE INDEX IF NOT EXISTS idx_summaries_vid_var_rev
  ON content_summaries (video_id, variant, revision DESC);

-- Keep updated_at fresh on UPDATEs
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_content_updated_at') THEN
    CREATE TRIGGER trg_content_updated_at
      BEFORE UPDATE ON content
      FOR EACH ROW EXECUTE FUNCTION set_updated_at();
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_summaries_updated_at') THEN
    CREATE TRIGGER trg_summaries_updated_at
      BEFORE UPDATE ON content_summaries
      FOR EACH ROW EXECUTE FUNCTION set_updated_at();
  END IF;
END$$;

-- JSON filter performance for dashboard filters
CREATE INDEX IF NOT EXISTS idx_content_analysis_gin ON content USING GIN (analysis_json);
CREATE INDEX IF NOT EXISTS idx_content_topics_gin   ON content USING GIN (topics_json);

-- Cards query pattern (PostgreSQL; uses latest revision without a view)
-- (Recommended pattern for dashboard reads)
 /*
 SELECT
   c.id, c.video_id, c.title, c.channel_name, c.canonical_url, c.thumbnail_url,
   c.indexed_at, c.analysis_json, c.topics_json, c.language, c.content_type,
   c.complexity_level, c.has_audio,
   cs.html AS summary_html, cs.variant, cs.revision
 FROM content c
 LEFT JOIN LATERAL (
   SELECT html, variant, revision
   FROM content_summaries s
   WHERE s.video_id = c.video_id AND s.variant = 'comprehensive'
   ORDER BY s.revision DESC
   LIMIT 1
 ) cs ON TRUE
 ORDER BY c.indexed_at DESC
 LIMIT $1 OFFSET $2;
 */
```

### **Why This Schema Works:**
- ✅ **Cards read via lateral join** - efficient latest revision lookup without materialized views
- ✅ **Individual pages** use same HTML rendering - consistent display
- ✅ **Deletes cascade correctly** - content → content_summaries cleanup
- ✅ **Preserves variants and revisions** - supports future summary types
- ✅ **JSON compatibility** - analysis_json/topics_json match current structure

## 🔄 **Safe Cutover Plan**

### **Phase 1: Freeze + Snapshot (Day 1)**
```bash
# Stop processing to ensure clean snapshot
cd /Volumes/Docker/YTV2
docker-compose down

# Create comprehensive backup
cp data/ytv2_content.db "ytv2_content_pre_postgres_$(date +%Y%m%d_%H%M%S).db"

# Download current Render database
cd /Users/markdarby/projects/YTV2-Dashboard
curl -H "Authorization: Bearer $SYNC_SECRET" \
     "https://ytv2-vy9k.onrender.com/api/download-database" \
     -o "render_pre_postgres_$(date +%Y%m%d_%H%M%S).db"

# Verify critical data intact
sqlite3 ytv2_content.db "SELECT COUNT(*) FROM content WHERE analysis LIKE '%subcategories%';"
# Expected: 67 records with subcategories
```

### **Phase 2: Provision PostgreSQL (Day 1)**
```bash
# Use MCP Render tools to create database
mcp__render__create_postgres({
    "name": "ytv2-database",
    "plan": "basic_1gb",           # Start small, can scale
    "region": "oregon"             # Same region as dashboard
})

# Enable automated backups (verify retention policy)
# Set DATABASE_URL in both NAS and Dashboard environments
```

### **Phase 3: Schema + Migration Script (Day 1-2)**
**Location**: `/Users/markdarby/projects/YTV2-Dashboard/migrations/`

```python
# migration_001_create_schema.py - Idempotent schema creation
import psycopg2
import json
import sqlite3
from typing import Dict, Any

class PostgreSQLMigrator:
    def __init__(self, postgres_url: str, sqlite_path: str):
        self.postgres_url = postgres_url
        self.sqlite_path = sqlite_path

    def create_schema(self):
        """Create PostgreSQL schema (idempotent)"""
        with psycopg2.connect(self.postgres_url) as conn:
            with conn.cursor() as cur:
                # Execute schema SQL (use ON CONFLICT DO NOTHING for reruns)
                cur.execute(open('schema.sql').read())

    def migrate_content(self):
        """Migrate content from SQLite to PostgreSQL (idempotent)"""
        sqlite_conn = sqlite3.connect(self.sqlite_path)
        sqlite_conn.row_factory = sqlite3.Row

        with psycopg2.connect(self.postgres_url) as pg_conn:
            with pg_conn.cursor() as cur:
                # Migrate main content
                for row in sqlite_conn.execute("SELECT * FROM content"):
                    cur.execute("""
                        INSERT INTO content (
                            id, video_id, title, channel_name, canonical_url,
                            thumbnail_url, duration_seconds, indexed_at,
                            analysis_json, topics_json, language, content_type,
                            complexity_level, has_audio
                        ) VALUES (
                            %(id)s, %(video_id)s, %(title)s, %(channel_name)s,
                            %(canonical_url)s, %(thumbnail_url)s, %(duration_seconds)s,
                            %(indexed_at)s, %(analysis_json)s, %(topics_json)s,
                            %(language)s, %(content_type)s, %(complexity_level)s,
                            %(has_audio)s
                        ) ON CONFLICT (video_id) DO UPDATE SET
                            title = EXCLUDED.title,
                            analysis_json = EXCLUDED.analysis_json,
                            topics_json   = EXCLUDED.topics_json,
                            updated_at = now()
                    """, self._extract_content_fields(row))

                # Migrate summaries (create comprehensive variant)
                for row in sqlite_conn.execute("SELECT * FROM content"):
                    if row['summary']:  # Has summary content
                        html_content = self._format_summary_html(row)
                        cur.execute("""
                            INSERT INTO content_summaries (
                                video_id, variant, revision, html, raw_json
                            ) VALUES (
                                %(video_id)s, 'comprehensive', 1, %(html)s, %(raw_json)s
                            ) ON CONFLICT (video_id, variant, revision) DO UPDATE SET
                                html = EXCLUDED.html,
                                updated_at = now()
                        """, {
                            'video_id': row['video_id'],
                            'html': html_content,
                            'raw_json': json.dumps(self._extract_summary_data(row))
                        })

    def _extract_content_fields(self, row: sqlite3.Row) -> Dict[str, Any]:
        """Extract and normalize content fields"""

        def val(r: sqlite3.Row, key: str, default=None):
            return r[key] if (hasattr(r, "keys") and key in r.keys() and r[key] is not None) else default

        # Parse JSON-serialized analysis safely
        analysis = {}
        raw_analysis = val(row, 'analysis')
        if raw_analysis:
            try:
                analysis = json.loads(raw_analysis)
            except Exception:
                analysis = {}

        return {
            'id':               val(row, 'id'),
            'video_id':         val(row, 'video_id'),
            'title':            val(row, 'title'),
            'channel_name':     val(row, 'channel_name'),
            'canonical_url':    val(row, 'canonical_url'),
            'thumbnail_url':    val(row, 'thumbnail_url'),
            'duration_seconds': val(row, 'duration_seconds', 0),
            'indexed_at':       val(row, 'indexed_at'),
            'analysis_json':    json.dumps(analysis),
            'topics_json':      json.dumps(analysis.get('key_topics', [])),
            'language':         val(row, 'language', 'en'),
            'content_type':     analysis.get('content_type'),
            'complexity_level': analysis.get('complexity_level'),
            'has_audio':        bool(val(row, 'audio_file'))
        }

    def _format_summary_html(self, row: sqlite3.Row) -> str:
        """Format summary as HTML (matching current Dashboard formatter)"""
        # Use existing format_key_points logic from telegram_bot.py
        # This ensures identical rendering between old and new systems
        pass

    def verify_migration(self):
        """Verify migration completeness and data integrity"""
        with psycopg2.connect(self.postgres_url) as conn:
            with conn.cursor() as cur:
                # Check record counts
                cur.execute("SELECT COUNT(*) FROM content")
                content_count = cur.fetchone()[0]

                cur.execute("SELECT COUNT(*) FROM content_summaries")
                summary_count = cur.fetchone()[0]

                # Check subcategory preservation
                cur.execute("""
                    SELECT COUNT(*) FROM content
                    WHERE analysis_json::text LIKE '%subcategories%'
                """)
                subcategory_count = cur.fetchone()[0]

                print(f"Migration verification:")
                print(f"  Content records: {content_count}")
                print(f"  Summary records: {summary_count}")
                print(f"  Records with subcategories: {subcategory_count}")

                assert subcategory_count >= 67, "Subcategory data not preserved!"
```

### **Phase 4: Dual-Write + Shadow-Read (Day 3-4)**

#### **NAS Side: Dual-Write Implementation**
```python
# modules/database_manager.py - New abstraction layer
class DatabaseManager:
    def __init__(self):
        self.postgres_url = os.getenv('DATABASE_URL')
        self.sqlite_path = 'data/ytv2_content.db'
        self.dual_write = os.getenv('DUAL_WRITE_MODE', 'true').lower() == 'true'

    def save_video_processing_result(self, video_data: Dict, summary_data: Dict):
        """Transactional save to avoid partial writes"""

        # Always write to PostgreSQL (new primary)
        self._save_to_postgres(video_data, summary_data)

        # Temporarily also write to SQLite during transition
        if self.dual_write:
            self._save_to_sqlite(video_data, summary_data)

    def _save_to_postgres(self, video_data: Dict, summary_data: Dict):
        """Atomic write to PostgreSQL"""
        with psycopg2.connect(self.postgres_url) as conn:
            with conn.cursor() as cur:
                # Upsert content metadata
                cur.execute("""
                    INSERT INTO content (id, video_id, title, channel_name, ...)
                    VALUES (%(id)s, %(video_id)s, %(title)s, ...)
                    ON CONFLICT (id) DO UPDATE SET
                        title = EXCLUDED.title,
                        analysis_json = EXCLUDED.analysis_json,
                        updated_at = now()
                """, video_data)

                # Create new summary revision
                cur.execute("""
                    INSERT INTO content_summaries (video_id, variant, revision, html, raw_json)
                    VALUES (
                        %(video_id)s,
                        'comprehensive',
                        COALESCE((
                            SELECT MAX(revision) + 1
                            FROM content_summaries
                            WHERE video_id = %(video_id)s AND variant = 'comprehensive'
                        ), 1),
                        %(html)s,
                        %(raw_json)s
                    )
                """, {
                    'video_id': video_data['video_id'],
                    'html': self._format_summary_html(summary_data),
                    'raw_json': json.dumps(summary_data)
                })

                # Commit all changes atomically
                conn.commit()
```

#### **Dashboard Side: Shadow-Read Implementation**
```python
# modules/sqlite_content_index.py - Add PostgreSQL support
class ContentIndex:
    def __init__(self):
        self.use_postgres = os.getenv('READ_FROM_POSTGRES', 'false').lower() == 'true'
        self.postgres_url = os.getenv('DATABASE_URL') if self.use_postgres else None
        self.sqlite_path = 'ytv2_content.db'

    def get_reports(self, filters: Dict, page: int, size: int) -> List[Dict]:
        """Get paginated reports from active database"""
        if self.use_postgres:
            return self._get_reports_postgres(filters, page, size)
        else:
            return self._get_reports_sqlite(filters, page, size)

    def _get_reports_postgres(self, filters: Dict, page: int, size: int) -> List[Dict]:
        """Read from PostgreSQL using existing filter logic"""
        with psycopg2.connect(self.postgres_url) as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                # Use content_summaries_latest for card rendering
                query = """
                    SELECT
                        c.id, c.video_id, c.title, c.channel_name,
                        c.canonical_url, c.thumbnail_url, c.indexed_at,
                        c.analysis_json, c.topics_json, c.language,
                        c.content_type, c.complexity_level, c.has_audio,
                        cs.html as summary_html,
                        cs.variant, cs.revision
                    FROM content c
                    LEFT JOIN content_summaries_latest cs
                        ON cs.video_id = c.video_id AND cs.variant = 'comprehensive'
                    WHERE 1=1
                """

                # Apply existing filter logic (adapted to PostgreSQL)
                params = []
                if filters.get('category'):
                    query += " AND c.analysis_json->'categories' @> %s"
                    params.append(json.dumps(filters['category']))

                if filters.get('channel'):
                    query += " AND c.channel_name = ANY(%s)"
                    params.append(filters['channel'])

                # Add pagination
                query += " ORDER BY c.indexed_at DESC LIMIT %s OFFSET %s"
                params.extend([size, page * size])

                cur.execute(query, params)
                return [dict(row) for row in cur.fetchall()]
```

### **Phase 5: Flip Reads to PostgreSQL (Day 5)**
```bash
# Dashboard environment update
# Change READ_FROM_POSTGRES=true in Render environment

# Verify identical rendering
curl "https://ytv2-vy9k.onrender.com/api/reports?size=1" | jq '.reports[0]'
# Compare with SQLite version to ensure identical structure

# The dashboard card API should use the lateral-join pattern above
# to fetch the latest summary revision efficiently.

# Monitor for any UI differences or errors
# Test all key endpoints: /, /api/reports, /api/filters, /<stem>.json
```

### **Phase 6: Remove Sync + Dual-Write (Day 6)**
```python
# Remove dangerous sync code from telegram_handler.py
# Comment out or delete these lines:
# subprocess.run(['python', 'sync_sqlite_db.py'])  # NUCLEAR OVERWRITE

# Disable dual-write mode
# Set DUAL_WRITE_MODE=false in NAS environment

# Archive SQLite files (keep as backup)
mv data/ytv2_content.db data/archive/ytv2_content_sqlite_backup_$(date +%Y%m%d).db
```

### **Phase 7: Delete Flow Fix (Day 7)**
```python
# Dashboard: Update delete endpoint to use PostgreSQL
def handle_delete_request(identifier: str):
    """Delete by id ('yt:<video_id>') or by bare video_id with proper cascade"""
    video_id = identifier
    # Normalize: if prefixed id arrives, strip "yt:" and delete by video_id
    if identifier.startswith('yt:'):
        video_id = identifier.split(':', 1)[1]

    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            # Try delete by id first (just in case UI still sends id)
            cur.execute("DELETE FROM content WHERE id = %s", (identifier,))
            if cur.rowcount == 0:
                # Fallback: delete by video_id
                cur.execute("DELETE FROM content WHERE video_id = %s", (video_id,))
            if cur.rowcount == 0:
                raise ValueError(f"Video {identifier} not found")
            conn.commit()
            return {"deleted": video_id, "cascade_summaries": True}
```

## ✅ **Acceptance Criteria**

### **Data Integrity**
- [ ] All 67 records with subcategories preserved
- [ ] Total record count matches SQLite source
- [ ] No orphaned content_summaries records
- [ ] All JSON fields properly migrated

### **Functional Equivalence**
- [ ] Inline cards render identical HTML before/after cutover
- [ ] Individual report pages show same content
- [ ] All filter combinations work (category, channel, content_type, etc.)
- [ ] Search functionality preserved
- [ ] Audio playback unaffected

### **Delete Workflow**
- [ ] Dashboard delete removes content + cascades to summaries
- [ ] Deleted videos don't reappear after NAS processing
- [ ] No "nuclear overwrite" code paths remain

### **Performance**
- [ ] Card loading time ≤ current SQLite performance
- [ ] Individual page load time ≤ current performance
- [ ] API response times within acceptable range
- [ ] Database query plans optimized

### **Safety & Rollback**
- [ ] Automated PostgreSQL backups configured
- [ ] Rollback procedure tested and documented
- [ ] All sync scripts removed/disabled
- [ ] Environment variables properly configured

## 🚨 **Rollback Procedure**

If issues arise during cutover:

```bash
# 1. Immediate rollback (Dashboard)
# Set READ_FROM_POSTGRES=false in Render environment

# 2. Restore SQLite if needed
cd /Users/markdarby/projects/YTV2-Dashboard
cp "render_pre_postgres_*.db" ytv2_content.db

# 3. Re-enable NAS SQLite writes temporarily
cd /Volumes/Docker/YTV2
cp "ytv2_content_pre_postgres_*.db" data/ytv2_content.db
# Set DUAL_WRITE_MODE=true to resume SQLite operations

# 4. Document issues and plan resolution
# Never lose the PostgreSQL data - it becomes the source for retry
```

## 📊 **Migration Timeline**

| Day | Phase | Component | Actions |
|-----|-------|-----------|---------|
| 1 | Preparation | Both | Freeze, backup, provision PostgreSQL |
| 1-2 | Schema | Dashboard | Create schema, run migration script |
| 3-4 | Dual-write | NAS | Implement dual writes, test shadow reads |
| 5 | Cutover | Dashboard | Flip to PostgreSQL reads, monitor |
| 6 | Cleanup | NAS | Disable dual-write, remove sync scripts |
| 7 | Delete Fix | Dashboard | Update delete flow for PostgreSQL |

## 🔧 **Implementation Files**

### **New Files to Create:**
- `/Users/markdarby/projects/YTV2-Dashboard/migrations/schema.sql`
- `/Users/markdarby/projects/YTV2-Dashboard/migrations/migrate_sqlite_to_postgres.py`
- `/Volumes/Docker/YTV2/modules/database_manager.py`

### **Files to Modify:**
- `/Users/markdarby/projects/YTV2-Dashboard/modules/sqlite_content_index.py` - Add PostgreSQL support
- `/Users/markdarby/projects/YTV2-Dashboard/telegram_bot.py` - Update delete handler
- `/Volumes/Docker/YTV2/modules/telegram_handler.py` - Remove sync calls, use database_manager
- Both `.env` files - Add DATABASE_URL, feature flags

### **Files to Remove (Post-Cutover):**
- `/Volumes/Docker/YTV2/sync_sqlite_db.py`
- `/Volumes/Docker/YTV2/nas_sync.py`
- Any cron jobs or Docker commands calling sync scripts

## 🎯 **Success Definition**

**Migration is complete when:**
1. ✅ Dashboard reads from PostgreSQL with identical UI behavior
2. ✅ NAS writes directly to PostgreSQL with transactional safety
3. ✅ Delete workflow works without restoration via sync
4. ✅ All 67 sophisticated categorization records preserved
5. ✅ No SQLite sync code paths remain active
6. ✅ Automated backups protecting PostgreSQL data

**This eliminates the dual-database sync architecture that caused data disasters while maintaining all existing functionality.**
