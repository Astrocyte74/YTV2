#!/usr/bin/env python3
"""
Build pgvector Embedding Index from PostgreSQL

Generates OpenAI embeddings for content rows that don't have one yet.
Resumable — can be run multiple times; only embeds rows where
embedding IS NULL.

Usage:
    python -m modules.build_semantic_index [--batch-size 50]

Run inside Docker container:
    docker exec -e OPENAI_API_KEY=$OPENAI_API_KEY ytv2-dashboard python -m modules.build_semantic_index
"""

import os
import sys
import logging
import argparse
import time
from pathlib import Path
from typing import List, Dict, Any

# Setup path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

logger = logging.getLogger(__name__)

BATCH_SIZE_DEFAULT = 50
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 5


def get_postgres_content() -> List[Dict[str, Any]]:
    """Fetch content rows that need embeddings, with their best summary text."""
    try:
        import psycopg2
        import psycopg2.extras
    except ImportError:
        logger.error("psycopg2 not installed")
        return []

    postgres_url = os.getenv('DATABASE_URL_POSTGRES_NEW')
    if not postgres_url:
        logger.error("DATABASE_URL_POSTGRES_NEW not set")
        return []

    try:
        conn = psycopg2.connect(postgres_url)
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # Source normalization matching the dashboard's logic
        source_case = """CASE
            WHEN LOWER(COALESCE(c.canonical_url::text, '')) LIKE '%%wikipedia.org%%' THEN 'wikipedia'
            WHEN LOWER(COALESCE(c.canonical_url::text, '')) LIKE '%%churchofjesuschrist.org%%'
                OR LOWER(COALESCE(c.canonical_url::text, '')) LIKE '%%lds.org%%' THEN 'lds'
            WHEN LOWER(COALESCE(c.canonical_url::text, '')) LIKE '%%youtube.com%%'
                OR LOWER(COALESCE(c.canonical_url::text, '')) LIKE '%%youtu.be%%' THEN 'youtube'
            WHEN LOWER(COALESCE(c.canonical_url::text, '')) LIKE '%%reddit.com%%'
                OR LOWER(COALESCE(c.video_id::text, '')) LIKE 'reddit:%%' THEN 'reddit'
            WHEN LOWER(COALESCE(c.id::text, '')) LIKE '%%-web-%%' THEN 'web'
            ELSE 'web'
        END"""

        query = f"""
            SELECT
                c.video_id,
                c.title,
                c.channel_name,
                {source_case} AS normalized_source,
                COALESCE(cs.text, ls.text) AS summary_text
            FROM content c
            LEFT JOIN LATERAL (
                SELECT cs.text
                FROM content_summaries cs
                WHERE cs.video_id = c.video_id
                  AND cs.is_latest = true
                  AND cs.text IS NOT NULL
                ORDER BY array_position(
                  ARRAY[
                    'comprehensive', 'key-insights', 'bullet-points',
                    'key-points', 'executive', 'audio',
                    'reddit-discussion', 'audio-fr'
                  ]::text[],
                  cs.variant
                )
                LIMIT 1
            ) cs ON true
            LEFT JOIN LATERAL (
                SELECT s.text
                FROM v_latest_summaries s
                WHERE s.video_id = c.video_id
                  AND s.text IS NOT NULL
                ORDER BY s.created_at DESC
                LIMIT 1
            ) ls ON true
            WHERE c.embedding IS NULL
              AND COALESCE(cs.text, ls.text) IS NOT NULL
              AND LENGTH(TRIM(COALESCE(cs.text, ls.text))) > 10
            ORDER BY c.indexed_at DESC NULLS LAST
        """

        cur.execute(query)
        rows = cur.fetchall()
        conn.close()

        logger.info(f"Found {len(rows)} content items needing embeddings")
        return rows

    except Exception as e:
        logger.error(f"Failed to fetch content: {e}")
        return []


