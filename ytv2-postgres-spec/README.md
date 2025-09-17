# YTV2 PostgreSQL Migration - Spec-Kit Project

## 🎯 Project Overview

This spec-kit project serves as the **single source of truth** for eliminating YTV2's dual SQLite sync disasters by migrating to a unified PostgreSQL architecture.

This Spec-Kit is the result of lessons learned from past data disasters and sync race conditions. The PostgreSQL migration is designed explicitly to prevent those issues by ensuring data integrity, consistency, and robust synchronization mechanisms.

## 📁 Project Structure

```
ytv2-postgres-spec/
├── spec.md               # WHAT we're building and WHY
├── plan.md               # HOW to implement technically
├── tasks.md              # Actionable implementation tasks
├── CONSTITUTION.md       # Non-negotiable migration principles
├── GLOSSARY.md          # YTV2-specific terminology
└── README.md            # This file
```

## 🚀 Getting Started

### For AI Assistants
0. **Confirm verified backups exist** before proceeding
1. **Read `CONSTITUTION.md` first** - Non-negotiable migration principles
2. **Review `spec.md`** - Understand the sync disaster problem and solution vision
3. **Study `plan.md`** - Technical migration strategy and safety procedures
4. **Execute `tasks.md`** - Phase-by-phase implementation with acceptance criteria

### For Human Developers
1. Open this directory in VS Code with Claude Code extension
2. Use `/specify`, `/plan`, and `/tasks` commands to iterate on specifications
3. Reference target codebases:
   - `/Volumes/Docker/YTV2/` (NAS component - 50% of work)
   - `/Users/markdarby/projects/YTV2-Dashboard/` (Dashboard component - 50% of work)

## 🔄 Workflow Commands

```bash
# Update specifications
/specify "Refine migration requirements or safety procedures"

# Refine technical implementation
/plan

# Generate updated task breakdown
/tasks
```

## 🎯 Implementation Strategy

### **Phase 0: Freeze & Snapshot (Day 1)**
- Comprehensive backups of both SQLite databases
- Verification of 67 sophisticated categorization records
- Creation of PostgreSQL instance on Render
- Freeze new video processing during this phase to avoid race conditions

### **Phase 1: Schema & Migration (Days 1-2)**
- Idempotent PostgreSQL schema creation using `video_id` as the natural key
- Indexes must support lateral-join queries (no materialized views)
- Data migration from SQLite with integrity verification
- Lateral join patterns for performance

### **Phase 2: Dual-Write + Shadow-Read (Days 3-4)**
- NAS writes to both SQLite and PostgreSQL
- Dashboard feature flag for PostgreSQL reads
- Validation of identical rendering
- Dual-write is temporary and must include logging to verify parity between SQLite and PostgreSQL

### **Phase 3: Cutover (Days 5-6)**
- Flip Dashboard to PostgreSQL reads
- Remove dangerous sync scripts from NAS
- Delete flow updates for shared database
- Test delete flows carefully to ensure cascade behavior in PostgreSQL matches dashboard expectations

### **Phase 4: Cleanup (Day 7)**
- Remove dual-write mode
- Archive SQLite files
- Verification testing

## 📊 Success Criteria

- ✅ All 67 sophisticated categorization records preserved
- ✅ Dashboard renders identically from PostgreSQL
- ✅ Delete workflow works without sync restoration
- ✅ No "nuclear overwrite" sync code remaining
- ✅ Real-time consistency between NAS and Dashboard
- ✅ No race conditions between NAS processing and dashboard deletions observed during tests

## 🔗 Context Files

### Current Problem Documentation
- `/Users/markdarby/projects/YTV2-Dashboard/NEW_CLAUDE_CONTINUATION.md` - Data disaster analysis
- `/Users/markdarby/projects/YTV_temp_NAS_files/POSTGRESQL_MIGRATION_PLAN.md` - Technical plan
- `/Users/markdarby/projects/YTV2-Dashboard/CLAUDE.md` - Dashboard architecture context

### Key Implementation Files
- **NAS Component**: `/Volumes/Docker/YTV2/` (processing, Telegram bot)
- **Dashboard Component**: `/Users/markdarby/projects/YTV2-Dashboard/` (web interface)
- **Current Databases**: SQLite files in both components requiring unification

## 🚨 Critical Safety Notes

- **NEVER work directly on main branch** - use feature branches
- **ALWAYS verify backups** before any destructive operations
- **Test extensively** in dual-write phase before cutover
- **Preserve all categorization data** - zero tolerance for data loss
- Freeze all deletions and processing during cutover windows

---

*This spec-kit project ensures safe, systematic elimination of YTV2's sync disasters while preserving all existing functionality and data.*
