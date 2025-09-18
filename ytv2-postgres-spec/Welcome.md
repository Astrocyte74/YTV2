# YTV2 PostgreSQL Migration - Welcome

## 🚨 CRITICAL: Active Database Migration Project

**Current State**: Dual SQLite architecture causing sync disasters
**Target State**: Single PostgreSQL eliminating all sync issues
**Status**: GitHub project set up, ready for Phase 0 implementation

## The Problem We're Solving

YTV2 currently runs a **dual SQLite architecture** that causes catastrophic data loss:

```
NAS Component (Processing)     Dashboard Component (Web UI)
├── ytv2_content.db           ├── ytv2_content.db
└── Auto-sync after          └── Gets overwritten
    video processing              ("Nuclear Overwrite")
```

**Sync Disaster Pattern**:
1. User deletes videos via Dashboard → Removes from Dashboard SQLite
2. User processes new video on NAS → Triggers auto-sync
3. **AUTO-SYNC OVERWRITES** entire Dashboard SQLite with NAS version
4. **Deleted videos "restored"** + 67 sophisticated categorization records lost

## The Solution

**Parallel deployment strategy** - Build new PostgreSQL system alongside current production:
- ✅ **Zero downtime** - current system stays live during migration
- ✅ **Zero risk** - new system built and tested separately
- ✅ **Safe cutover** - DNS switch with instant rollback capability
- ✅ **Complete validation** - thorough testing before any changes to production

## Project Structure

### Essential Files (Read These First)
| File | Purpose |
|------|---------|
| **spec.md** | What we're building and why (start here) |
| **plan.md** | Technical implementation details |
| **tasks.md** | 32 implementation tasks (T-Y000 through T-Y026) |
| **CONSTITUTION.md** | Non-negotiable migration safety principles |
| **GLOSSARY.md** | All terminology explained (excellent reference) |