def build_index(batch_size: int = BATCH_SIZE_DEFAULT):
    """
    Generate embeddings for all content rows that need them.

    Resumable: only processes rows where embedding IS NULL.
    Token-budgeted: uses modest batch sizes to stay under OpenAI limits.
    """
    from modules.semantic_search import (
        _build_canonical_text,
        _compute_source_hash,
        _generate_embeddings_batch,
        EMBEDDING_MODEL,
        EMBEDDING_VERSION,
    )

    # Verify OpenAI key is set
    if not os.getenv('OPENAI_API_KEY'):
        logger.error("OPENAI_API_KEY not set — cannot generate embeddings")
        return False

    # Fetch rows needing embeddings
    content_items = get_postgres_content()
    if not content_items:
        logger.info("No content items need embeddings — all caught up!")
        return True

    # Connect to PG for updates
    import psycopg2

    postgres_url = os.getenv('DATABASE_URL_POSTGRES_NEW')
    if not postgres_url:
        logger.error("DATABASE_URL_POSTGRES_NEW not set")
        return False

    total_embedded = 0
    total_failed = 0

    for batch_start in range(0, len(content_items), batch_size):
        batch = content_items[batch_start:batch_start + batch_size]

        # Build canonical texts
        texts = []
        for row in batch:
            canonical = _build_canonical_text(
                title=row.get('title', ''),
                summary=row.get('summary_text', ''),
                channel=row.get('channel_name', ''),
                source=row.get('normalized_source', 'web'),
            )
            texts.append(canonical)

        # Generate embeddings with retries
        embeddings = None
        for attempt in range(MAX_RETRIES):
            try:
                embeddings = _generate_embeddings_batch(texts)
                break
            except Exception as e:
                logger.warning(f"Batch embedding attempt {attempt + 1} failed: {e}")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY_SECONDS * (attempt + 1))

        if embeddings is None:
            logger.error(f"Failed to generate embeddings for batch starting at {batch_start}")
            total_failed += len(batch)
            continue

        # Write embeddings to PostgreSQL
        conn = psycopg2.connect(postgres_url)
        try:
            cur = conn.cursor()
            batch_success = 0

            for i, (row, embedding) in enumerate(zip(batch, embeddings)):
                if embedding is None:
                    logger.warning(f"No embedding generated for {row['video_id']}")
                    total_failed += 1
                    continue

                source_hash = _compute_source_hash(texts[i])

                try:
                    cur.execute("""
                        UPDATE content
                        SET embedding = %s::vector,
                            embedding_model = %s,
                            embedding_version = %s,
                            embedding_source_hash = %s,
                            embedding_updated_at = NOW()
                        WHERE video_id = %s
                    """, [
                        str(embedding),
                        EMBEDDING_MODEL,
                        EMBEDDING_VERSION,
                        source_hash,
                        row['video_id'],
                    ])
                    batch_success += 1
                except Exception as e:
                    logger.error(f"Failed to update {row['video_id']}: {e}")
                    total_failed += 1

            conn.commit()
            total_embedded += batch_success
            logger.info(
                f"Batch {batch_start // batch_size + 1}: "
                f"{batch_success}/{len(batch)} embedded "
                f"(total: {total_embedded}/{len(content_items)})"
            )

        except Exception as e:
            conn.rollback()
            logger.error(f"Batch commit failed: {e}")
            total_failed += len(batch)
        finally:
            conn.close()

    logger.info(f"Backfill complete: {total_embedded} embedded, {total_failed} failed")
    return total_failed == 0


def verify_index():
    """Verify the index was built correctly."""
    try:
        import psycopg2
    except ImportError:
        logger.error("psycopg2 not installed")
        return False

    postgres_url = os.getenv('DATABASE_URL_POSTGRES_NEW')
    if not postgres_url:
        logger.error("DATABASE_URL_POSTGRES_NEW not set")
        return False

    try:
        conn = psycopg2.connect(postgres_url)
        cur = conn.cursor()

        cur.execute("SELECT COUNT(*) FROM content")
        total = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM content WHERE embedding IS NOT NULL")
        embedded = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM content WHERE embedding IS NULL")
        missing = cur.fetchone()[0]

        logger.info(f"Content rows: {total} total, {embedded} with embeddings, {missing} without")

        if missing > 0:
            # Check how many missing have summary text
            cur.execute("""
                SELECT COUNT(*) FROM content c
                LEFT JOIN LATERAL (
                    SELECT 1 FROM v_latest_summaries s
                    WHERE s.video_id = c.video_id
                      AND s.text IS NOT NULL
                    LIMIT 1
                ) ls ON true
                WHERE c.embedding IS NULL AND ls IS NOT NULL
            """)
            missing_with_summary = cur.fetchone()[0]
            logger.info(f"  {missing_with_summary} missing rows have summary text (can be embedded)")
            logger.info(f"  {missing - missing_with_summary} missing rows have no summary text")

        conn.close()
        return embedded > 0

    except Exception as e:
        logger.error(f"Failed to verify index: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description='Build pgvector embedding index from PostgreSQL')
    parser.add_argument('--batch-size', type=int, default=BATCH_SIZE_DEFAULT,
                        help='Rows per embedding API batch (default: 50)')
    parser.add_argument('--verify-only', action='store_true',
                        help='Only verify existing index')
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    if args.verify_only:
        success = verify_index()
        sys.exit(0 if success else 1)

    logger.info("Building pgvector embedding index...")

    success = build_index(batch_size=args.batch_size)

    if success:
        verify_index()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
