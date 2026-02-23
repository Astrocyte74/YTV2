"""
Semantic Search Module for YTV2 Dashboard

Integrates ChromaDB vector search with the dashboard for semantic
similarity search across content summaries.
"""

import os
import sys
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

# ChromaDB configuration
# Store index in dashboard16/data/chromadb/ - same data source as dashboard UI
# In Docker container: /app/data/chromadb (volume mounted from dashboard16/data/)
# In local dev: dashboard16/data/chromadb (relative to this module)
CHROMA_DIR = Path(__file__).parent.parent / "data" / "chromadb"
if not CHROMA_DIR.exists():
    # Fallback for Docker container where data is mounted at /app/data
    CHROMA_DIR = Path("/app/data/chromadb")
COLLECTION_NAME = "ytv2_summaries"

# Lazy-loaded client and collection
_chroma_client = None
_collection = None


def _get_chroma_client():
    """Get or create ChromaDB client (lazy loading)."""
    global _chroma_client

    if _chroma_client is not None:
        return _chroma_client

    try:
        import chromadb
        from chromadb.config import Settings
    except ImportError:
        logger.error("chromadb not installed. Run: pip install chromadb")
        return None

    if not CHROMA_DIR.exists():
        logger.warning(f"ChromaDB directory not found: {CHROMA_DIR}")
        return None

    _chroma_client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    return _chroma_client


def _get_collection():
    """Get or create the collection (lazy loading)."""
    global _collection

    if _collection is not None:
        return _collection

    client = _get_chroma_client()
    if client is None:
        return None

    try:
        _collection = client.get_collection(name=COLLECTION_NAME)
        return _collection
    except Exception as e:
        logger.error(f"Failed to get ChromaDB collection: {e}")
        return None


def is_available() -> bool:
    """Check if semantic search is available."""
    return _get_collection() is not None


def get_indexed_count() -> int:
    """Get the number of indexed documents."""
    collection = _get_collection()
    if collection is None:
        return 0
    return collection.count()


