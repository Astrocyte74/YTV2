# YTV2 PostgreSQL Migration Glossary

## Core Concepts

### Sync Disaster
The critical architectural flaw causing data loss in YTV2's dual SQLite system:
- **Auto-Sync Overwrite**: NAS SQLite completely replaces Dashboard SQLite after video processing
- **Race Conditions**: Deleting while processing causes sophisticated categorization loss
- **"Nuclear Overwrite"**: Term for the destructive `subprocess.run(['python', 'sync_sqlite_db.py'])` operation
- **Data Restoration**: Deleted videos reappearing due to sync from stale NAS database

### Sophisticated Categorization
Enhanced metadata applied to 67 YTV2 videos with detailed subcategory classifications:
- **67 Records**: Specific count of videos with advanced categorization
- **Subcategories**: Detailed classification beyond basic categories
- **Manual Curation**: Human-applied categorization requiring preservation
- **Loss Prevention**: Primary goal of migration to prevent categorization disasters

### Dual SQLite Architecture (Current/Legacy)
The problematic current architecture causing sync disasters:
- **NAS SQLite**: Database in `/Volumes/Docker/YTV2/data/ytv2_content.db`
- **Dashboard SQLite**: Database in `/Users/markdarby/projects/YTV2-Dashboard/ytv2_content.db`
- **Sync Scripts**: `sync_sqlite_db.py` and `nas_sync.py` causing overwrites
- **Auto-Sync**: Automatic synchronization after video processing

## YTV2 Components

### NAS Component
Docker-based processing component handling video analysis:
- **Location**: `/Volumes/Docker/YTV2/`
- **Functions**: YouTube video processing, AI summarization, content generation
- **Database**: Currently SQLite, migrating to PostgreSQL
- **Sync Role**: Source of "nuclear overwrites" via auto-sync

### Dashboard Component
Render-hosted web interface for content viewing:
- **Location**: `/Users/markdarby/projects/YTV2-Dashboard/`
- **Functions**: Web interface, audio streaming, content display
- **Database**: Currently SQLite (synced from NAS), migrating to PostgreSQL
- **Sync Role**: Victim of overwrites, loses user deletions

### Telegram Bot
Interface component within NAS for user interaction:
- **File**: `server.py` (formerly `telegram_bot.py`)
- **NAS Role**: Actual Telegram bot for user commands
- **Dashboard Role**: Web server (not Telegram bot, confusing naming)
- **Processing**: Triggers auto-sync after video processing completion

## Database Architecture Terms

### Natural Key
The true unique identifier for content in YTV2:
- **video_id**: YouTube video ID (11 characters, alphanumeric)
- **Conflict Resolution**: Use `ON CONFLICT (video_id)` not `ON CONFLICT (id)`
- **Primary Key**: `id` field contains `"yt:<video_id>"` format
- **Migration Strategy**: Conflict on video_id for robust upserts

### Content Table
Main database table storing video metadata:
- **Current Structure**: SQLite table with JSON fields
- **Target Structure**: PostgreSQL table with JSONB fields
- **Key Fields**: video_id, title, channel_name, analysis (JSON), summary
- **Preservation Requirement**: All existing data must migrate without loss

### Content Summaries Table (New)
PostgreSQL table storing renderable summary content:
- **Purpose**: Separate pre-rendered HTML from metadata
- **Structure**: video_id, variant, revision, html, raw_json
- **Query Pattern**: Lateral joins for latest revision lookup
- **Performance**: Eliminates need for materialized views

### Analysis JSON
Complex JSON field containing categorization and metadata:
- **Categories**: Array of category strings
- **Subcategories**: Detailed subcategory information (67 records critical)
- **Key Topics**: Array of topic strings for filtering
- **Content Type**: Tutorial, Review, Discussion classification
- **Migration Risk**: JSON parsing must preserve all nested structures

### Latest-Pointer Pattern
Efficient PostgreSQL technique to track latest summary revisions:
- **Purpose**: Store a direct pointer to the latest revision per variant
- **Structure**: Separate column or table referencing latest content_summaries record
- **Benefit**: Simplifies queries by avoiding repeated lateral joins
- **Use Case**: Improves performance for frequent latest summary retrievals

## Migration-Specific Terms

### Dual-Write Phase
Safe migration period where both databases receive writes:
- **NAS Behavior**: Writes to both SQLite and PostgreSQL
- **Dashboard Behavior**: Reads from SQLite (with PostgreSQL shadow reads)
- **Validation**: Ensures PostgreSQL implementation works correctly
- **Duration**: 1-2 days for thorough validation

### Shadow Reads
Testing PostgreSQL reads while SQLite remains primary:
- **Feature Flag**: `READ_FROM_POSTGRES` environment variable
- **Admin Testing**: PostgreSQL reads for admin users only
- **Comparison**: Validate identical results between databases
- **Safety**: Immediate rollback to SQLite if issues detected

### Nuclear Overwrite
The specific destructive operation causing sync disasters:
- **Code Location**: `subprocess.run(['python', 'sync_sqlite_db.py'])`
- **Trigger**: Automatic execution after video processing
- **Effect**: Complete replacement of Dashboard SQLite with NAS SQLite
- **Elimination**: Primary target for removal in migration

