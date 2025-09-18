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

- [ ] (T-Y002) **Provision PostgreSQL database + new Render web service**
  - **Implementation**: Create parallel system - PostgreSQL database + new web service (keep production untouched)
  - **PostgreSQL Configuration**:
    - **Service name**: `ytv2-database`
    - **Plan**: `Basic 1GB` (start; can scale later)
    - **Region**: same as Dashboard (e.g., `oregon`)
    - **Backups**: Enable automated daily backups + on-demand snapshots
  - **New Web Service Configuration**:
    - **Service name**: `ytv2-dashboard-postgres`
    - **Repository**: Same repo, branch `postgres-migration-phase0`
    - **Environment variables**:
      - `READ_FROM_POSTGRES=true`
      - `DATABASE_URL=postgresql://...` (new PostgreSQL instance)
      - All other vars identical to production (except sync-related)
    - **Health endpoints**: Add `/health` and `/health/db` (SELECT 1)
  - **Safety**: Keep separate DATABASE_URL secrets; do NOT reuse production secrets
  - **Verification**:
    - `psql $DATABASE_URL -c "SELECT version();"`
    - Both health endpoints return 200 on new service
    - New service completely isolated from production
  - **Testing**: Confirm new service deploys successfully; PostgreSQL connectivity verified
  - **Git**: Commit "T-Y002: Provision PostgreSQL + parallel web service (production untouched)"
  - **Acceptance**: New parallel system ready; production continues running unmodified

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

### Data Migration Execution (One-Time Snapshot)
- [ ] (T-Y006) **One-time data snapshot from production to new PostgreSQL**
  - **Implementation**: Execute migration script from current production SQLite to new PostgreSQL
  - **Source**: Production backup `dashboard_pre_postgres_20250917_162149.db` (81 records, 74 categorized)
  - **Target**: New PostgreSQL instance in parallel service only
  - **Safety**: Production SQLite never touched - using backup snapshot
  - **Verification**: Compare record counts, spot-check complex JSON fields
  - **Testing**: Verify all 74 categorization records preserved correctly in new system
  - **Git**: Commit "T-Y006: One-time data snapshot to parallel PostgreSQL system"
  - **Acceptance**: 100% data migration success in new system, production unaffected

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

## Phase 2: Parallel Testing & Validation - Days 3-4

### New Service Deployment & Testing
- [ ] (T-Y009) **Deploy new system on postgres-migration-phase0 branch**
  - **Implementation**: Deploy new web service with PostgreSQL backend
  - **Service**: `ytv2-dashboard-postgres` pointing to migration branch
  - **Environment**: `READ_FROM_POSTGRES=true`, new DATABASE_URL
  - **Health checks**: Verify `/health` and `/health/db` endpoints return 200
  - **Testing**: Confirm new service loads with migrated data
  - **Git**: Commit "T-Y009: Deploy parallel PostgreSQL service successfully"
  - **Acceptance**: New service running independently with PostgreSQL data

- [ ] (T-Y010) **Comprehensive API parity testing**
  - **Implementation**: Compare API responses between production and new service
  - **Endpoints**: `/api/reports`, `/api/filters`, individual video pages
  - **Validation**: Ensure identical JSON responses and UI rendering
  - **Performance**: Verify response times meet production baseline (<500ms)
  - **Testing**: Automated comparison script between both services
  - **Git**: Commit "T-Y010: Validate API parity between SQLite and PostgreSQL"
  - **Acceptance**: New service produces identical results to production

### Stakeholder Validation
- [ ] (T-Y011) **Stakeholder testing on new parallel system**
  - **Implementation**: Share new service URL with testers for comprehensive validation
  - **URL**: `ytv2-dashboard-postgres.onrender.com` (new parallel service)
  - **Test scenarios**: Navigation, filtering, search, individual video pages, audio playback
  - **Validation**: Visual comparison with production for UI/UX parity
  - **Feedback**: Document any issues or discrepancies found
  - **Performance**: Monitor response times and user experience
  - **Testing**: End-users validate functionality matches production exactly
  - **Git**: Commit "T-Y011: Complete stakeholder validation of parallel system"
  - **Acceptance**: Stakeholders confirm new system ready for production cutover

- [ ] (T-Y012) **Performance validation of new system**
  - **Implementation**: Load testing and performance verification of new PostgreSQL service
  - **Metrics**: Response times, query performance, memory usage, concurrent users
  - **Baseline**: Must meet or exceed current production performance
  - **Tools**: Load testing scripts, monitoring dashboard metrics
  - **Testing**: Simulate production traffic patterns on new service
  - **Git**: Commit "T-Y012: Validate performance meets production requirements"
  - **Acceptance**: New system performs equal or better than current production

## Phase 3: Safe Cutover - Days 5-6

### Cutover Preparation
- [ ] (T-Y013) **Prepare for cutover - brief freeze window**
  - **Implementation**: Coordinate brief processing freeze for final data synchronization
  - **Communication**: Notify stakeholders of planned cutover window (5-10 minutes)
  - **NAS preparation**: Prepare dual-write mode for final sync if needed
  - **Monitoring**: Set up real-time monitoring for cutover process
  - **Rollback plan**: Document instant rollback procedures (DNS switch back)
  - **Git**: Commit "T-Y013: Prepare cutover coordination and rollback procedures"
  - **Acceptance**: Cutover plan documented, stakeholders informed, rollback ready

### DNS/Service Cutover
- [ ] (T-Y014) **Execute DNS/domain switch to new service**
  - **Implementation**: Switch domain/DNS to point to new PostgreSQL service
  - **Method**: Update Render service routing or custom domain configuration
  - **Verification**: Confirm new service receiving production traffic
  - **Monitoring**: Watch error rates, response times, user experience
  - **Immediate rollback**: DNS switch back if any issues detected
  - **Git**: Commit "T-Y014: Complete DNS cutover to PostgreSQL service"
  - **Acceptance**: Production traffic successfully routed to new system

### Post-Cutover Validation
- [ ] (T-Y015) **Monitor stability and validate workflows**
  - **Implementation**: 24-48 hour monitoring period of new production system
  - **Monitoring**: Error rates, performance metrics, user feedback
  - **Validation**: End-to-end workflow testing in live production
  - **Issue response**: Immediate rollback capability if problems arise
  - **User support**: Monitor for any user-reported issues
  - **Git**: Commit "T-Y015: Complete post-cutover stability monitoring"
  - **Acceptance**: New system stable for 24-48 hours, ready for cleanup phase

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
