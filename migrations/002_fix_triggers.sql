-- Fix infinite recursion in latest-pointer triggers
-- This addresses the stack overflow issue discovered in smoke testing

BEGIN;

-- ---------- Fixed "latest pointer" trigger: prevent infinite recursion ----------
CREATE OR REPLACE FUNCTION mark_latest_summary()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  -- When inserting/updating a summary for (video_id, variant), make this row latest
  -- and flip all others to FALSE. Use a separate UPDATE to avoid recursion.

  -- Only process if this is actually changing to latest or is a new insert
  IF (TG_OP = 'INSERT') OR (TG_OP = 'UPDATE' AND NEW.is_latest = TRUE AND OLD.is_latest = FALSE) THEN

    -- Set all other rows for this video_id/variant to NOT latest
    UPDATE public.content_summaries
       SET is_latest = FALSE
     WHERE video_id = NEW.video_id
       AND variant  = NEW.variant
       AND id      <> NEW.id
       AND is_latest = TRUE;  -- Only update rows that are currently latest

    -- Set this row to latest
    NEW.is_latest := TRUE;

    -- Auto-bump revision if not provided on INSERT
    IF (TG_OP = 'INSERT') AND (NEW.revision IS NULL OR NEW.revision <= 0) THEN
      SELECT COALESCE(MAX(revision), 0) + 1
        INTO NEW.revision
        FROM public.content_summaries
       WHERE video_id = NEW.video_id
         AND variant  = NEW.variant;
    END IF;

  END IF;

  RETURN NEW;
END$$;

-- Recreate triggers with BEFORE timing to avoid recursion
DROP TRIGGER IF EXISTS trg_summaries_mark_latest_ins ON public.content_summaries;
CREATE TRIGGER trg_summaries_mark_latest_ins
BEFORE INSERT ON public.content_summaries
FOR EACH ROW EXECUTE FUNCTION mark_latest_summary();

DROP TRIGGER IF EXISTS trg_summaries_mark_latest_upd ON public.content_summaries;
CREATE TRIGGER trg_summaries_mark_latest_upd
BEFORE UPDATE ON public.content_summaries
FOR EACH ROW EXECUTE FUNCTION mark_latest_summary();

COMMIT;