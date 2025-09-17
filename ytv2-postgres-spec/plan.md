# YTV2 PostgreSQL Migration Implementation Plan

## Technical Architecture Overview

### Database Foundation (PostgreSQL)
```sql
-- Minimal schema preserving current YTV2 behavior
CREATE TABLE IF NOT EXISTS content (
    id TEXT PRIMARY KEY,                    -- "yt:<video_id>"
    video_id TEXT NOT NULL UNIQUE,          -- "<video_id>" (natural key)
    title TEXT NOT NULL,
    channel_name TEXT,
    canonical_url TEXT,
    thumbnail_url TEXT,
    duration_seconds INTEGER,
    indexed_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),

    -- JSON structures Dashboard expects
    analysis_json JSONB,                    -- categories/subcategories
    topics_json JSONB,                      -- key_topics, named_entities

    -- Metadata fields for filtering
    language TEXT,
    content_type TEXT,
    complexity_level TEXT,
    has_audio BOOLEAN DEFAULT false,

    -- Data quality constraints
    CONSTRAINT valid_video_id CHECK (video_id ~ '^[A-Za-z0-9_-]{11}$'),
    CONSTRAINT valid_language CHECK (language ~ '^[a-z]{2}$' OR language IS NULL)
);

-- Renderable summaries (what Dashboard cards read)
CREATE TABLE IF NOT EXISTS content_summaries (
    id BIGSERIAL PRIMARY KEY,
    video_id TEXT NOT NULL REFERENCES content(video_id) ON DELETE CASCADE,
    variant TEXT NOT NULL DEFAULT 'comprehensive',
    revision INTEGER NOT NULL DEFAULT 1,
    html TEXT NOT NULL,                     -- Pre-rendered HTML
    raw_json JSONB,                         -- Source data (post-normalization)
    is_latest BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT valid_variant CHECK (variant IN (
        'comprehensive','bullet-points','key-points','key-insights','executive','audio','audio-fr','audio-es'
    )),
    UNIQUE(video_id, variant, revision)
);

-- Indexes for current query patterns
CREATE INDEX IF NOT EXISTS idx_content_indexed_at ON content(indexed_at DESC);
CREATE INDEX IF NOT EXISTS idx_content_channel ON content(channel_name);
CREATE INDEX IF NOT EXISTS idx_summaries_vid_var_rev ON content_summaries (video_id, variant, revision DESC);
CREATE INDEX IF NOT EXISTS idx_summaries_latest ON content_summaries (video_id, variant) WHERE is_latest;

-- JSON search performance
CREATE INDEX IF NOT EXISTS idx_content_analysis_gin ON content USING GIN (analysis_json);
CREATE INDEX IF NOT EXISTS idx_content_topics_gin ON content USING GIN (topics_json);

-- Auto-updating timestamps
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

-- Maintain single latest revision per (video_id, variant)
CREATE OR REPLACE FUNCTION mark_latest_summary()
RETURNS TRIGGER AS $$
BEGIN
  UPDATE content_summaries
     SET is_latest = FALSE
   WHERE video_id = NEW.video_id
     AND variant = NEW.variant
     AND is_latest = TRUE;

  NEW.is_latest = TRUE;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_summaries_mark_latest_ins') THEN
    CREATE TRIGGER trg_summaries_mark_latest_ins
      BEFORE INSERT ON content_summaries
      FOR EACH ROW EXECUTE FUNCTION mark_latest_summary();
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_summaries_mark_latest_upd') THEN
    CREATE TRIGGER trg_summaries_mark_latest_upd
      BEFORE UPDATE OF revision, variant, video_id ON content_summaries
      FOR EACH ROW EXECUTE FUNCTION mark_latest_summary();
  END IF;
END$$;

-- Convenience view for latest summaries per (video_id, variant)
CREATE OR REPLACE VIEW v_latest_summaries AS
SELECT video_id, variant, revision, html, raw_json, created_at, updated_at
FROM content_summaries
WHERE is_latest = TRUE;
```

### Performance Optimization
```sql
-- Indexes for current query patterns (kept in schema above)
-- Additional helper indexes for card lists and filters
CREATE INDEX IF NOT EXISTS idx_content_created_title ON content(indexed_at DESC, title);

-- Timestamp triggers are defined idempotently in the schema block.
```

