# YTV2 PostgreSQL Migration Specification

## Overview
This specification outlines the detailed requirements and implementation guidelines for migrating YTV2's data storage backend from SQLite to PostgreSQL. The goal is to achieve a seamless transition with zero data loss, no frontend changes, and complete parity in API behavior and UI rendering.

## Schema and Data Model Expectations

- The PostgreSQL schema must fully represent all existing data structures currently stored in SQLite, including:
  - **67 sophisticated categorization records** with all hierarchical and relational integrity preserved.
  - All video metadata fields: title, channel, thumbnails, audio files, and associated attributes.
  - Summary content stored both as formatted HTML and JSON structures, mapped appropriately to Postgres tables and JSONB columns.
- Categorization and subcategorization data must remain fully represented. The current implementation stores them in JSONB columns with strict validation, which is acceptable provided filter performance and integrity checks stay in place.
- Summary content should leverage PostgreSQL's JSONB capabilities for efficient querying and indexing.
- The schema must explicitly support cascade deletion to ensure that deleting a video or category propagates correctly without residual data or restoration after sync issues. JSONB storage must be pruned along with parent records.

## Migration Phases and Validation

- The migration must follow the defined phased approach:
  - **Phase 0: Freeze & Snapshot** - Create clean, consistent snapshots of SQLite data before migration.
  - **Phase 1: Schema & Migration** - Apply idempotent schema changes and data migration scripts.
  - **Phase 2: Dual-Write + Shadow-Read** - Implement dual-write parity checks ensuring that all writes go to both SQLite and PostgreSQL, with continuous shadow reads from PostgreSQL to validate consistency.
  - **Phase 3: Cutover** - Switch reads from SQLite to PostgreSQL behind a feature flag, ensuring reversibility.
  - **Phase 4: Cleanup** - Remove SQLite dependencies and sync code only after complete validation.
- During Phase 2, dual-write parity checks must be comprehensive and automated, detecting any discrepancies immediately.
- Shadow reads must confirm that PostgreSQL query results are identical to SQLite for all API endpoints and UI components.
- Rollback to SQLite snapshots is non-optional and must be readily available until parity is fully proven and validated.

## Safety, Rollback, and Race Condition Prevention

- Comprehensive backups must be created before any destructive operations.
- Data integrity verification must occur at every migration step.
- The system must prevent race conditions, especially between delete operations and new video processing workflows, to avoid data inconsistency or partial corruption.
- Transactional writes must be implemented to ensure atomicity and prevent partial data corruption.
- Rollback capability to SQLite snapshots must be maintained until the migration is fully validated and stable.

## API and Frontend Compatibility

- No changes to frontend UI or user experience are permitted throughout the migration.
- All API endpoints must maintain identical behavior, response formats, and performance characteristics.
- The migration must not introduce any new features or workflow changes.
- Performance must be monitored to avoid regressions exceeding 20% of baseline metrics.

## Elimination of Legacy Components

- All synchronization scripts causing overwrites or manual sync processes must be removed, including:
  - `sync_sqlite_db.py`
  - `nas_sync.py`
  - Auto-sync calls from `telegram_handler.py`
- The dual SQLite architecture must be eliminated in favor of a single PostgreSQL backend.
- Race conditions arising from legacy sync processes must be fully resolved.

## Logging and Audit

- All migration steps and data transformations must be logged with sufficient detail to enable audit trails.
- Errors must be handled gracefully with clear diagnostics and recovery paths.

---

*This specification is a living document and must be adhered to strictly to ensure a successful migration without data loss or service disruption.*
