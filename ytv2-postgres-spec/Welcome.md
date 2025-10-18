# YTV2 PostgreSQL Migration - Welcome

## 🚨 STATUS: Migration Complete

**Current State**: NAS and Dashboard now run on a shared PostgreSQL database.  
**Legacy State**: Dual SQLite architecture that caused repeated “nuclear overwrite” incidents.  
**Purpose of this Kit**: Preserve the migration playbook, safety notes, and context for future enhancements.

## Legacy Problem (Why This Exists)

```
NAS Component (SQLite)      Dashboard Component (SQLite)
├── Auto-sync after ingest  ├── Local deletions and edits
└── sync_sqlite_db.py  ---> └── Entire database overwritten, curated data lost
```

- 67 hand-curated categorization records were repeatedly wiped out.
- Deletions reappeared minutes later, eroding trust in the dashboard.
- Race conditions between deletes and ingest ran daily.

## Delivered Solution

Parallel deployment delivered a zero-downtime cutover to PostgreSQL:

- ✅ Built a new Render service + PostgreSQL instance in isolation.
- ✅ Migrated data, validated parity, and rehearsed rollback.
- ✅ Cut over via DNS flip with dual-write window for safety.
- ✅ Archived SQLite databases and removed sync scripts.

The production dashboard (`ytv2-vy9k.onrender.com`) now connects directly to PostgreSQL using `DATABASE_URL_POSTGRES_NEW`. The NAS ingest stack uses the same DSN, so both sides operate on one source of truth.

## Project Folder Overview

| File | Role today |
|------|------------|
| **spec.md** | Historical requirements + success criteria |
| **plan.md** | Implementation blueprint with notes on final architecture |
| **tasks.md** | Completed checklist (T-Y000…T-Y026) for audit trail |
| **CONSTITUTION.md** | Safety principles (updated to reflect JSONB decision) |
| **GLOSSARY.md** | Terminology with legacy vs current references |

GitHub issues referencing these tasks have been closed; keep them for traceability but open new issues for fresh work.

## Architecture Snapshot

```
Current Production (PostgreSQL)
├── NAS (Docker) ingest jobs
│   └── Uses shared PG via DATABASE_URL_POSTGRES_NEW
├── Render dashboard service
│   └── Uses modules/postgres_content_index.py
└── PostgreSQL (Render managed instance)

Legacy Assets (Archival Only)
├── SQLite backups in /archive
└── Retired Render staging service (ytv2-dashboard-postgres)
```

## Historical Phases (All Completed)

1. **Phase 0 – Backups & Staging**: Created verified snapshots, provisioned PostgreSQL + staging service.
2. **Phase 1 – Schema & Migration**: Brought up JSONB-centric schema, executed migration scripts, verified counts.
3. **Phase 2 – Validation**: Compared API responses, UI renders, and performance metrics.
4. **Phase 3 – Cutover**: Ran dual-write window, flipped DNS, monitored closely.
5. **Phase 4 – Cleanup**: Removed sync scripts, archived SQLite, confirmed audits.

Use these phases as a model for future infrastructure changes.

## Environment Variables (Current)

```bash
# Shared PostgreSQL DSN for both NAS and Dashboard
DATABASE_URL_POSTGRES_NEW=postgresql://user:pass@host:port/dbname

# Security
SYNC_SECRET=shared_secret

# Optional metrics bridge
NGROK_BASE_URL=https://<your-subdomain>.ngrok-free.app
NGROK_BASIC_USER=optional
NGROK_BASIC_PASS=optional

# Render supplies PORT; override only for local runs
PORT=10000
```

> ℹ️ Legacy flags such as `READ_FROM_POSTGRES` and `DUAL_WRITE_MODE` were temporary cutover switches and have been removed from the running code.

## Safety & Recovery (Still Relevant)

1. **Snapshot first**: Before major changes, capture a PostgreSQL dump plus existing SQLite archives.
2. **Pause ingest**: Disable NAS processing during risky operations.
3. **Validate curated records**: The 67 enhanced categorization entries remain the canary.
4. **Rollback playbook**: Reload a known-good snapshot into PostgreSQL and repoint the dashboard if ever required.

## Working With This Codebase

### New Contributors
- Read `spec.md` and `CONSTITUTION.md` to understand non-negotiables.
- Review `modules/postgres_content_index.py` to see how filters, variants, and JSONB payloads are served.
- Use the archived SQLite backups only for audits—do not reintroduce dual-database flows.

### Extending the System
- Preserve PostgreSQL integrity: migrations go through `migrations/` with reversible scripts.
- Maintain JSONB filter structures (analysis, topics, summary_variants) so the UI stays in sync.
- Keep API responses backward compatible unless bumping the dashboard together.

### Automation & AI Assistants
- Reference this spec-kit for context, but operate on the current PostgreSQL-first architecture.
- Open new issues instead of reusing T-Y### IDs; those denote completed historical work.

## Contacts & References

- Repo: `/Users/markdarby/projects/YTV2-Dashboard/`
- Context archive: `/Users/markdarby/projects/YTV2-Dashboard/archive/`
- Live dashboard: `ytv2-vy9k.onrender.com`
- Migration spec folder (this directory) for historical details.

---

**Key Takeaways**
- PostgreSQL is the single source of truth (`DATABASE_URL_POSTGRES_NEW`).
- JSONB fields in `content` + lateral joins supply dashboard data—no normalization layer for categories is required today.
- Keep those 67 curated categorization records intact.
- Treat this kit as both an operations manual and a cautionary tale.