### Query Pattern (Dashboard Cards)
```sql
-- Efficient latest revision lookup uses is_latest + view
SELECT
  c.id, c.video_id, c.title, c.channel_name, c.canonical_url,
  c.indexed_at, c.analysis_json, c.topics_json, c.language,
  c.content_type, c.complexity_level, c.has_audio,
  coalesce(cs_comp.html, cs_any.html) AS summary_html,
  coalesce(cs_comp.variant, cs_any.variant) AS variant,
  coalesce(cs_comp.revision, cs_any.revision) AS revision
FROM content c
LEFT JOIN LATERAL (
  SELECT html, variant, revision
  FROM v_latest_summaries s
  WHERE s.video_id = c.video_id AND s.variant = 'comprehensive'
  LIMIT 1
) cs_comp ON TRUE
LEFT JOIN LATERAL (
  SELECT html, variant, revision
  FROM v_latest_summaries s
  WHERE s.video_id = c.video_id
  ORDER BY (CASE variant
              WHEN 'comprehensive' THEN 0
              WHEN 'key-points' THEN 1
              WHEN 'bullet-points' THEN 2
              WHEN 'executive' THEN 3
              WHEN 'key-insights' THEN 4
              WHEN 'audio' THEN 5
              WHEN 'audio-fr' THEN 6
              WHEN 'audio-es' THEN 7
              ELSE 99
            END), revision DESC
  LIMIT 1
) cs_any ON TRUE
ORDER BY c.indexed_at DESC
LIMIT $1 OFFSET $2;
```

## Implementation Strategy

### Phase 0: Freeze & Snapshot (Day 1)
**Goal**: Create clean starting point with comprehensive backups

#### Environment Preparation
```bash
# Stop all processing to ensure clean data state
cd /Volumes/Docker/YTV2
docker-compose down

# Create timestamped backups
cp data/ytv2_content.db "ytv2_nas_pre_postgres_$(date +%Y%m%d_%H%M%S).db"

cd /Users/markdarby/projects/YTV2-Dashboard
curl -H "Authorization: Bearer $SYNC_SECRET" \
     "https://ytv2-vy9k.onrender.com/api/download-database" \
     -o "dashboard_pre_postgres_$(date +%Y%m%d_%H%M%S).db"
```

#### Database Provisioning
```bash
# Create PostgreSQL on Render using MCP tools
mcp__render__create_postgres({
    "name": "ytv2-database",
    "plan": "basic_1gb",
    "region": "oregon"
})
```

#### Verification
```sql
-- Verify critical data preservation
sqlite3 ytv2_content.db "SELECT COUNT(*) FROM content WHERE analysis LIKE '%subcategories%';"
-- Expected: 67 records with sophisticated categorization
```

### Phase 1: Schema & Migration (Days 1-2)
**Goal**: Create PostgreSQL schema and migrate data with verification

#### Schema Creation
```python
# migration_001_create_schema.py
class SchemaCreator:
    def create_schema(self):
        """Idempotent schema creation"""
        with psycopg2.connect(self.postgres_url) as conn:
            with conn.cursor() as cur:
                cur.execute(open('schema.sql').read())
                conn.commit()
```