### Lateral Join Pattern
Efficient PostgreSQL query technique for latest revision lookup:
- **Purpose**: Get latest content_summaries revision without materialized views
- **Performance**: Avoids subqueries and trigger complexity
- **Syntax**: `LEFT JOIN LATERAL (SELECT ... ORDER BY revision DESC LIMIT 1)`
- **Benefit**: Simpler maintenance than materialized view approaches

### Summary Normalization
Process of standardizing summary content storage:
- **Purpose**: Store summaries in normalized form to reduce duplication
- **Implementation**: Separate raw JSON and rendered HTML fields
- **Benefit**: Enables efficient updates and consistent rendering
- **Migration Impact**: Requires transformation of existing summary data

## Safety & Rollback Terms

### Comprehensive Backup
Complete data preservation before destructive operations:
- **SQLite Files**: Timestamped copies of both NAS and Dashboard databases
- **Verification**: Ensure backups are readable and contain expected data
- **67 Record Check**: Verify sophisticated categorization preserved in backup
- **Naming Convention**: Include timestamp for easy identification

### Idempotent Migration
Scripts that can be safely run multiple times:
- **Upsert Operations**: `ON CONFLICT DO UPDATE` for safe reruns
- **State Checking**: Verify current state before making changes
- **Error Recovery**: Graceful handling of partial migration states
- **Testing**: Validate scripts work correctly when run repeatedly

### Feature Flag Cutover
Using environment variables for safe migration phases:
- **READ_FROM_POSTGRES**: Dashboard database source selection
- **DUAL_WRITE_MODE**: NAS dual-write behavior control
- **Immediate Rollback**: Toggle flags for instant reversion
- **Validation**: Test each phase thoroughly before advancing

### Cascade Delete
PostgreSQL foreign key behavior for data consistency:
- **Relationship**: content → content_summaries
- **Behavior**: Deleting content automatically removes related summaries
- **Safety**: Prevents orphaned summary records
- **Testing**: Verify delete operations clean up all related data

### SQLite Write Guard
Safety mechanism to prevent unsafe SQLite writes during migration:
- **Purpose**: Block writes to SQLite when in PostgreSQL-only mode
- **Implementation**: Environment variable or code checks to disable writes
- **Benefit**: Prevents data corruption or loss by accidental writes
- **Use Case**: Ensures safe cutover and rollback scenarios

## Performance Terms

### Query Baseline
Current SQLite performance metrics to maintain:
- **Dashboard Loading**: Sub-second page load times
- **API Response**: <500ms for report endpoints
- **Card Rendering**: Efficient display of video cards
- **Filter Operations**: Real-time filter updates

### JSON GIN Index
PostgreSQL index type for efficient JSON queries:
- **Purpose**: Fast filtering on analysis_json and topics_json fields
- **Syntax**: `CREATE INDEX USING GIN (analysis_json)`
- **Performance**: Enables efficient category and subcategory filtering
- **Migration**: Required for maintaining current filter performance

### Updated_at Triggers
Automatic timestamp maintenance for data freshness:
- **Purpose**: Track when records were last modified
- **Implementation**: PostgreSQL trigger function
- **Maintenance**: Automatic updates on any record change
- **Monitoring**: Helps track migration progress and data freshness

## Quality Assurance Terms

### Data Integrity Verification
Systematic checking of migration completeness:
- **Record Counts**: Total records match source database
- **JSON Validation**: Complex fields properly formatted
- **Foreign Keys**: All relationships properly established
- **Spot Checking**: Manual verification of sample records

### Acceptance Criteria
Specific, measurable requirements for task completion:
- **Format**: Concrete, testable statements
- **Coverage**: Technical implementation, testing, git workflow
- **Validation**: Each criterion must be explicitly verified
- **Traceability**: Link to task IDs (T-YXXX format)

### Rollback Capability
Ability to safely revert to previous state:
- **SQLite Restoration**: Return to dual SQLite architecture
- **Feature Flags**: Immediate environment variable changes
- **Backup Recovery**: Restore from comprehensive backups
- **Testing**: Validate rollback procedures work correctly

### DB Health Endpoint
Diagnostic API endpoint exposing database health metrics:
- **Purpose**: Monitor PostgreSQL availability and responsiveness
- **Implementation**: HTTP endpoint returning status and stats
- **Use Case**: Enables proactive detection of database issues
- **Integration**: Used by monitoring and alerting systems

## Implementation Terms

### Database Manager
New abstraction layer for database operations:
- **Location**: `/Volumes/Docker/YTV2/modules/database_manager.py`
- **Purpose**: Support both SQLite and PostgreSQL during migration
- **Features**: Transactional writes, dual-write mode, error handling
- **Safety**: Atomic operations preventing partial data corruption

### Environment Variables
Configuration settings controlling migration behavior:
- **DATABASE_URL**: PostgreSQL connection string
- **READ_FROM_POSTGRES**: Dashboard database source control
- **DUAL_WRITE_MODE**: NAS dual-write behavior flag
- **Security**: No plaintext credentials in code

### Task IDs
Systematic numbering for implementation traceability:
- **Format**: T-YXXX (Y for YTV2, XXX for sequential number)
- **Usage**: Git commit messages, task tracking, documentation
- **Benefits**: Clear implementation history, easy reference
- **Example**: T-Y001, T-Y025, etc.

---

*This glossary ensures consistent terminology across all YTV2 PostgreSQL migration documentation and implementation.*
