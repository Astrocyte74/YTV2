# YTV2 PostgreSQL Migration Implementation Tasks

*Generated from YTV2 PostgreSQL Migration specification for systematic implementation*


## Phase 0: Freeze & Snapshot - Day 1

### GitHub Project Bootstrapping (RECOMMENDED, can run in parallel)
- [ ] (T-Y000) **Create milestones, labels, and issues from spec-kit**
  - **Implementation**: Convert each `T-Yxxx` task in this file into a GitHub Issue with labels and milestones
  - **Repository**: `Astrocyte74/YTV2`
  - **Milestones**: 
    - Phase 0 – Safety & Backups
    - Phase 1 – Postgres Provision
    - Phase 2 – Schema & Import
    - Phase 3 – Dual-Write & Cutover
    - Phase 4 – Decommission SQLite
  - **Labels**: `spec-kit`, `postgres`, `migration`, `phase-0|1|2|3|4`, `ai-run` (optional)
  - **Script (optional)**: Use `gh` script to parse `tasks.md` and create issues (see memo to Claude)
  - **Testing**: Verify all 27 issues (T-Y000…T-Y026) exist with correct milestone + labels
  - **Git**: Commit "T-Y000: Bootstrap GitHub milestones/labels/issues from spec-kit"
  - **Acceptance**: Issues list reflects all tasks with proper milestones/labels; project board (optional) shows all items


### Environment Preparation (CRITICAL)
- [ ] (T-Y001) **Stop all processing and create comprehensive backups**
  - **Implementation**: Stop Docker containers, create timestamped SQLite backups
  - **Location**: `/Volumes/Docker/YTV2/` and `/Users/markdarby/projects/YTV2-Dashboard/`
  - **Commands**:
    - `docker-compose down`
    - `cp data/ytv2_content.db ytv2_nas_pre_postgres_$(date +%Y%m%d_%H%M%S).db`
    - `curl -H "Authorization: Bearer $SYNC_SECRET" $DASHBOARD_URL/api/download-database -o dashboard_pre_postgres_$(date +%Y%m%d_%H%M%S).db`
  - **Testing**: Verify backup files exist and are readable via sqlite3
  - **Git**: Commit "T-Y001: Create comprehensive pre-migration backups"
  - **Acceptance**: Both SQLite databases backed up with verification of 67 categorization records

- [ ] (T-Y002) **Provision PostgreSQL database on Render**
  - **Implementation**: Purchase/provision a managed PostgreSQL instance on Render
  - **Configuration**:
    - **Service name**: `ytv2-database`
    - **Plan**: `Basic 1GB` (start; can scale later)
    - **Region**: same as Dashboard (e.g., `oregon`)
    - **Backups**: Enable automated daily backups + on-demand snapshots
  - **Billing**: Confirm Render billing is active and the new Postgres service is billable
  - **Environment**:
    - Set `DATABASE_URL` in **both** components (Dashboard + NAS)
    - Store credentials in secrets manager; do **not** commit plaintext URLs
  - **Verification**:
    - `psql $DATABASE_URL -c "SELECT version();"`
    - `psql $DATABASE_URL -c "CREATE EXTENSION IF NOT EXISTS pgcrypto;"`
    - `psql $DATABASE_URL -c "SHOW server_version;"`
  - **Testing**: Confirm connectivity from both environments; verify backups appear in Render UI
  - **Git**: Commit "T-Y002: Provision PostgreSQL on Render (billing + backups configured)"
  - **Acceptance**: PostgreSQL accessible from both components; backups enabled; credentials configured

- [ ] (T-Y003) **Verify data integrity baseline**
  - **Implementation**: Document current data state for migration verification
  - **Queries**:
    - `SELECT COUNT(*) FROM content;` (expected: ~68 total)
    - `SELECT COUNT(*) FROM content WHERE analysis_json LIKE '%subcategories%';` (expected: 67)
    - `SELECT COUNT(*) FROM content WHERE topics_json LIKE '%key_topics%';` (sanity check)
  - **Documentation**: Record exact counts, sample data structures
  - **Testing**: Export representative sample for post-migration comparison
  - **Git**: Commit "T-Y003: Document baseline data integrity"
  - **Acceptance**: Complete inventory of current data with verification checksums