### GitHub Project
- **Repository**: [Astrocyte74/YTV2](https://github.com/Astrocyte74/YTV2)
- **Issues**: 32 tasks created with proper milestones and labels
- **Automation**: Add `ai-run` label to any issue for AI implementation
- **Milestones**: 5 phases (Phase 0-4) with clear progression

## System Architecture

### Current Components
```
NAS Component (Docker)
├── Location: /Volumes/Docker/YTV2/
├── Purpose: YouTube processing, AI summarization
├── Database: SQLite (ytv2_content.db)
└── Problem: Source of "nuclear overwrites"

Dashboard Component (Render)
├── Location: /Users/markdarby/projects/YTV2-Dashboard/
├── Purpose: Web interface, audio streaming
├── Database: SQLite (synced from NAS)
└── Problem: Victim of overwrites, loses deletions
```

### Target Architecture (Parallel Deployment)
```
Current Production (Keep Running)
├── ytv2-vy9k.onrender.com (existing)
├── SQLite database (current)
└── Users continue uninterrupted

New Parallel System (Build & Test)
├── ytv2-dashboard-postgres (new Render service)
├── PostgreSQL database (new)
├── postgres-migration-phase0 branch
└── Complete validation environment

Final State (Post-Cutover)
├── PostgreSQL on Render (Single Source of Truth)
├── DNS switched to new service
├── Real-time consistency, no sync needed
└── Old system decommissioned safely
```

## Migration Phases

### Phase 0: Parallel System Setup (Day 1)
- **T-Y000**: Bootstrap GitHub project structure ✅
- **T-Y001**: Create comprehensive backups ✅
- **T-Y002**: Provision PostgreSQL + **new Render web service** (`ytv2-dashboard-postgres`)
- **T-Y003**: Document baseline data integrity (67 categorization records)

### Phase 1: Build New System (Days 1-2)
- **T-Y004**: Create PostgreSQL schema with triggers
- **T-Y005**: Build idempotent migration script
- **T-Y006-008**: One-time data snapshot from production SQLite to new PostgreSQL

### Phase 2: Parallel Testing & Validation (Days 3-4)
- **T-Y009-012**: Deploy new system on `postgres-migration-phase0` branch
- **T-Y013-014**: Comprehensive testing and stakeholder validation
- **Health checks**: `/health` and `/health/db` endpoints on new service

### Phase 3: Safe Cutover (Days 5-6)
- **T-Y015**: Brief freeze window + dual-write synchronization
- **T-Y016**: DNS/domain switch to new service
- **T-Y017-018**: Monitor stability, validate end-to-end workflows

### Phase 4: Decommission Old System (Day 7)
- **T-Y019-026**: Archive old SQLite, cleanup sync scripts, final validation

## Critical Data

### 67 Sophisticated Categorization Records
- **What**: Enhanced subcategory classifications applied to videos
- **Why Critical**: Manual curation requiring preservation
- **Risk**: Primary target of sync disasters - MUST be preserved
- **Verification**: Every migration step must verify these records intact

### Service Locations
- **Current Production**: `ytv2-vy9k.onrender.com` (SQLite, keep running)
- **New Parallel System**: `ytv2-dashboard-postgres` (PostgreSQL, to be created)
- **Database Files**:
  - Current SQLite: `/Users/markdarby/projects/YTV2-Dashboard/ytv2_content.db`
  - Backup: `dashboard_pre_postgres_20250917_162149.db` ✅
  - Target PostgreSQL: To be provisioned on Render

## Emergency Procedures (Parallel Deployment)

### 🔴 Instant Rollback (Zero Risk)
1. **DNS Switch Back**: Point domain back to original service (`ytv2-vy9k`)
2. **Current System**: Continues running unmodified throughout migration
3. **No Data Loss**: Original SQLite system never touched during parallel build
4. **Immediate Recovery**: Original service always available for instant rollback

### 🔴 Data Disaster Recovery
1. **Stop All Processing**: `docker-compose down` on NAS
2. **Assess Damage**: Compare current vs backup databases
3. **Restore from Backup**: Use most recent pre-migration backup
4. **Verify 67 Records**: Ensure categorization data intact
5. **Resume Safely**: Only restart after confirming data integrity

## Environment Variables

### Required Configuration
```bash
# PostgreSQL (to be set after T-Y002)
DATABASE_URL=postgresql://user:pass@host:port/db

# Feature Flags (migration control)
READ_FROM_POSTGRES=false          # Dashboard database source
DUAL_WRITE_MODE=false             # NAS dual-write behavior

# Security (existing)
SYNC_SECRET=your_secure_secret    # API authentication
```

### Component-Specific Paths
```bash
# NAS Component
/Volumes/Docker/YTV2/
├── data/ytv2_content.db          # Current SQLite
├── modules/database_manager.py   # New abstraction layer
└── modules/telegram_handler.py   # Remove sync calls

# Dashboard Component
/Users/markdarby/projects/YTV2-Dashboard/
├── ytv2_content.db               # Current SQLite (synced)
├── modules/sqlite_content_index.py  # Add PostgreSQL support
└── migrations/                   # New migration scripts
```

## Success Criteria

Migration is complete ONLY when:
1. ✅ All 67 sophisticated categorization records verified intact
2. ✅ Dashboard renders identically from PostgreSQL
3. ✅ Delete workflow works without sync restoration
4. ✅ No SQLite sync code paths remain active
5. ✅ Performance meets or exceeds SQLite baseline
6. ✅ End-to-end workflows function correctly
7. ✅ Comprehensive rollback procedures validated

## Quick Start for New Contributors

### If You're New to This Project
1. **Read spec.md** - Understand the problem and solution
2. **Review GLOSSARY.md** - Learn all terminology
3. **Check GitHub Issues** - See current task status
4. **Understand Architecture** - Study current vs target state
5. **Follow CONSTITUTION.md** - Non-negotiable safety principles

### If You're Implementing Tasks
1. **Check current phase** in GitHub milestones
2. **Read task details** in issues and tasks.md
3. **Follow safety procedures** - always backup first
4. **Test thoroughly** - verify acceptance criteria
5. **Maintain rollback capability** at every step

### If You're Using AI Automation
1. **Add `ai-run` label** to any GitHub issue
2. **Monitor PR creation** - AI will create implementation PR
3. **Review changes** - ensure they meet acceptance criteria
4. **Test before merge** - validate functionality
5. **Follow git workflow** - proper commit messages with task IDs

## Contact & Resources

### Documentation
- **This Folder**: `/Users/markdarby/projects/YTV2-Dashboard/ytv2-postgres-spec/`
- **GitHub Project**: https://github.com/Astrocyte74/YTV2
- **Tasks Reference**: All T-Y### tasks in GitHub Issues

### Key Architectural Insights
- **Natural Key**: video_id (YouTube ID) is the true unique identifier
- **Conflict Resolution**: Use `ON CONFLICT (video_id)` not `ON CONFLICT (id)`
- **Latest-Pointer Pattern**: Efficient revision tracking without materialized views
- **Lateral Joins**: PostgreSQL query pattern for summary retrieval
- **Dual-Write Phase**: Safe migration period with validation

---

**⚠️ Remember**: This migration eliminates a critical architectural flaw. Take time to understand the problem before implementing solutions. The 67 categorization records represent significant manual work that MUST be preserved.

**🎯 Goal**: Zero data loss, zero user impact, zero sync disasters in the new architecture.