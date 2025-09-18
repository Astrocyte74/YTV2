-- == Core schema for YTV2 Postgres (Parallel System) ==
-- Assumes extensions installed: pgcrypto, uuid-ossp, pg_trgm, pg_stat_statements, vector

BEGIN;

-- ---------- Utility: updated_at auto-stamp ----------
CREATE OR REPLACE FUNCTION touch_updated_at()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  NEW.updated_at := NOW();
  RETURN NEW;
END$$;

-- ---------- content (primary catalog) ----------
CREATE TABLE IF NOT EXISTS public.content (
  -- Natural key
  video_id           TEXT PRIMARY KEY,

  -- Legacy/internal id if you want to keep it around (nullable, unique if present)
  id                 TEXT UNIQUE,

  -- Core metadata (add/remove as needed — TEXT is fine; we can tighten types later)
  title              TEXT,
  channel_name       TEXT,
  published_at       TIMESTAMPTZ,
  duration_seconds   INTEGER,
  thumbnail_url      TEXT,
  canonical_url      TEXT,

  -- JSON payloads
  subcategories_json JSONB,         -- 74 sophisticated categorization records live here
  topics_json        JSONB,         -- "key_topics", etc. (if present)
  analysis_json      JSONB,         -- new analysis field (you mentioned 1 record so far)

  -- Feature flags / perf fields
  has_audio          BOOLEAN DEFAULT FALSE,
  indexed_at         TIMESTAMPTZ,   -- main sort field in dashboard

  -- housekeeping
  created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Keep updated_at fresh
DROP TRIGGER IF EXISTS trg_content_touch_updated ON public.content;
CREATE TRIGGER trg_content_touch_updated
BEFORE UPDATE ON public.content
FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

-- Helpful indexes
CREATE INDEX IF NOT EXISTS idx_content_indexed_at       ON public.content (indexed_at DESC);
CREATE INDEX IF NOT EXISTS idx_content_channel_name     ON public.content (channel_name);
CREATE INDEX IF NOT EXISTS idx_content_has_audio        ON public.content (has_audio);
CREATE INDEX IF NOT EXISTS idx_content_title_trgm       ON public.content USING GIN (title gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_content_subcats_gin      ON public.content USING GIN (subcategories_json);
CREATE INDEX IF NOT EXISTS idx_content_topics_gin       ON public.content USING GIN (topics_json);
CREATE INDEX IF NOT EXISTS idx_content_analysis_gin     ON public.content USING GIN (analysis_json);


-- ---------- content_summaries (multiple revisions / variants per video) ----------
-- We keep all revisions; "is_latest" marks the head per (video_id, variant)
CREATE TABLE IF NOT EXISTS public.content_summaries (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  video_id      TEXT NOT NULL REFERENCES public.content(video_id) ON DELETE CASCADE,

  -- variant examples: 'comprehensive', 'key-points', 'bullet-points', 'executive',
  -- 'key-insights', 'audio', 'audio-fr', 'audio-es', etc.
  variant       TEXT NOT NULL,

  -- source data (normalized plain text) and the rendered HTML the dashboard expects
  text          TEXT,         -- normalized text we select from dict/string payloads
  html          TEXT,         -- prerendered HTML used by the dashboard inline reader

  -- bookkeeping
  revision      INTEGER NOT NULL DEFAULT 1,
  is_latest     BOOLEAN NOT NULL DEFAULT FALSE,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  -- ensure one (video_id, variant, revision) is unique historically
  UNIQUE (video_id, variant, revision)
);

-- updated_at auto-stamp
DROP TRIGGER IF EXISTS trg_summaries_touch_updated ON public.content_summaries;
CREATE TRIGGER trg_summaries_touch_updated
BEFORE UPDATE ON public.content_summaries
FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

-- Fast lookups
CREATE INDEX IF NOT EXISTS idx_summaries_video_variant          ON public.content_summaries (video_id, variant);
CREATE INDEX IF NOT EXISTS idx_summaries_video_variant_latest   ON public.content_summaries (video_id, variant, is_latest DESC, created_at DESC);

-- ---------- "latest pointer" trigger: keep exactly one is_latest = TRUE ----------
CREATE OR REPLACE FUNCTION mark_latest_summary()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  -- When inserting/updating a summary for (video_id, variant), make this row latest
  -- and flip all others to FALSE.
  UPDATE public.content_summaries
     SET is_latest = FALSE, updated_at = NOW()
   WHERE video_id = NEW.video_id
     AND variant  = NEW.variant
     AND id      <> NEW.id;

  NEW.is_latest := TRUE;

  -- Auto-bump revision if not provided: set to (max + 1)
  IF (TG_OP = 'INSERT') AND (NEW.revision IS NULL OR NEW.revision <= 0) THEN
    SELECT COALESCE(MAX(revision), 0) + 1
      INTO NEW.revision
      FROM public.content_summaries
     WHERE video_id = NEW.video_id
       AND variant  = NEW.variant;
  END IF;

  RETURN NEW;
END$$;

DROP TRIGGER IF EXISTS trg_summaries_mark_latest_ins ON public.content_summaries;
CREATE TRIGGER trg_summaries_mark_latest_ins
AFTER INSERT ON public.content_summaries
FOR EACH ROW EXECUTE FUNCTION mark_latest_summary();

DROP TRIGGER IF EXISTS trg_summaries_mark_latest_upd ON public.content_summaries;
CREATE TRIGGER trg_summaries_mark_latest_upd
AFTER UPDATE OF text, html, revision, is_latest ON public.content_summaries
FOR EACH ROW EXECUTE FUNCTION mark_latest_summary();


-- ---------- A clean view for "just give me the latest" ----------
CREATE OR REPLACE VIEW public.v_latest_summaries AS
SELECT DISTINCT ON (cs.video_id, cs.variant)
       cs.*
  FROM public.content_summaries cs
  WHERE cs.is_latest = TRUE
  ORDER BY cs.video_id, cs.variant, cs.created_at DESC, cs.revision DESC;

COMMIT;