## Phase 1: Schema & Migration - Days 1-2

### PostgreSQL Schema Creation
- [ ] (T-Y004) **Create unified PostgreSQL schema**
  - **Implementation**: Execute idempotent schema creation script
  - **Location**: `/Users/markdarby/projects/YTV2-Dashboard/migrations/`
  - **Schema**: content table, content_summaries table, indexes, triggers
  - **Features**: Updated_at triggers, JSON GIN indexes, FK constraints
  - **Testing**: Verify all tables created, constraints active, indexes present
  - **Git**: Commit "T-Y004: Implement PostgreSQL schema with performance optimizations"
  - **Acceptance**: Complete schema matches plan.md specification

- [ ] (T-Y004A) **Install latest-pointer triggers & view**
  - **Implementation**: Create `mark_latest_summary()` trigger function, `trg_summaries_mark_latest_ins/upd` triggers, and `v_latest_summaries` view (one row per `(video_id, variant)` with `is_latest=TRUE`)
  - **Location**: `/Users/markdarby/projects/YTV2-Dashboard/migrations/001_schema.sql`
  - **Testing**:
    - Insert 2 summaries for same `(video_id, variant)` → Only the newest has `is_latest=TRUE`
    - Update older row → `is_latest` flips to the updated row
    - `SELECT * FROM v_latest_summaries WHERE video_id=?` returns exactly one row per `variant`
  - **Git**: Commit "T-Y004A: Add latest-pointer triggers and v_latest_summaries view"
  - **Acceptance**: Triggers enforce single-latest invariant and the view returns expected rows

- [ ] (T-Y005) **Create idempotent migration script**
  - **Implementation**: Python script for SQLite → PostgreSQL data migration
  - **Location**: `/Users/markdarby/projects/YTV2-Dashboard/migrations/migrate_sqlite_to_postgres.py`
  - **Features**: Robust field extraction, JSON parsing, conflict resolution
  - **Safety**: ON CONFLICT handling, transaction safety, error recovery
  - **Testing**: Run against test data, verify idempotency (can run multiple times)
  - **Git**: Commit "T-Y005: Create robust data migration script"
  - **Acceptance**: Script handles all edge cases, safe for reruns

### Data Migration Execution
- [ ] (T-Y006) **Migrate content metadata from SQLite**
  - **Implementation**: Execute migration script for content table
  - **Source**: Both NAS and Dashboard SQLite files (use most recent)
  - **Verification**: Compare record counts, spot-check complex JSON fields
  - **Rollback**: Keep SQLite files for emergency recovery
  - **Testing**: Verify all 67 categorization records preserved correctly
  - **Git**: Commit "T-Y006: Migrate content metadata with integrity verification"
  - **Acceptance**: 100% data migration success, categorization preserved

- [ ] (T-Y007) **Create content_summaries from existing summary data**
  - **Implementation**: Extract HTML summaries and create revision 1 records
  - **Format**: Use existing Dashboard formatter to ensure identical rendering
  - **Variants**: Start with 'comprehensive' variant only
  - **Testing**: Compare rendered HTML output between SQLite and PostgreSQL **(visual diff on three samples: short, long/chunked, and dict-as-string)**  
  - **Git**: Commit "T-Y007: Create content_summaries with formatted HTML"
  - **Acceptance**: All videos have summary records, rendering identical **(no visible differences > 1 line in side-by-side)**

- [ ] (T-Y007A) **Normalize dict-as-string summaries during migration**
  - **Implementation**: Parser handles both JSON (`{"comprehensive": ...}`) and Python-literal (`{'comprehensive': ...}`) forms; unescape `\\n → \n`
  - **Location**: `/Users/markdarby/projects/YTV2-Dashboard/migrations/migrate_sqlite_to_postgres.py`
  - **Testing**:
    - Inputs: (a) plain string, (b) JSON dict-as-string, (c) Python dict-as-string
    - Output: normalized text + pre-rendered HTML present in `content_summaries.html`
  - **Git**: Commit "T-Y007A: Normalize dict-as-string summaries and prerender HTML"
  - **Acceptance**: 100% of migrated rows produce non-empty `html`; no JSON parse errors in logs

