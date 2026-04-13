"""
Semantic Search Module for YTV2 Dashboard

Uses pgvector + OpenAI embeddings for semantic similarity search
across content summaries. Replaces the previous ChromaDB implementation.

Embeddings live in the same PostgreSQL `content` table — no separate
vector store, no sync drift, no rebuild mechanism needed.
"""

import os
import hashlib
import logging
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

# Configuration from environment
EMBEDDING_MODEL = os.getenv('EMBEDDING_MODEL', 'text-embedding-3-large')
EMBEDDING_VERSION = os.getenv('EMBEDDING_VERSION', 'v1')
EMBEDDING_DIM = 3072  # text-embedding-3-large dimension

# Lazy-loaded OpenAI client
_openai_client = None


def _get_openai_client():
    """Get or create OpenAI client (lazy loading)."""
    global _openai_client

    if _openai_client is not None:
        return _openai_client

    try:
        from openai import OpenAI
    except ImportError:
        logger.error("openai not installed. Run: pip install openai")
        return None

    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        logger.warning("OPENAI_API_KEY not set — semantic search unavailable")
        return None

    _openai_client = OpenAI(api_key=api_key)
    return _openai_client


def _get_pg_connection():
    """Get a PostgreSQL connection using the dashboard's DATABASE_URL."""
    try:
        import psycopg2
    except ImportError:
        logger.error("psycopg2 not available")
        return None

    postgres_url = os.getenv('DATABASE_URL_POSTGRES_NEW')
    if not postgres_url:
        logger.error("DATABASE_URL_POSTGRES_NEW not set")
        return None

    try:
        conn = psycopg2.connect(postgres_url)
        return conn
    except Exception as e:
        logger.error(f"Failed to connect to PostgreSQL: {e}")
        return None


def _build_canonical_text(title: str, summary: str,
                          channel: str = "", source: str = "") -> str:
    """Build canonical embedding input string.

    Same structure used for backfill and incremental upsert.
    Keep labels stable — changes here require re-embedding.
    """
    parts = []
    if title:
        parts.append(f"Title: {title}")
    if channel:
        parts.append(f"Channel: {channel}")
    if source:
        parts.append(f"Source: {source}")
    if summary:
        parts.append(f"Summary:\n{summary}")

    return "\n\n".join(parts)


def _compute_source_hash(text: str) -> str:
    """SHA-256 hash of canonical text for staleness detection."""
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def _generate_embedding(text: str) -> Optional[List[float]]:
    """Generate a single embedding via OpenAI API."""
    client = _get_openai_client()
    if client is None:
        return None

    try:
        response = client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=text,
        )
        return response.data[0].embedding
    except Exception as e:
        logger.error(f"Failed to generate embedding: {e}")
        return None


def _generate_embeddings_batch(texts: List[str]) -> List[Optional[List[float]]]:
    """Generate embeddings for a batch of texts via OpenAI API.

    Token-budgeted: callers should batch 25-50 texts to stay under
    OpenAI's 300K token/request limit.
    """
    client = _get_openai_client()
    if client is None:
        return [None] * len(texts)

    try:
        response = client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=texts,
        )
        # Results come back in same order as input
        indexed = {d.index: d.embedding for d in response.data}
        return [indexed.get(i) for i in range(len(texts))]
    except Exception as e:
        logger.error(f"Failed to generate batch embeddings: {e}")
        return [None] * len(texts)


