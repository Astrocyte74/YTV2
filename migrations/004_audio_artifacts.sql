-- == Audio On-Demand Artifacts ==
-- Stores metadata for generated audio artifacts, separate from summary_variants.

BEGIN;

CREATE TABLE IF NOT EXISTS public.audio_artifacts (
    id                BIGSERIAL PRIMARY KEY,
    video_id          TEXT NOT NULL,
    mode              TEXT NOT NULL,       -- 'audio_current', 'audio_briefing'
    scope             TEXT NOT NULL,       -- 'summary_active', 'ponderings_visible', 'transcript_visible'
    source_hash       TEXT NOT NULL,       -- sha256 of (mode + scope + canonical_source_text)
    status            TEXT NOT NULL DEFAULT 'missing',  -- missing|queued|generating|ready|failed
    audio_url         TEXT,                -- populated when status = ready
    duration_seconds  INTEGER,
    provider          TEXT,                -- e.g. 'openai_tts'
    source_label      TEXT,                -- human label, e.g. 'Key Insights'
    error_message     TEXT,
    metadata          JSONB DEFAULT '{}',
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE(video_id, mode, scope)
);

CREATE INDEX IF NOT EXISTS idx_audio_artifacts_video_id ON audio_artifacts(video_id);
CREATE INDEX IF NOT EXISTS idx_audio_artifacts_source_hash ON audio_artifacts(source_hash);
CREATE INDEX IF NOT EXISTS idx_audio_artifacts_status ON audio_artifacts(status) WHERE status IN ('queued', 'generating');

-- Auto-update updated_at on row change
CREATE TRIGGER trg_audio_artifacts_updated_at
    BEFORE UPDATE ON audio_artifacts
    FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

COMMENT ON TABLE audio_artifacts IS 'On-demand generated audio artifacts, separate from summary_variants';
COMMENT ON COLUMN audio_artifacts.mode IS 'Generation mode: audio_current (single source) or audio_briefing (combined)';
COMMENT ON COLUMN audio_artifacts.source_hash IS 'SHA-256 of mode+scope+canonical text — used for cache validation';

COMMIT;