- [ ] (T-Y008) **Verify complete data integrity**
  - **Implementation**: Run comprehensive verification queries
  - **Checks**:
    - Record counts match baseline
    - JSON fields properly formatted
    - Foreign key constraints satisfied
    - No orphaned records
  - **Comparison**: Side-by-side SQLite vs PostgreSQL for sample records
  - **Testing**: Automated integrity check script
  - **Git**: Commit "T-Y008: Verify complete data migration integrity"
  - **Acceptance**: All verification checks pass, no data corruption detected

## Phase 2: Dual-Write + Shadow-Read - Days 3-4

### NAS Dual-Write Implementation
- [ ] (T-Y009) **Create database abstraction layer**
  - **Implementation**: DatabaseManager class supporting both SQLite and PostgreSQL
  - **Location**: `/Volumes/Docker/YTV2/modules/database_manager.py`
  - **Features**: Transactional writes, dual-write mode, error handling
  - **Environment**: DUAL_WRITE_MODE and DATABASE_URL configuration
  - **Testing**: Verify both databases receive identical data
  - **Git**: Commit "T-Y009: Implement database abstraction with dual-write"
  - **Acceptance**: NAS writes to both databases atomically

- [ ] (T-Y010) **Update video processing pipeline**
  - **Implementation**: Replace direct SQLite calls with DatabaseManager
  - **Location**: `/Volumes/Docker/YTV2/modules/telegram_handler.py`
  - **Changes**: Remove sync subprocess calls, use database_manager
  - **Safety**: Maintain transaction boundaries, error recovery
  - **Testing**: Process test video, verify data appears in both databases
  - **Git**: Commit "T-Y010: Update video processing to use database abstraction"
  - **Acceptance**: Video processing writes to PostgreSQL correctly

### Dashboard Shadow-Read Implementation
- [ ] (T-Y011) **Add PostgreSQL support to content index**
  - **Implementation**: Extend sqlite_content_index.py with PostgreSQL queries
  - **Location**: `/Users/markdarby/projects/YTV2-Dashboard/modules/sqlite_content_index.py`
  - **Features**: Feature flag support, lateral join queries, filter compatibility, **fallback to any available variant if 'comprehensive' missing (ordering: comprehensive → key-points → bullet-points → executive → key-insights → audio → audio-fr → audio-es)**
  - **Environment**: READ_FROM_POSTGRES flag for gradual cutover
  - **Testing**: Compare API responses between SQLite and PostgreSQL
  - **Git**: Commit "T-Y011: Add PostgreSQL support with feature flag"
  - **Acceptance**: Dashboard can read from PostgreSQL with identical results

- [ ] (T-Y011A) **Adopt lateral-join + fallback card query**
  - **Implementation**: Use `LEFT JOIN LATERAL` against `v_latest_summaries` for (a) `variant='comprehensive'` and (b) any variant with defined precedence, selecting first non-null
  - **Location**: `/Users/markdarby/projects/YTV2-Dashboard/modules/sqlite_content_index.py`
  - **Testing**:
    - Card list includes videos with only non-comprehensive variants
    - Response time ≤ 500ms for 1k rows on Render
  - **Git**: Commit "T-Y011A: Implement lateral-join fallback query for cards"
  - **Acceptance**: Cards display summaries where any variant exists; performance meets target

- [ ] (T-Y012) **Implement lateral join query pattern**
  - **Implementation**: Efficient latest revision lookup for cards
  - **Pattern**: LEFT JOIN LATERAL for content_summaries
  - **Performance**: Verify query execution time <500ms for large result sets
  - **Compatibility**: Ensure results match current SQLite query structure
  - **Testing**: Load test with full dataset, compare performance
  - **Git**: Commit "T-Y012: Implement efficient PostgreSQL query patterns"
  - **Acceptance**: Card loading performance meets or exceeds SQLite baseline

