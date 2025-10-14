-- Add performance index for summary_type filtering
-- This migration adds a btree index on summary_type_latest for fast filtering

BEGIN;

-- Index for summary_type filtering performance
CREATE INDEX IF NOT EXISTS idx_content_summary_type_latest
  ON content (summary_type_latest);

COMMIT;