#### Data Migration
```python
class DataMigrator:
    def migrate_content(self):
        """Migrate from SQLite to PostgreSQL (idempotent)"""
        sqlite_conn = sqlite3.connect(self.sqlite_path)
        sqlite_conn.row_factory = sqlite3.Row

        with psycopg2.connect(self.postgres_url) as pg_conn:
            with pg_conn.cursor() as cur:
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
                            topics_json = EXCLUDED.topics_json,
                            updated_at = now()
                    """, self._extract_content_fields(row))

    def migrate_summaries(self):
        """Migrate summaries from SQLite to PostgreSQL with normalization."""
        sqlite_conn = sqlite3.connect(self.sqlite_path)
        sqlite_conn.row_factory = sqlite3.Row

        with psycopg2.connect(self.postgres_url) as pg_conn:
            with pg_conn.cursor() as cur:
                # Preferred path: dedicated table in SQLite if present
                try:
                    rows = list(sqlite_conn.execute("SELECT video_id, variant, revision, html, raw_json FROM content_summaries"))
                except sqlite3.OperationalError:
                    rows = []

                for r in rows:
                    cur.execute("""
                        INSERT INTO content_summaries (video_id, variant, revision, html, raw_json, is_latest)
                        VALUES (%(video_id)s, %(variant)s, %(revision)s, %(html)s, %(raw_json)s, TRUE)
                        ON CONFLICT (video_id, variant, revision) DO NOTHING
                    """, {
                        'video_id': r['video_id'],
                        'variant': r['variant'] or 'comprehensive',
                        'revision': r['revision'] or 1,
                        'html': r['html'],
                        'raw_json': r['raw_json'],
                    })

                # Fallback path: parse content.summary when present
                try:
                    cr = sqlite_conn.execute("SELECT video_id, summary FROM content WHERE summary IS NOT NULL AND TRIM(summary) != ''")
                except sqlite3.OperationalError:
                    cr = []

                for r in cr:
                    video_id = r['video_id']
                    raw = r['summary']
                    normalized = self._normalize_summary(raw)  # returns plain text
                    html = self._format_summary_html(normalized)
                    cur.execute("""
                        INSERT INTO content_summaries (video_id, variant, revision, html, raw_json, is_latest)
                        VALUES (%s, 'comprehensive', 1, %s, %s, TRUE)
                        ON CONFLICT (video_id, variant, revision) DO NOTHING
                    """, (video_id, html, json.dumps({'source': 'sqlite.content.summary', 'raw': raw})))

                pg_conn.commit()

    def _normalize_summary(self, value: str) -> str:
        """Handle dict-as-string (JSON or Python literal) and escape sequences."""
        if not value:
            return ""
        parsed = None
        if isinstance(value, str) and value.strip().startswith("{"):
            try:
                parsed = json.loads(value)
            except Exception:
                try:
                    import ast
                    parsed = ast.literal_eval(value)
                except Exception:
                    parsed = None
        if isinstance(parsed, dict):
            for key in ('comprehensive', 'bullet_points', 'key_points', 'summary', 'text'):
                if key in parsed and isinstance(parsed[key], str):
                    value = parsed[key]
                    break
        if "\\n" in value and "\n" not in value:
            value = value.replace("\\n", "\n")
        return value

    def _format_summary_html(self, text: str) -> str:
        """Very close to dashboard key-points formatter (server-side parity)."""
        lines = [ln.strip() for ln in (text or "").splitlines()]
        items = [ln[2:].strip() if ln.startswith("- ") else ln for ln in lines]
        return "<p>" + "</p><p>".join([i for i in items if i]) + "</p>"

    def _extract_content_fields(self, row: sqlite3.Row) -> Dict[str, Any]:
        """Robust field extraction with safe defaults"""
        def val(r: sqlite3.Row, key: str, default=None):
            return r[key] if (hasattr(r, "keys") and key in r.keys() and r[key] is not None) else default

        analysis = {}
        raw_analysis = val(row, 'analysis')
        if raw_analysis:
            try:
                analysis = json.loads(raw_analysis)
            except Exception:
                analysis = {}

        return {
            'id': val(row, 'id'),
            'video_id': val(row, 'video_id'),
            'title': val(row, 'title'),
            'channel_name': val(row, 'channel_name'),
            'canonical_url': val(row, 'canonical_url'),
            'thumbnail_url': val(row, 'thumbnail_url'),
            'duration_seconds': val(row, 'duration_seconds', 0),
            'indexed_at': val(row, 'indexed_at'),
            'analysis_json': json.dumps(analysis),
            'topics_json': json.dumps(analysis.get('key_topics', [])),
            'language': val(row, 'language', 'en'),
            'content_type': analysis.get('content_type'),
            'complexity_level': analysis.get('complexity_level'),
            'has_audio': bool(val(row, 'audio_file'))
        }
```

### Phase 2: Dual-Write + Shadow-Read (Days 3-4)
**Goal**: Validate PostgreSQL implementation before cutover