def _source_case_sql(alias: str = 'c') -> str:
    """SQL CASE expression for source normalization.

    Matches the logic in PostgreSQLContentIndex._source_case_expression()
    so semantic search returns the same source values as the dashboard UI.
    """
    canonical = f"LOWER(COALESCE({alias}.canonical_url::text, ''))"
    video_id = f"LOWER(COALESCE({alias}.video_id::text, ''))"
    record_id = f"LOWER(COALESCE({alias}.id::text, ''))"

    return f"""CASE
        WHEN {canonical} LIKE '%%wikipedia.org%%' THEN 'wikipedia'
        WHEN {canonical} LIKE '%%churchofjesuschrist.org%%'
            OR {canonical} LIKE '%%lds.org%%' THEN 'lds'
        WHEN {canonical} LIKE '%%youtube.com%%'
            OR {canonical} LIKE '%%youtu.be%%' THEN 'youtube'
        WHEN {canonical} LIKE '%%reddit.com%%'
            OR {video_id} LIKE 'reddit:%%' THEN 'reddit'
        WHEN {record_id} LIKE '%%-web-%%' THEN 'web'
        ELSE 'web'
    END"""


def is_available() -> bool:
    """Check if semantic search is available (pgvector + OpenAI key)."""
    if not os.getenv('OPENAI_API_KEY'):
        return False

    conn = _get_pg_connection()
    if conn is None:
        return False

    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT COUNT(*) FROM content
            WHERE embedding IS NOT NULL
        """)
        count = cur.fetchone()[0]
        return count > 0
    except Exception as e:
        logger.error(f"Semantic search availability check failed: {e}")
        return False
    finally:
        conn.close()


def get_indexed_count() -> int:
    """Get the number of content rows with embeddings."""
    conn = _get_pg_connection()
    if conn is None:
        return 0

    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM content WHERE embedding IS NOT NULL")
        return cur.fetchone()[0]
    except Exception as e:
        logger.error(f"Failed to get indexed count: {e}")
        return 0
    finally:
        conn.close()


def search(
    query: str,
    topk: int = 20,
    filters: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """
    Perform semantic search using pgvector cosine similarity.

    Args:
        query: The search query text
        topk: Maximum number of results to return
        filters: Optional metadata filters (e.g., {"source": "youtube"})

    Returns:
        List of search results with id, score, title, source, channel, snippet
    """
    if not query or not query.strip():
        return []

    # Generate query embedding
    query_embedding = _generate_embedding(query.strip())
    if query_embedding is None:
        logger.warning("Semantic search unavailable — could not generate query embedding")
        return []

    conn = _get_pg_connection()
    if conn is None:
        return []

    try:
        import psycopg2.extras
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        source_case = _source_case_sql('c')

        # Build WHERE conditions
        where_clauses = ["c.embedding IS NOT NULL"]
        params: list = [str(query_embedding)]

        if filters:
            if filters.get('source'):
                if filters['source'] == 'youtube':
                    where_clauses.append(
                        "(c.canonical_url ILIKE '%%youtube%%' OR c.canonical_url ILIKE '%%youtu.be%%')"
                    )
                elif filters['source'] == 'reddit':
                    where_clauses.append("c.canonical_url ILIKE '%%reddit%%'")
                elif filters['source'] == 'wikipedia':
                    where_clauses.append("c.canonical_url ILIKE '%%wikipedia%%'")
                else:
                    where_clauses.append(f"{source_case} = %s")
                    params.append(filters['source'])

            if filters.get('channel'):
                where_clauses.append("c.channel_name = %s")
                params.append(filters['channel'])

        where_sql = " AND ".join(where_clauses)
        params.append(topk)

        sql = f"""
            SELECT
                c.video_id,
                c.title,
                c.channel_name,
                {source_case} AS normalized_source,
                1 - (c.embedding <=> %s::vector) AS score,
                ls.text AS summary_text
            FROM content c
            LEFT JOIN LATERAL (
                SELECT s.text
                FROM v_latest_summaries s
                WHERE s.video_id = c.video_id
                  AND s.variant IN ('key-insights', 'comprehensive', 'bullet-points')
                ORDER BY array_position(
                    ARRAY['key-insights', 'comprehensive', 'bullet-points']::text[],
                    s.variant
                )
                LIMIT 1
            ) ls ON true
            WHERE {where_sql}
            ORDER BY c.embedding <=> %s::vector
            LIMIT %s
        """

        # Need the embedding vector twice (WHERE distance + ORDER BY)
        # Insert it again after the first %s placeholder for ORDER BY
        params_with_embedding = [str(query_embedding)] + params[1:]

        cur.execute(sql, params_with_embedding)
        rows = cur.fetchall()

        formatted_results = []
        for row in rows:
            snippet = ""
            if row.get('summary_text'):
                text = row['summary_text']
                snippet = text[:300] + "..." if len(text) > 300 else text

            formatted_results.append({
                "id": row['video_id'],
                "score": round(float(row['score']), 4),
                "title": row.get('title', '') or "",
                "source": row.get('normalized_source', '') or "",
                "channel": row.get('channel_name', '') or "",
                "snippet": snippet,
            })

        logger.info(f"Semantic search for '{query}' returned {len(formatted_results)} results")
        return formatted_results

    except Exception as e:
        logger.exception(f"Semantic search error: {e}")
        return []
    finally:
        conn.close()


def find_similar(content_id: str, topk: int = 5) -> List[Dict[str, Any]]:
    """
    Find content similar to a specific document by ID.

    Uses the target document's stored embedding to find nearest neighbors.

    Args:
        content_id: The video_id of the document to find similar content for
        topk: Maximum number of similar items to return

    Returns:
        List of similar items with id, score, title, source, channel
    """
    conn = _get_pg_connection()
    if conn is None:
        return []

    try:
        import psycopg2.extras
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        source_case = _source_case_sql('c')

        # Use subquery to get the source embedding and search in one query
        sql = f"""
            SELECT
                c.video_id,
                c.title,
                c.channel_name,
                {source_case} AS normalized_source,
                1 - (c.embedding <=> (
                    SELECT embedding FROM content WHERE video_id = %s
                )) AS score
            FROM content c
            WHERE c.embedding IS NOT NULL
              AND c.video_id != %s
              AND (SELECT embedding FROM content WHERE video_id = %s) IS NOT NULL
            ORDER BY c.embedding <=> (
                SELECT embedding FROM content WHERE video_id = %s
            )
            LIMIT %s
        """

        cur.execute(sql, [content_id, content_id, content_id, content_id, topk])
        rows = cur.fetchall()

        formatted_results = []
        for row in rows:
            formatted_results.append({
                "id": row['video_id'],
                "score": round(float(row['score']), 4),
                "title": row.get('title', '') or "",
                "source": row.get('normalized_source', '') or "",
                "channel": row.get('channel_name', '') or "",
            })

        return formatted_results

    except Exception as e:
        logger.exception(f"Find similar error: {e}")
        return []
    finally:
        conn.close()


def upsert_document(
    video_id: str,
    title: str,
    summary: str,
    channel: str = "",
    source: str = "unknown",
    variant: str = ""
) -> bool:
    """
    Generate and store an embedding for a content row.

    Called incrementally when new content is ingested via /api/ingest.

    Args:
        video_id: Unique identifier for the content
        title: Content title
        summary: Summary text to be embedded
        channel: Channel or author name
        source: Content source (youtube, reddit, web, etc.)
        variant: Summary variant type (unused, kept for API compat)

    Returns:
        True if successful, False otherwise
    """
    if not video_id or not summary:
        logger.warning("upsert_document called with missing video_id or summary")
        return False

    # Build canonical text and check if re-embedding is needed
    canonical_text = _build_canonical_text(title, summary, channel, source)
    source_hash = _compute_source_hash(canonical_text)

    # Check if embedding is already up to date
    conn = _get_pg_connection()
    if conn is None:
        return False

    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT embedding_source_hash FROM content WHERE video_id = %s",
            [video_id]
        )
        row = cur.fetchone()
        if row and row[0] == source_hash:
            logger.debug(f"Embedding for {video_id} is up to date (hash match)")
            return True

        # Generate new embedding
        embedding = _generate_embedding(canonical_text)
        if embedding is None:
            logger.warning(f"Failed to generate embedding for {video_id}")
            return False

        # Update the content row
        cur.execute("""
            UPDATE content
            SET embedding = %s::vector,
                embedding_model = %s,
                embedding_version = %s,
                embedding_source_hash = %s,
                embedding_updated_at = NOW()
            WHERE video_id = %s
        """, [str(embedding), EMBEDDING_MODEL, EMBEDDING_VERSION,
              source_hash, video_id])

        conn.commit()
        logger.info(f"Upserted embedding for {video_id}")
        return True

    except Exception as e:
        conn.rollback()
        logger.exception(f"Failed to upsert embedding for {video_id}: {e}")
        return False
    finally:
        conn.close()


def delete_document(video_id: str) -> bool:
    """
    No-op: deleting the content row automatically removes the embedding.

    Kept for API compatibility with server.py delete hook.

    Args:
        video_id: Unique identifier for the content to remove

    Returns:
        True (always — the row deletion handles cleanup)
    """
    logger.debug(f"delete_document called for {video_id} — no-op (row deletion handles it)")
    return True


# =============================================================================
# HYBRID SEARCH - Combines Semantic + Keyword using Reciprocal Rank Fusion
# =============================================================================

def keyword_search(
    query: str,
    topk: int = 20,
    filters: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """
    Perform keyword search using PostgreSQL ILIKE pattern matching.

    Finds exact word matches in titles and summaries.

    Args:
        query: The search query text
        topk: Maximum number of results to return
        filters: Optional filters (source, channel)

    Returns:
        List of search results with id, score, title, source, channel
    """
    if not query or not query.strip():
        return []

    try:
        import psycopg2
        import psycopg2.extras
    except ImportError:
        logger.error("psycopg2 not available for keyword search")
        return []

    postgres_url = os.getenv('DATABASE_URL_POSTGRES_NEW')
    if not postgres_url:
        logger.error("DATABASE_URL_POSTGRES_NEW not set for keyword search")
        return []

    try:
        conn = psycopg2.connect(postgres_url)
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        source_case = _source_case_sql('c')
        search_term = f"%{query.strip()}%"

        sql = f"""
            SELECT DISTINCT c.video_id, c.title, c.channel_name,
                   {source_case} AS normalized_source,
                   ls.text as summary_text
            FROM content c
            LEFT JOIN LATERAL (
                SELECT s.text
                FROM v_latest_summaries s
                WHERE s.video_id = c.video_id
                  AND s.variant IN ('key-insights', 'comprehensive', 'bullet-points')
                ORDER BY array_position(
                    ARRAY['key-insights', 'comprehensive', 'bullet-points']::text[],
                    s.variant
                )
                LIMIT 1
            ) ls ON true
            WHERE (c.title ILIKE %s OR ls.text ILIKE %s)
        """

        params = [search_term, search_term]

        # Add filter conditions
        if filters:
            if filters.get('source'):
                if filters['source'] == 'youtube':
                    sql += " AND (c.canonical_url ILIKE '%%youtube%%' OR c.canonical_url ILIKE '%%youtu.be%%')"
                elif filters['source'] == 'reddit':
                    sql += " AND c.canonical_url ILIKE '%%reddit%%'"
                elif filters['source'] == 'wikipedia':
                    sql += " AND c.canonical_url ILIKE '%%wikipedia%%'"

            if filters.get('channel'):
                sql += " AND c.channel_name = %s"
                params.append(filters['channel'])

        sql += " ORDER BY c.indexed_at DESC NULLS LAST LIMIT %s"
        params.append(topk)

        cur.execute(sql, params)
        rows = cur.fetchall()

        results = []
        for rank, row in enumerate(rows, 1):
            # Score based on rank (higher rank = lower score)
            score = 1.0 / (rank + 1)
            results.append({
                "id": row['video_id'],
                "score": round(score, 4),
                "title": row['title'] or "",
                "source": row['normalized_source'] or "",
                "channel": row['channel_name'] or "",
                "snippet": (row['summary_text'] or "")[:300] + "..." if row.get('summary_text') else "",
            })

        conn.close()
        logger.info(f"Keyword search for '{query}' returned {len(results)} results")
        return results

    except Exception as e:
        logger.exception(f"Keyword search error: {e}")
        return []


def reciprocal_rank_fusion(
    semantic_results: List[Dict[str, Any]],
    keyword_results: List[Dict[str, Any]],
    k: int = 60,
    semantic_weight: float = 0.6,
    keyword_weight: float = 0.4
) -> List[Dict[str, Any]]:
    """
    Combine semantic and keyword results using Reciprocal Rank Fusion (RRF).

    RRF formula: score = weight / (k + rank)

    Args:
        semantic_results: Results from semantic search
        keyword_results: Results from keyword search
        k: RRF constant (default 60, common in literature)
        semantic_weight: Weight for semantic results (default 0.6)
        keyword_weight: Weight for keyword results (default 0.4)

    Returns:
        Merged and ranked results
    """
    # Accumulate RRF scores per document
    rrf_scores: Dict[str, float] = {}
    doc_data: Dict[str, Dict[str, Any]] = {}  # Store full doc data

    # Process semantic results
    for rank, result in enumerate(semantic_results, 1):
        doc_id = result['id']
        rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + (semantic_weight / (k + rank))
        if doc_id not in doc_data:
            doc_data[doc_id] = result

    # Process keyword results
    for rank, result in enumerate(keyword_results, 1):
        doc_id = result['id']
        rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + (keyword_weight / (k + rank))
        if doc_id not in doc_data:
            doc_data[doc_id] = result

    # Sort by RRF score
    sorted_ids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)

    # Build final results with combined scores
    merged = []
    for doc_id in sorted_ids:
        doc = doc_data[doc_id].copy()
        doc['rrf_score'] = round(rrf_scores[doc_id], 4)
        doc['search_type'] = 'hybrid'
        merged.append(doc)

    logger.info(f"RRF merged {len(semantic_results)} semantic + {len(keyword_results)} keyword = {len(merged)} unique results")
    return merged


def hybrid_search(
    query: str,
    topk: int = 20,
    filters: Optional[Dict[str, Any]] = None,
    semantic_weight: float = 0.6,
    keyword_weight: float = 0.4
) -> List[Dict[str, Any]]:
    """
    Perform hybrid search combining semantic and keyword search using RRF.

    This gives the best of both worlds:
    - Semantic: finds conceptually similar content
    - Keyword: finds exact word matches

    Args:
        query: The search query text
        topk: Maximum number of results to return
        filters: Optional metadata filters
        semantic_weight: Weight for semantic results (default 0.6)
        keyword_weight: Weight for keyword results (default 0.4)

    Returns:
        List of search results ranked by RRF score
    """
    # Get results from both methods (get more than topk for better fusion)
    fetch_count = min(topk * 2, 100)

    semantic_results = search(query, topk=fetch_count, filters=filters)
    keyword_results = keyword_search(query, topk=fetch_count, filters=filters)

    # Merge using RRF
    merged = reciprocal_rank_fusion(
        semantic_results,
        keyword_results,
        semantic_weight=semantic_weight,
        keyword_weight=keyword_weight
    )

    # Return top k
    return merged[:topk]


# For testing
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print(f"Embedding model: {EMBEDDING_MODEL}")
    print(f"Available: {is_available()}")
    print(f"Indexed count: {get_indexed_count()}")

    if is_available():
        print("\nTesting search...")
        results = search("AI and machine learning", topk=3)
        for r in results:
            print(f"  [{r['score']}] {r['title']}")
