# (Legacy) 🤖 NEW CLAUDE EMPLOYEE HANDOFF - Dashboard Component

## 🚨 IMMEDIATE CONTEXT (September 15, 2025)

### **What Just Happened:**
- **Major data disaster** caused by sync architecture flaw
- **Sophisticated categorization system** (67 subcategory records) was lost and recovered
- **Root cause identified**: Auto-sync after video processing overwrites entire database
- **Solution identified**: Migrate to PostgreSQL to eliminate dual-database complexity

### **Current Status:**
- ✅ **System working** - disaster recovered, data restored
- ✅ **Protection implemented** - backups, safety checks, snapshots
- ⚠️ **Architecture still fragile** - needs PostgreSQL migration

## 📋 **Critical Knowledge for New Claude:**

### **The Delete Disaster Sequence:**
1. **User deletes videos** on Dashboard (removes from Render SQLite)
2. **User processes new video** on NAS
3. **Auto-sync triggers**: `subprocess.run(['python', 'sync_sqlite_db.py'])`
4. **NAS SQLite overwrites entire Render SQLite**
5. **Deleted videos "restored"** + sophisticated categorization lost

### **Architecture Flaw:**
```
CURRENT (BROKEN):
NAS SQLite ←sync→ Render SQLite
    ↑              ↓
  Adds only     Deletes only
```

```
SOLUTION (NEEDED):
NAS ←connects→ PostgreSQL ←connects→ Dashboard
           (Single source of truth)
```

### **Key Files Understanding:**

**Dashboard Database Access:**
- `telegram_bot.py` - Main server, handles deletions
- `modules/sqlite_content_index.py` - Database interface layer
- `static/dashboard_v3.js` - Frontend delete functionality

**Critical Delete Flow:**
1. Frontend: `data-action="confirm-delete"` → `handleDelete()`
2. API call: `DELETE /api/delete/${id}`
3. Backend: `handle_delete_request()` → `_delete_one()`
4. SQLite: `DELETE FROM content WHERE id = ?`
5. **Missing**: Sync deletion back to NAS

## 🎯 **NEXT ACTIONS FOR NEW CLAUDE:**

### **Immediate Priority: PostgreSQL Migration**
1. **Follow migration plan**: `/Volumes/Docker/YTV2/POSTGRESQL_MIGRATION_PLAN.md`
2. **Use feature branches** - NEVER work directly on main
3. **Create backups first** - disaster recovery available
4. **Test thoroughly** before merging

### **Safety Commands:**
```bash
# If anything goes wrong during migration:
cd /Users/markdarby/projects/YTV2-Dashboard
git checkout main  # Instant recovery to working state

cd /Volumes/Docker/YTV2
git checkout main  # Instant recovery to working state
```

## 🔍 **Key Insights Learned:**

### **What I Learned About This Codebase:**
1. **Dual SQLite architecture is inherently fragile**
2. **Auto-sync is dangerous** - never overwrite entire databases
3. **User has sophisticated categorization** that must be preserved
4. **Delete functionality works** - sync back is what's missing
5. **MCP Render tools available** for PostgreSQL creation

### **Dashboard-Specific Insights:**
- **Frontend is solid** - dashboard_v3.js, CSS, templates all work well
- **Delete UI is perfect** - the backend sync is the only issue
- **Database layer is clean** - sqlite_content_index.py is well-structured
- **API endpoints work** - just need PostgreSQL instead of SQLite

### **Critical Don'ts:**
- ❌ **Never modify frontend** - it works perfectly
- ❌ **Never auto-sync entire databases** - causes race conditions
- ❌ **Never work directly on main branch** - use feature branches
- ❌ **Never ignore subcategory data** - user has 67 records that are precious

## 📊 **Database Preservation Requirements:**

**MUST PRESERVE during migration:**
- **67 records with subcategory data**
- **Sophisticated categorization system**
- **Multi-category assignments**
- **All content metadata**

**Current database stats to verify:**
```sql
-- Should return 67
SELECT COUNT(*) FROM content WHERE subcategory IS NOT NULL;

-- Should return ~68 total records
SELECT COUNT(*) FROM content;
```

## 🛡️ **Recovery Options Available:**
- ✅ **Git branches** with working state
- ✅ **Database backups** in `/Volumes/Docker/YTV2/backups/`
- ✅ **Daily automated backups** via cron
- ✅ **Asustor snapshots** (volume-level)

**The user has been through "new employee syndrome" disaster - BE CAUTIOUS and use branches!**