#### NAS: Dual-Write Implementation
```python
# modules/database_manager.py
class DatabaseManager:
    def __init__(self):
        self.postgres_url = os.getenv('DATABASE_URL')
        self.sqlite_path = 'data/ytv2_content.db'
        self.dual_write = os.getenv('DUAL_WRITE_MODE', 'true').lower() == 'true'

    def save_video_processing_result(self, video_data: Dict, summary_data: Dict):
        """Transactional save preventing partial writes"""
        # Primary: Write to PostgreSQL
        self._save_to_postgres(video_data, summary_data)

        # Temporary: Also write to SQLite during transition
        if self.dual_write:
            self._save_to_sqlite(video_data, summary_data)

    def _save_to_postgres(self, video_data: Dict, summary_data: Dict):
        """Atomic PostgreSQL write"""
        with psycopg2.connect(self.postgres_url) as conn:
            with conn.cursor() as cur:
                # Upsert content metadata
                cur.execute("""
                    INSERT INTO content (id, video_id, title, ...)
                    VALUES (%(id)s, %(video_id)s, %(title)s, ...)
                    ON CONFLICT (video_id) DO UPDATE SET
                        title = EXCLUDED.title,
                        analysis_json = EXCLUDED.analysis_json,
                        updated_at = now()
                """, video_data)

                # Create new summary revision (let DB enforce latest pointer)
                cur.execute("""
                    INSERT INTO content_summaries (video_id, variant, revision, html, raw_json)
                    VALUES (
                        %(video_id)s,
                        %(variant)s,
                        COALESCE((
                          SELECT MAX(revision) + 1 FROM content_summaries
                          WHERE video_id = %(video_id)s AND variant = %(variant)s
                        ), 1),
                        %(html)s,
                        %(raw_json)s
                    )
                """, {
                    'video_id': video_data['video_id'],
                    'variant': (summary_data.get('variant') or 'comprehensive'),
                    'html': self._format_summary_html(summary_data),
                    'raw_json': json.dumps(summary_data)
                })
                conn.commit()
```

#### Dashboard: Shadow-Read Implementation
```python
# modules/sqlite_content_index.py
class ContentIndex:
    def __init__(self):
        self.use_postgres = os.getenv('READ_FROM_POSTGRES', 'false').lower() == 'true'
        self.postgres_url = os.getenv('DATABASE_URL') if self.use_postgres else None

    def get_reports(self, filters: Dict, page: int, size: int) -> List[Dict]:
        """Read from active database"""
        if self.use_postgres:
            return self._get_reports_postgres(filters, page, size)
        else:
            return self._get_reports_sqlite(filters, page, size)

    def _get_reports_postgres(self, filters: Dict, page: int, size: int) -> List[Dict]:
        """PostgreSQL implementation using lateral join pattern"""
        with psycopg2.connect(self.postgres_url) as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                query = """
                    SELECT
                        c.id, c.video_id, c.title, c.channel_name,
                        c.canonical_url, c.thumbnail_url, c.indexed_at,
                        c.analysis_json, c.topics_json, c.language,
                        c.content_type, c.complexity_level, c.has_audio,
                        cs.html as summary_html, cs.variant, cs.revision
                    FROM content c
                    LEFT JOIN LATERAL (
                        SELECT html, variant, revision
                        FROM content_summaries s
                        WHERE s.video_id = c.video_id AND s.variant = 'comprehensive'
                        ORDER BY s.revision DESC
                        LIMIT 1
                    ) cs ON TRUE
                    WHERE 1=1
                """

                params = []
                # Apply filter logic (adapted for PostgreSQL JSON operations)
                if filters.get('category'):
                    query += " AND c.analysis_json->'categories' @> %s"
                    params.append(json.dumps(filters['category']))

                query += " ORDER BY c.indexed_at DESC LIMIT %s OFFSET %s"
                params.extend([size, page * size])

                cur.execute(query, params)
                return [dict(row) for row in cur.fetchall()]
```

### Phase 3: Cutover (Days 5-6)
**Goal**: Switch to PostgreSQL as primary database

#### Dashboard Cutover
```bash
# Set environment variable in Render
READ_FROM_POSTGRES=true

# Verify identical rendering
curl "https://ytv2-vy9k.onrender.com/api/reports?size=1" | jq '.reports[0]'

# Monitor all endpoints for consistency
# /, /api/reports, /api/filters, /<stem>.json
```

#### Health, Pooling & Secrets

- Enable pooled connections (Render) via **pgbouncer** if available.
- Add `/health/db` endpoint in Dashboard and NAS that performs `SELECT 1`.
- Store `DATABASE_URL` and flags (`READ_FROM_POSTGRES`, `DUAL_WRITE_MODE`) in Render Secrets.
- Add retry/backoff on connection failures (`psycopg connect_timeout=5`, exponential backoff on first 3 attempts).

