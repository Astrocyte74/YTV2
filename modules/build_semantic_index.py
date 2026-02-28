#!/usr/bin/env python3
"""
Build ChromaDB Index from PostgreSQL

Indexes content from the dashboard's PostgreSQL database into ChromaDB
for semantic search. This ensures the semantic search uses the same
data source as the dashboard UI.

Usage:
    python -m modules.build_semantic_index [--batch-size 100]

Run inside Docker container:
    docker exec ytv2-dashboard python -m modules.build_semantic_index
"""

import os
import sys
import logging
import argparse
from pathlib import Path
from typing import List, Dict, Any, Optional

# Setup path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

logger = logging.getLogger(__name__)

# ChromaDB directory - store in dashboard16/data/chromadb/
# In Docker: /app/data/chromadb
# Local dev: dashboard16/data/chromadb
CHROMA_DIR = Path(__file__).parent.parent / "data" / "chromadb"
COLLECTION_NAME = "ytv2_summaries"


def get_chroma_client():
    """Get or create ChromaDB client."""
    try:
        import chromadb
        from chromadb.config import Settings
    except ImportError:
        logger.error("chromadb not installed. Run: pip install chromadb")
        return None

    # Ensure directory exists
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)

    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    return client


def get_postgres_content():
    """Fetch all content with summaries from PostgreSQL."""
    try:
        from postgres_content_index import PostgreSQLContentIndex
    except ImportError:
        from modules.postgres_content_index import PostgreSQLContentIndex

    # Get PostgreSQL URL from environment
    postgres_url = os.getenv('DATABASE_URL_POSTGRES_NEW')
    if not postgres_url:
        logger.error("DATABASE_URL_POSTGRES_NEW not set")
        return []

    index = PostgreSQLContentIndex(postgres_url)
    conn = index._get_connection()

    try:
        source_case = index._source_case_expression('c', conn)

        # Query all content with summaries
        query = f"""
            SELECT
                c.video_id,
                c.title,
                c.channel_name,
                {source_case} AS normalized_source,
                ls.text as summary_text,
                ls.variant as summary_variant
            FROM content c
            LEFT JOIN LATERAL (
                SELECT s.text, s.variant
                FROM v_latest_summaries s
                WHERE s.video_id = c.video_id
                  AND s.variant IN (
                    'comprehensive','key-points','bullet-points',
                    'executive','key-insights','audio','audio-fr','audio-es'
                  )
                ORDER BY array_position(
                  ARRAY[
                    'comprehensive','key-points','bullet-points',
                    'executive','key-insights','audio','audio-fr','audio-es'
                  ]::text[],
                  s.variant
                )
                LIMIT 1
            ) ls ON true
            WHERE ls.text IS NOT NULL
              AND LENGTH(TRIM(ls.text)) > 50
            ORDER BY c.indexed_at DESC
        """

        cur = conn.cursor()
        cur.execute(query)
        rows = cur.fetchall()

        logger.info(f"Fetched {len(rows)} content items with summaries from PostgreSQL")
        return rows

    finally:
        conn.close()


def build_index(batch_size: int = 100, clear_existing: bool = True):
    """
    Build ChromaDB index from PostgreSQL content.

    Args:
        batch_size: Number of documents to index per batch
        clear_existing: If True, delete existing collection before indexing
    """
    client = get_chroma_client()
    if client is None:
        return False

    # Get or create collection
    if clear_existing:
        try:
            client.delete_collection(COLLECTION_NAME)
            logger.info(f"Deleted existing collection: {COLLECTION_NAME}")
        except Exception:
            pass  # Collection may not exist

    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "l2"}
    )

    # Fetch content from PostgreSQL
    content_items = get_postgres_content()
    if not content_items:
        logger.warning("No content found to index")
        return False

    # Prepare batches
    ids = []
    documents = []
    metadatas = []

    for row in content_items:
        video_id = row.get('video_id', '')
        title = row.get('title', '')
        channel = row.get('channel_name', '')
        source = row.get('normalized_source', 'unknown')
        summary = row.get('summary_text', '')

        if not video_id or not summary:
            continue

        # Create document text for embedding (title + summary)
        doc_text = f"{title}\n\n{summary}"

        ids.append(video_id)
        documents.append(doc_text)
        metadatas.append({
            'title': title[:500],  # Truncate for metadata limits
            'channel': channel or '',
            'source': source or 'unknown',
            'variant': row.get('summary_variant', '')
        })

    # Index in batches
    total_indexed = 0
    for i in range(0, len(ids), batch_size):
        batch_ids = ids[i:i + batch_size]
        batch_docs = documents[i:i + batch_size]
        batch_meta = metadatas[i:i + batch_size]

        collection.add(
            ids=batch_ids,
            documents=batch_docs,
            metadatas=batch_meta
        )

        total_indexed += len(batch_ids)
        logger.info(f"Indexed batch {i // batch_size + 1}: {total_indexed}/{len(ids)} documents")

    logger.info(f"Indexing complete: {total_indexed} documents in collection '{COLLECTION_NAME}'")
    logger.info(f"ChromaDB stored at: {CHROMA_DIR}")

    return True


def verify_index():
    """Verify the index was built correctly."""
    client = get_chroma_client()
    if client is None:
        return False

    try:
        collection = client.get_collection(COLLECTION_NAME)
        count = collection.count()
        logger.info(f"Collection '{COLLECTION_NAME}' has {count} documents")

        # Test a simple search
        results = collection.query(
            query_texts=["test search"],
            n_results=3
        )

        if results and results['ids'] and results['ids'][0]:
            logger.info(f"Test search returned {len(results['ids'][0])} results")
            return True
        else:
            logger.warning("Test search returned no results")
            return False

    except Exception as e:
        logger.error(f"Failed to verify index: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description='Build ChromaDB index from PostgreSQL')
    parser.add_argument('--batch-size', type=int, default=100, help='Documents per batch')
    parser.add_argument('--no-clear', action='store_true', help='Keep existing collection')
    parser.add_argument('--verify-only', action='store_true', help='Only verify existing index')
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    if args.verify_only:
        success = verify_index()
        sys.exit(0 if success else 1)

    logger.info(f"Building ChromaDB index at: {CHROMA_DIR}")

    success = build_index(
        batch_size=args.batch_size,
        clear_existing=not args.no_clear
    )

    if success:
        verify_index()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