### Validation Phase
- [ ] (T-Y013) **Enable shadow reads for admin testing**
  - **Implementation**: Feature flag to enable PostgreSQL reads for specific users
  - **Environment**: READ_FROM_POSTGRES=true for admin-only testing
  - **Testing**: Compare dashboard rendering between SQLite and PostgreSQL
  - **Validation**: Verify filters, search, individual pages work identically
  - **Monitoring**: Log any differences for investigation
  - **Git**: Commit "T-Y013: Enable shadow reads for validation testing"
  - **Acceptance**: Admin can use PostgreSQL backend with identical experience

- [ ] (T-Y014) **Validate dual-write consistency**
  - **Implementation**: Automated checking that both databases stay in sync
  - **Monitoring**: Regular comparison queries between SQLite and PostgreSQL
  - **Alerts**: Flag any inconsistencies for immediate investigation
  - **Testing**: Process multiple videos, delete videos, verify consistency
  - **Recovery**: Procedures for handling sync drift if detected
  - **Git**: Commit "T-Y014: Implement dual-write consistency monitoring"
  - **Acceptance**: Both databases remain synchronized during dual-write period

## Phase 3: Cutover - Days 5-6

### Dashboard Migration
- [ ] (T-Y015) **Switch Dashboard to PostgreSQL reads**
  - **Implementation**: Set READ_FROM_POSTGRES=true in Render environment
  - **Monitoring**: Watch for any UI differences, performance issues, errors
  - **Rollback**: Immediate flag toggle back to SQLite if issues detected
  - **Testing**: Comprehensive dashboard testing, all endpoints functional
  - **User Impact**: Monitor user activity for any reported issues
  - **Git**: Commit "T-Y015: Switch Dashboard to PostgreSQL reads"
  - **Acceptance**: Dashboard fully functional on PostgreSQL with no user impact

- [ ] (T-Y015A) **Add DB health endpoints & pooling**
  - **Implementation**: `/health/db` endpoint returns `200` on `SELECT 1`; enable PgBouncer (if available) or connection pooling; add exponential backoff on connect
  - **Location**: Dashboard server & NAS service entrypoints
  - **Testing**: Health endpoint returns 200; graceful reconnect after forced restart
  - **Git**: Commit "T-Y015A: Health checks and connection pooling"
  - **Acceptance**: Zero cold-start errors in logs; uptime checks pass

- [ ] (T-Y016) **Remove dangerous sync code**
  - **Implementation**: Delete/comment out auto-sync subprocess calls
  - **Location**: `/Volumes/Docker/YTV2/modules/telegram_handler.py`
  - **Target**: `subprocess.run(['python', 'sync_sqlite_db.py'])` calls
  - **Safety**: Keep files temporarily for emergency rollback
  - **Testing**: Verify video processing no longer triggers auto-sync
  - **Git**: Commit "T-Y016: Remove dangerous auto-sync code"
  - **Acceptance**: No more "nuclear overwrite" sync operations possible

### Delete Flow Updates
- [ ] (T-Y017) **Update delete endpoint for PostgreSQL**
  - **Implementation**: Modify delete handler to use shared PostgreSQL
  - **Location**: `/Users/markdarby/projects/YTV2-Dashboard/telegram_bot.py`
  - **Features**: Handle both id formats, cascade delete via FK constraints
  - **Safety**: Transactional deletes, proper error handling
  - **Testing**: Delete videos, verify removal from both components
  - **Git**: Commit "T-Y017: Update delete flow for shared PostgreSQL"
  - **Acceptance**: Delete operations work correctly without sync restoration