def search(
    query: str,
    topk: int = 20,
    filters: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """
    Perform semantic search across indexed summaries.

    Args:
        query: The search query text
        topk: Maximum number of results to return
        filters: Optional metadata filters (e.g., {"source": "youtube"})

    Returns:
        List of search results with id, score, title, source, channel, text
    """
    collection = _get_collection()
    if collection is None:
        logger.warning("Semantic search not available - collection not found")
        return []

    if not query or not query.strip():
        return []

    try:
        # Build where clause for filters
        where = None
        if filters:
            conditions = []
            for key, value in filters.items():
                if value and key in ["source", "channel"]:
                    conditions.append({key: value})
            if conditions:
                if len(conditions) == 1:
                    where = conditions[0]
                else:
                    where = {"$and": conditions}

        # Query ChromaDB
        results = collection.query(
            query_texts=[query],
            n_results=topk,
            where=where,
            include=["documents", "metadatas", "distances"]
        )

        # Format results
        formatted_results = []
        if results and results['ids'] and results['ids'][0]:
            for i, doc_id in enumerate(results['ids'][0]):
                distance = results['distances'][0][i]
                metadata = results['metadatas'][0][i]
                document = results['documents'][0][i]

                # Convert L2 distance to similarity score (0-1 range)
                score = 1 / (1 + distance)

                formatted_results.append({
                    "id": doc_id,
                    "score": round(score, 4),
                    "title": metadata.get("title", ""),
                    "source": metadata.get("source", ""),
                    "channel": metadata.get("channel", ""),
                    "snippet": document[:300] + "..." if len(document) > 300 else document,
                })

        logger.info(f"Semantic search for '{query}' returned {len(formatted_results)} results")
        return formatted_results

    except Exception as e:
        logger.exception(f"Semantic search error: {e}")
        return []


def find_similar(content_id: str, topk: int = 5) -> List[Dict[str, Any]]:
    """
    Find content similar to a specific document by ID.

    Args:
        content_id: The ID of the document to find similar content for
        topk: Maximum number of similar items to return

    Returns:
        List of similar items with id, score, title, source
    """
    collection = _get_collection()
    if collection is None:
        return []

    try:
        # Get the source document
        doc = collection.get(
            ids=[content_id],
            include=["documents", "metadatas"]
        )

        if not doc['ids']:
            logger.warning(f"Document not found: {content_id}")
            return []

        text = doc['documents'][0]

        # Search for similar (get extra to exclude self)
        results = collection.query(
            query_texts=[text],
            n_results=topk + 1,
            include=["metadatas", "distances"]
        )

        # Format results, excluding the source document
        formatted_results = []
        if results and results['ids'] and results['ids'][0]:
            for i, doc_id in enumerate(results['ids'][0]):
                if doc_id == content_id:
                    continue  # Skip self

                distance = results['distances'][0][i]
                metadata = results['metadatas'][0][i]
                score = 1 / (1 + distance)

                formatted_results.append({
                    "id": doc_id,
                    "score": round(score, 4),
                    "title": metadata.get("title", ""),
                    "source": metadata.get("source", ""),
                    "channel": metadata.get("channel", ""),
                })

                if len(formatted_results) >= topk:
                    break

        return formatted_results

    except Exception as e:
        logger.exception(f"Find similar error: {e}")
        return []


def upsert_document(
    video_id: str,
    title: str,
    summary: str,
    channel: str = "",
    source: str = "unknown",
    variant: str = ""
) -> bool:
    """
    Add or update a single document in ChromaDB.

    Called incrementally when new content is ingested via /api/ingest,
    ensuring semantic search stays in sync with PostgreSQL.

    Args:
        video_id: Unique identifier for the content
        title: Content title
        summary: Summary text to be embedded (used for semantic search)
        channel: Channel or author name
        source: Content source (youtube, reddit, web, etc.)
        variant: Summary variant type (key-insights, bullet-points, etc.)

    Returns:
        True if successful, False otherwise
    """
    if not video_id or not summary:
        logger.warning("upsert_document called with missing video_id or summary")
        return False

    # Need to get or create collection (not just get, in case index doesn't exist)
    client = _get_chroma_client()
    if client is None:
        logger.warning("ChromaDB not available for upsert")
        return False

    try:
        # Get or create collection (creates if doesn't exist)
        collection = client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "l2"}
        )

        # Create document text for embedding (title + summary)
        doc_text = f"{title}\n\n{summary}" if title else summary

        # Upsert into collection
        collection.upsert(
            ids=[video_id],
            documents=[doc_text],
            metadatas=[{
                'title': (title or "")[:500],  # Truncate for metadata limits
                'channel': channel or "",
                'source': source or "unknown",
                'variant': variant or ""
            }]
        )

        logger.info(f"Upserted document {video_id} into ChromaDB")
        return True

    except Exception as e:
        logger.exception(f"Failed to upsert document {video_id}: {e}")
        return False


def delete_document(video_id: str) -> bool:
    """
    Remove a document from ChromaDB.

    Should be called when content is deleted from PostgreSQL.

    Args:
        video_id: Unique identifier for the content to remove

    Returns:
        True if successful, False otherwise
    """
    collection = _get_collection()
    if collection is None:
        return False

    try:
        collection.delete(ids=[video_id])
        logger.info(f"Deleted document {video_id} from ChromaDB")
        return True
    except Exception as e:
        logger.exception(f"Failed to delete document {video_id}: {e}")
        return False


# For testing
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print(f"ChromaDB dir: {CHROMA_DIR}")
    print(f"Available: {is_available()}")
    print(f"Indexed count: {get_indexed_count()}")

    if is_available():
        print("\nTesting search...")
        results = search("AI and machine learning", topk=3)
        for r in results:
            print(f"  [{r['score']}] {r['title']}")
