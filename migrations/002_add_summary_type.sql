-- Add Summary Type support for filtering and display
-- This migration adds summary_type columns to support the new Summary Type filter facet

BEGIN;

-- content_summaries: add a normalized summary_type
ALTER TABLE content_summaries
  ADD COLUMN IF NOT EXISTS summary_type text;

-- content: store the type for the "featured/primary" summary shown on cards
ALTER TABLE content
  ADD COLUMN IF NOT EXISTS summary_type_latest text;

-- helpful index for filtering
CREATE INDEX IF NOT EXISTS ix_content_summary_type_latest
  ON content (summary_type_latest);

-- Create index on content_summaries.summary_type for facet counting
CREATE INDEX IF NOT EXISTS ix_summaries_summary_type
  ON content_summaries (summary_type);

-- Optional: Add constraint for known values (can be added later once stabilized)
-- ALTER TABLE content_summaries ADD CONSTRAINT ck_summary_type
--   CHECK (summary_type IN ('comprehensive','bulleted','concise','narrative','kids','technical','qa','keypoints'));

COMMIT;