- [ ] (T-Y018) **Verify end-to-end delete workflow**
  - **Implementation**: Full test of delete → process → verify consistency
  - **Test Case**: Delete video via Dashboard, process new video on NAS
  - **Test Case**: Delete B while processing A; ensure A completion does **not** resurrect B (historical regression test)
  - **Expected**: Deleted video stays deleted, new video appears correctly
  - **Historical Issue**: This scenario previously caused data disasters
  - **Validation**: Confirm no sync restoration of deleted content
  - **Git**: Commit "T-Y018: Verify delete workflow prevents restoration"
  - **Acceptance**: Delete operations are permanent and correct

## Phase 4: Cleanup - Day 7

### SQLite Elimination
- [ ] (T-Y019) **Disable dual-write mode**
  - **Implementation**: Set DUAL_WRITE_MODE=false in NAS environment
  - **Verification**: Confirm NAS writes only to PostgreSQL
  - **Monitoring**: Verify no SQLite file modifications during processing
  - **Backup**: Keep SQLite files temporarily for emergency fallback
  - **Testing**: Process videos, confirm only PostgreSQL receives data
  - **Git**: Commit "T-Y019: Disable dual-write mode"
  - **Acceptance**: NAS writes exclusively to PostgreSQL

- [ ] (T-Y019A) **Guard-rail to prevent accidental SQLite writes**
  - **Implementation**: Add runtime assertion/feature-flag guard; fail fast if any SQLite write path is called
  - **Location**: `/Volumes/Docker/YTV2/modules/database_manager.py`
  - **Testing**: Simulate write call in read-only mode → expected exception; confirm no writes occur in logs
  - **Git**: Commit "T-Y019A: Add guard-rail against SQLite writes"
  - **Acceptance**: No SQLite file mtime changes after processing flows

- [ ] (T-Y020) **Archive SQLite files**
  - **Implementation**: Move SQLite files to archive directory
  - **Location**: Create `/archive/` directories in both components
  - **Naming**: Timestamped archive files for recovery if needed
  - **Cleanup**: Remove from active application paths
  - **Testing**: Verify applications continue functioning without SQLite files
  - **Git**: Commit "T-Y020: Archive SQLite files"
  - **Acceptance**: No active SQLite dependencies remain

### Code Cleanup
- [ ] (T-Y021) **Remove sync scripts and dependencies**
  - **Implementation**: Delete sync_sqlite_db.py, nas_sync.py files
  - **Review**: Search codebase for any remaining sync references **(`ripgrep -n "sync_sqlite|upload-database|download-database|subprocess\.run\(\s*\['python',\s*'sync_sqlite_db\.py'`)**
  - **Environment**: Remove unused environment variables
  - **Documentation**: Update README files to reflect PostgreSQL architecture
  - **Testing**: Verify clean builds with no missing dependencies
  - **Git**: Commit "T-Y021: Remove sync scripts and SQLite dependencies"
  - **Acceptance**: Codebase contains no sync-related code or dependencies

- [ ] (T-Y022) **Update environment documentation**
  - **Implementation**: Update CLAUDE.md files with PostgreSQL architecture
  - **Location**: Both component CLAUDE.md files
  - **Content**: Remove SQLite references, add PostgreSQL configuration
  - **Instructions**: Update development setup and deployment procedures
  - **Context**: Ensure future Claude sessions understand new architecture
  - **Git**: Commit "T-Y022: Update documentation for PostgreSQL architecture"
  - **Acceptance**: Documentation accurately reflects single-database architecture

## Success Criteria & Final Validation

### Data Integrity Validation
- [ ] (T-Y023) **Comprehensive data integrity audit**
  - **Implementation**: Automated verification of complete migration success
  - **Checks**:
    - All 67 categorization records present and correct
    - Total record count matches pre-migration baseline
    - JSON fields properly formatted and accessible
    - Foreign key relationships intact
  - **Comparison**: Sample data matches original SQLite structure
  - **Testing**: Automated integrity check suite
  - **Git**: Commit "T-Y023: Complete comprehensive data integrity audit"
  - **Acceptance**: 100% data preservation verified with detailed report

