# YTV2 PostgreSQL Migration Specification

## What We're Building

Eliminate YTV2's dual SQLite architecture by migrating to a single PostgreSQL database, ending the sync disasters that cause data loss and race conditions.

### Current Problem
- **Dual SQLite Databases**: NAS component and Dashboard component each maintain separate databases
- **"Nuclear Overwrite" Sync**: Auto-sync after video processing overwrites entire Dashboard database
- **Race Conditions**: Deleting videos while processing causes sophisticated categorization loss
- **Data Disasters**: 67 carefully curated subcategory records lost multiple times due to sync conflicts

### Root Cause Analysis
```
USER DELETES VIDEO ON DASHBOARD → Removes from Dashboard SQLite
            ↓
USER PROCESSES NEW VIDEO ON NAS → Triggers auto-sync
            ↓
AUTO-SYNC OVERWRITES DASHBOARD → NAS SQLite replaces entire Dashboard SQLite
            ↓
DELETED VIDEOS "RESTORED" + CATEGORIZATION LOST
```

### Target Solution
Single PostgreSQL database serving both components, eliminating all synchronization complexity.

## Core Capabilities

### 1. Unified Database Architecture
**What**: Single PostgreSQL instance on Render serving both NAS and Dashboard components, providing a single source of truth for all video metadata, categorization, and summary information.
**Why**: Eliminates dual-database synchronization complexity entirely
**How**: Both NAS ingestion and Dashboard frontend connect to the same PostgreSQL instance via shared ORM/SQLAlchemy layer with consistent schema contracts
**For**: Both components access same data in real-time without sync delays

### 2. Preserved Data Integrity
**What**: All existing video metadata, summaries, and categorization preserved during migration
**Why**: Zero tolerance for data loss during architectural changes
**For**: Users continue accessing all content without interruption

### 3. Identical User Experience
**What**: No changes to Dashboard UI, NAS workflows, or API endpoints
**Why**: Migration should be transparent to end users
**For**: Existing workflows continue working without modification

### 4. Real-Time Consistency
**What**: Changes in one component immediately visible in the other
**Why**: Eliminates delayed consistency issues from sync processes
**For**: Delete operations work correctly without restoration delays

### 5. Transactional Safety
**What**: Database writes are atomic and cannot leave partial data
**Why**: Prevents corruption during video processing or deletion
**For**: Reliable data integrity during all operations

## Problem Scenarios (Current State)

### Sync Disaster Scenario
1. **User deletes multiple videos** via Dashboard interface
2. **Videos removed** from Dashboard SQLite database
3. **User processes new video** on NAS component
4. **Auto-sync triggers** `subprocess.run(['python', 'sync_sqlite_db.py'])`
5. **NAS SQLite overwrites** entire Dashboard SQLite database
6. **Deleted videos reappear** + sophisticated categorization lost
7. **Data disaster complete** - manual recovery required

### Race Condition Scenario
1. **User starts deleting videos** via Dashboard (long operation)
2. **User processes video** on NAS simultaneously
3. **NAS completes first** and triggers auto-sync
4. **Dashboard delete completes** on now-stale database
5. **Next auto-sync restores** deleted videos, losing delete work

### Categorization Loss Scenario
1. **67 videos enhanced** with sophisticated subcategorization
2. **Auto-sync overwrites** Dashboard with NAS version
3. **NAS version lacks** recent categorization enhancements
4. **Sophisticated data lost** requiring manual restoration from backups

## Target User Experience (Post-Migration)

### Seamless Dashboard Experience
1. **User deletes videos** via Dashboard interface
2. **Videos immediately removed** from shared PostgreSQL
3. **Deletion visible** across all components instantly
4. **No restoration** via sync - delete is permanent and correct

### Reliable NAS Processing
1. **User processes new video** on NAS component
2. **Video data written** directly to shared PostgreSQL
3. **Content immediately available** on Dashboard
4. **No sync step required** - real-time consistency

### Consistent Data Layer
1. **Both components read/write** same PostgreSQL database
2. **No synchronization delays** between components
3. **Atomic transactions** prevent partial data corruption
4. **Foreign key constraints** ensure referential integrity

## Technical Requirements

### Database Architecture
- **Single PostgreSQL instance** hosted on Render
- **Shared access** from both NAS and Dashboard components
- **Transactional writes** preventing partial data corruption
- **Cascade deletes** ensuring proper cleanup

### Migration Safety
- **Comprehensive backups** before any destructive operations
- **Idempotent migration scripts** safe for multiple runs
- **Dual-write validation period** before cutover
- **Rollback procedures** tested and documented

### Performance Standards
- **Sub-second Dashboard loading** maintained or improved
- **Efficient query patterns** using lateral joins
- **Proper indexing** for JSON filters and future vector search
- **No performance regression** from current SQLite baseline

### Data Preservation
- All 67 sophisticated categorization records preserved
- Complete video metadata and summary content migrated
- Audio file associations maintained
- API response formats unchanged

## Success Measures

### Elimination Metrics
- 0 sync scripts remaining in codebase
- 0 SQLite database files in production
- 0 auto-sync subprocess calls
- 0 race conditions possible between components

### Preservation Metrics
- 100% of categorization records preserved
- 100% of video metadata migrated
- 100% of summary content accessible
- 100% of existing API endpoints functional

### User Experience Metrics
- 0 UI changes required for users
- 0 workflow modifications needed
- 0 performance regression detected
- 0 data inconsistency windows

## Constraints and Assumptions

### Technical Constraints
- Must use existing Render PostgreSQL infrastructure
- Must preserve all existing data without loss
- Must maintain API compatibility during migration
- Must support both component access patterns

### Scope Constraints
- **In Scope**: Database migration, sync elimination, data preservation
- **Out of Scope**: UI changes, new features, API modifications, workflow enhancements
- **Future Scope**: Vector search, semantic features (post-migration)

### Timeline Constraints
- 7-day implementation window
- Feature branch development required
- Comprehensive testing before cutover
- Rollback capability maintained throughout

## Quality Attributes

### Reliability
- **Zero data loss** during migration process
- **Complete rollback procedures** for failed migrations
- **Audit trails** for all migration steps
- **Automated backups** protecting against corruption

### Performance
- **Sub-second response times** maintained
- **Efficient query patterns** optimized for PostgreSQL
- **Proper indexing strategy** for current and future needs
- **Transactional overhead** minimized

### Maintainability
- **Clean separation** of concerns between components
- **Documented architectural decisions** for future reference
- **Elimination of complex sync logic** reducing technical debt
- **Single source of truth** simplifying debugging

---

*This specification provides the foundation for technical planning and safe implementation of YTV2's PostgreSQL migration.*