#### Sync Code Elimination
```python
# Remove dangerous auto-sync from telegram_handler.py
# DELETE these lines that cause "nuclear overwrites":
# subprocess.run(['python', 'sync_sqlite_db.py'])

# Disable dual-write in NAS
DUAL_WRITE_MODE=false
```

#### Delete Flow Fix
```python
def handle_delete_request(identifier: str):
    """Delete by id or video_id with proper cascade"""
    video_id = identifier
    if identifier.startswith('yt:'):
        video_id = identifier.split(':', 1)[1]

    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            # Try delete by id first, fallback to video_id
            cur.execute("DELETE FROM content WHERE id = %s", (identifier,))
            if cur.rowcount == 0:
                cur.execute("DELETE FROM content WHERE video_id = %s", (video_id,))
            if cur.rowcount == 0:
                raise ValueError(f"Video {identifier} not found")
            conn.commit()
            return {"deleted": video_id, "cascade_summaries": True}
```

### Phase 4: Cleanup (Day 7)
**Goal**: Remove all SQLite dependencies and sync code

#### File Cleanup
```bash
# Archive SQLite files
mv data/ytv2_content.db data/archive/ytv2_content_backup_$(date +%Y%m%d).db
mv ytv2_content.db archive/dashboard_backup_$(date +%Y%m%d).db

# Remove sync scripts
rm sync_sqlite_db.py nas_sync.py
```

#### Code Cleanup
```python
# Remove dual-write capability
# Update DatabaseManager to use only PostgreSQL
# Remove SQLite connection code
# Update environment variable requirements
```

## Technology Stack Details

### Database Components
- **PostgreSQL 16+** on Render with automated backups
- **psycopg[binary] 3.1+** for Python database connectivity
- **Transactional writes** preventing data corruption
- **Foreign key constraints** ensuring referential integrity

### Migration Components
- **Idempotent scripts** safe for multiple runs
- **Comprehensive backups** before destructive operations
- **Rollback procedures** tested and documented
- **Data integrity verification** at each step

### Monitoring & Validation
- **Query performance tracking** (<500ms target)
- **Data integrity checks** (foreign keys, constraints)
- **UI rendering comparison** (SQLite vs PostgreSQL)
- **API response validation** (format consistency)

## Risk Mitigation

### Rollback Procedures

> Note: Because we keep dual-write during Phase 2, rollback simply flips the `READ_FROM_POSTGRES` flag off and continues operating from the SQLite snapshot taken in Phase 0. No data will be lost if cutover validation fails.

```bash
# Emergency rollback to SQLite
# 1. Set READ_FROM_POSTGRES=false in Dashboard
# 2. Restore SQLite files from backup
# 3. Re-enable dual-write in NAS if needed
# 4. Document issues for retry planning
```

### Data Integrity Validation
```sql
-- Migration verification queries
SELECT COUNT(*) as total_content FROM content;
SELECT COUNT(*) as total_summaries FROM content_summaries;
SELECT COUNT(*) as with_subcategories
FROM content WHERE analysis_json::text LIKE '%subcategories%';

-- Constraint validation
SELECT COUNT(*) as orphan_summaries FROM content_summaries cs
LEFT JOIN content c ON c.video_id = cs.video_id
WHERE c.video_id IS NULL;
```

### Performance Monitoring
- Dashboard loading time comparison
- API response time benchmarks
- Database query execution plans
- Memory and CPU usage patterns

## Success Validation

### Technical Metrics
- ✅ All 67 categorization records preserved
- ✅ Dashboard rendering identical before/after
- ✅ API responses match SQLite format
- ✅ Delete workflow functions correctly
- ✅ No sync code remaining in codebase

### User Experience Metrics
- ✅ No UI changes visible to users
- ✅ No workflow disruptions
- ✅ No performance regressions
- ✅ Real-time consistency achieved

### Platform Integration
- ✅ Single database serves both components
- ✅ Transactional safety implemented
- ✅ Cascade deletes working correctly
- ✅ Automated backups protecting data

---

*This implementation plan provides the detailed technical roadmap for safely executing YTV2's PostgreSQL migration while eliminating all sync disasters.*