### Functional Validation
- [ ] (T-Y024) **End-to-end workflow testing**
  - **Implementation**: Test all critical user workflows
  - **Workflows**:
    - Process new video on NAS → appears on Dashboard
    - Delete video on Dashboard → permanently removed
    - Filter/search videos → same results as SQLite
    - Individual video pages → identical rendering
  - **Performance**: Response times meet or exceed SQLite baseline
  - **Testing**: Comprehensive UI and API testing
  - **Git**: Commit "T-Y024: Complete end-to-end workflow validation"
  - **Acceptance**: All user workflows function identically to pre-migration

### Performance Validation
- [ ] (T-Y025) **Performance baseline verification**
  - **Implementation**: Measure and compare key performance metrics
  - **Metrics**:
    - Dashboard loading time
    - API response times
    - Database query performance
    - Memory and CPU usage
    - **95th percentile card list API ≤ 500ms; P95 individual page API ≤ 400ms**
    - Database connection reuse/pooling metrics (no connection-storms; steady-state pool utilization & low churn)
  - **Comparison**: Must meet or exceed SQLite performance
  - **Optimization**: Address any performance regressions identified
  - **Testing**: Load testing with realistic user scenarios
  - **Git**: Commit "T-Y025: Verify performance meets baseline requirements"
  - **Acceptance**: Performance metrics meet or exceed SQLite baseline

### Architecture Validation
- [ ] (T-Y026) **Confirm sync disaster elimination**
  - **Implementation**: Verify no sync code paths remain active
  - **Tests**:
    - Search codebase for sync-related function calls
    - Verify no subprocess sync operations
    - Confirm no SQLite file dependencies
    - Test race condition scenarios that previously caused disasters
  - **Documentation**: Update architectural diagrams and documentation
  - **Monitoring**: Verify no sync-related errors in logs
  - **Git**: Commit "T-Y026: Confirm complete sync disaster elimination"
  - **Acceptance**: No sync disasters possible in new architecture

---

## Task Completion Standards

### Required Steps for Each Task
Every task MUST include these completion steps:

#### 1. **Testing Phase** 🧪
- **Unit tests** for new database functions
- **Integration tests** for cross-component operations
- **End-to-end tests** for critical user workflows
- **Performance benchmarks** for database operations

#### 2. **Git Workflow** 📝
- **Branch Strategy**: Feature branch for major phases, direct commits for fixes
- **Commit Standards**: "T-YXXX: [description]" format with task ID
- **Push Requirement**: Push to GitHub after successful completion
- **Review**: Code review for major architectural changes

#### 3. **Rollback Readiness** 🔄
- **Backup Verification**: Ensure rollback capability maintained
- **Flag Strategy**: Feature flags allow immediate rollback
- **Documentation**: Clear rollback procedures for each phase
- **Testing**: Rollback procedures tested and validated

### Task Template
```
- [ ] (T-YXXX) **Task Name**
  - **Implementation**: [Core work to be done]
  - **Location**: [Specific file paths]
  - **Testing**: [Specific tests to run]
  - **Git**: Commit with "T-YXXX: [description]" and push
  - **Acceptance**: [Specific success criteria]
```

## Success Definition

Migration is complete ONLY when:
1. ✅ All 67 sophisticated categorization records verified intact
2. ✅ Dashboard renders identically from PostgreSQL
3. ✅ Delete workflow works without sync restoration
4. ✅ No SQLite sync code paths remain active
5. ✅ Performance meets or exceeds SQLite baseline
6. ✅ End-to-end workflows function correctly
7. ✅ Comprehensive rollback procedures validated

## Emergency Procedures

### Immediate Rollback (if critical issues detected)
1. **Dashboard**: Set `READ_FROM_POSTGRES=false`
2. **NAS**: Set `DUAL_WRITE_MODE=true`
3. **Files**: Restore SQLite files from backup if corrupted
4. **Verification**: Confirm rollback successful via testing
5. **Investigation**: Document issues for resolution before retry

---

*Each task includes specific file locations, acceptance criteria, and git workflow requirements. This enables systematic implementation with full traceability and rollback capability.*
