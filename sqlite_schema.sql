CREATE TABLE content (
            id TEXT PRIMARY KEY,
            title TEXT,
            canonical_url TEXT,
            thumbnail_url TEXT,
            published_at TEXT,
            indexed_at TEXT,
            duration_seconds INTEGER DEFAULT 0,
            word_count INTEGER DEFAULT 0,
            has_audio BOOLEAN DEFAULT 0,
            audio_duration_seconds INTEGER DEFAULT 0,
            has_transcript BOOLEAN DEFAULT 0,
            transcript_chars INTEGER DEFAULT 0,
            video_id TEXT,
            channel_name TEXT,
            channel_id TEXT,
            view_count INTEGER DEFAULT 0,
            like_count INTEGER DEFAULT 0,
            comment_count INTEGER DEFAULT 0,
            category TEXT,
            content_type TEXT,
            complexity_level TEXT,
            language TEXT DEFAULT 'en',
            key_topics TEXT,
            named_entities TEXT,
            format_source TEXT DEFAULT 'api',
            processing_status TEXT DEFAULT 'completed',
            created_at TEXT,
            updated_at TEXT
        , subcategory TEXT, subcategories_json TEXT, summary TEXT, analysis TEXT);
CREATE TABLE content_summaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content_id TEXT UNIQUE,
            summary_text TEXT,
            summary_type TEXT DEFAULT 'comprehensive',
            created_at TEXT,
            FOREIGN KEY (content_id) REFERENCES content (id)
        );
CREATE TABLE sqlite_sequence(name,seq);
CREATE INDEX idx_content_video_id ON content (video_id);
CREATE INDEX idx_content_indexed_at ON content (indexed_at);
CREATE INDEX idx_summaries_content_id ON content_summaries (content_id);
CREATE TABLE summary_variants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                video_id TEXT NOT NULL,
                variant_type TEXT NOT NULL,
                revision INTEGER DEFAULT 1,
                content TEXT NOT NULL,
                raw_payload TEXT,
                metadata TEXT,
                is_latest BOOLEAN DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT,
                file_size INTEGER,
                word_count INTEGER,
                
                -- Ensure uniqueness per video/variant/revision
                UNIQUE(video_id, variant_type, revision),
                
                -- Check constraints
                CHECK(revision > 0),
                CHECK(is_latest IN (0, 1))
            );
CREATE INDEX idx_video_variant 
            ON summary_variants(video_id, variant_type)
        ;
CREATE INDEX idx_latest 
            ON summary_variants(video_id, is_latest)
        ;
CREATE INDEX idx_created_at 
            ON summary_variants(created_at DESC)
        ;
CREATE TRIGGER update_latest_revision
            AFTER INSERT ON summary_variants
            BEGIN
                -- Unmark old revisions as latest for same video/variant
                UPDATE summary_variants 
                SET is_latest = 0,
                    updated_at = datetime('now')
                WHERE video_id = NEW.video_id 
                  AND variant_type = NEW.variant_type 
                  AND id != NEW.id;
            END;
CREATE TRIGGER update_timestamp
            AFTER UPDATE ON summary_variants
            BEGIN
                UPDATE summary_variants 
                SET updated_at = datetime('now')
                WHERE id = NEW.id;
            END;
