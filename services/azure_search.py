"""
Azure AI Search client wrapper.
Handles document indexing, semantic search, Cohere reranking,
and retrieval quality / knowledge-gap detection.
"""
import os
import logging
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

_search_client = None


def get_search_client():
    """Get or create Azure AI Search client (singleton)."""
    global _search_client

    endpoint = os.getenv("AZURE_SEARCH_ENDPOINT")
    api_key = os.getenv("AZURE_SEARCH_API_KEY")

    if not endpoint or not api_key:
        logger.warning("Azure AI Search not configured — using mock mode.")
        return None

    if _search_client is None:
        try:
            from azure.search.documents import SearchClient
            from azure.core.credentials import AzureKeyCredential
            _search_client = SearchClient(
                endpoint=endpoint,
                index_name=os.getenv("AZURE_SEARCH_INDEX_NAME", "atlas-documents"),
                credential=AzureKeyCredential(api_key),
            )
            logger.info("Azure AI Search client initialised.")
        except Exception as e:
            logger.error(f"Failed to init Azure Search: {e}")
            return None

    return _search_client


# ── Indexing ──────────────────────────────────────────────────────────────────

async def index_document_chunks(
    document_id: str,
    title: str,
    chunks: List,  # accepts List[str] (legacy) or List[Dict] (rich chunks)
    metadata: Dict[str, Any],
) -> bool:
    """
    Upload document chunks to Azure AI Search index.
    Accepts both plain-string chunks (legacy) and rich chunk dicts produced
    by smart_chunk_document().  Rich chunks carry section_heading and
    page_number; plain strings fall back to safe defaults.
    """
    client = get_search_client()
    if client is None:
        logger.info(f"Mock index: {len(chunks)} chunks for '{title}'")
        return True

    try:
        documents = []
        for i, chunk in enumerate(chunks):
            if isinstance(chunk, dict):
                content = chunk.get("content", "")
                chunk_index = chunk.get("chunk_index", i)
                section_heading = chunk.get("section_heading", "")
                page_number = chunk.get("page_number", 1)
            else:
                content = chunk
                chunk_index = i
                section_heading = ""
                page_number = 1

            documents.append({
                "id": f"{document_id}_chunk_{chunk_index}",
                "parent_id": document_id,
                "title": title,
                "content": content,
                "chunk_index": chunk_index,
                "section_heading": section_heading,
                "page_number": page_number,
                "department": metadata.get("department", ""),
                "doc_type": metadata.get("doc_type", "document"),
                "tags": metadata.get("tags", []),
                "created_at": metadata.get("created_at", ""),
            })

        result = client.upload_documents(documents=documents)
        succeeded = sum(1 for r in result if r.succeeded)
        logger.info(f"Indexed {succeeded}/{len(documents)} chunks for '{title}'")
        return succeeded == len(documents)

    except Exception as e:
        logger.error(f"Failed to index document '{title}': {e}")
        return False


# ── Legacy chunker (kept for backward compatibility) ──────────────────────────

def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
    """
    Simple word-count-based chunker.
    Retained for backward compatibility; prefer smart_chunk_document() instead.
    """
    words = text.split()
    chunks = []
    start = 0
    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunks.append(" ".join(words[start:end]))
        if end == len(words):
            break
        start += chunk_size - overlap
    return chunks


# ── Cohere Reranking ──────────────────────────────────────────────────────────

def rerank_results(
    query: str,
    results: List[Dict[str, Any]],
    top_n: int = 5,
) -> List[Dict[str, Any]]:
    """
    Reorder search results by true relevance using Cohere Rerank.

    Falls back gracefully to the original order (limited to top_n) when
    COHERE_API_KEY is not set or the API call fails — the pipeline keeps
    working in all environments.
    """
    api_key = os.getenv("COHERE_API_KEY")
    if not api_key or not results:
        return results[:top_n]

    try:
        import cohere
        co = cohere.Client(api_key)

        documents = [r.get("content", r.get("excerpt", "")) for r in results]
        # Filter empty docs to avoid Cohere API errors
        non_empty = [(i, d) for i, d in enumerate(documents) if d.strip()]
        if not non_empty:
            return results[:top_n]

        indices, docs = zip(*non_empty)

        rerank_response = co.rerank(
            query=query,
            documents=list(docs),
            top_n=min(top_n, len(docs)),
            model="rerank-english-v3.0",
        )

        reranked = []
        for hit in rerank_response.results:
            original_index = indices[hit.index]
            result = dict(results[original_index])
            result["rerank_score"] = round(hit.relevance_score, 4)
            reranked.append(result)

        logger.info(f"Cohere rerank: {len(results)} → {len(reranked)} results for query '{query[:60]}'")
        return reranked

    except Exception as e:
        logger.warning(f"Cohere rerank failed (falling back to original order): {e}")
        return results[:top_n]


# ── Retrieval Quality / Knowledge-Gap Detection ───────────────────────────────

def check_retrieval_quality(
    query: str,
    results: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Score whether the retrieved results are actually able to answer the query.

    Returns:
        {
            "confidence": float  — 0.0 (no answer) to 1.0 (high confidence),
            "knowledge_gap": bool — True when confidence < 0.5,
        }

    Approach (corrective-RAG heuristic):
      - No results at all → hard gap (confidence 0.0)
      - Relevance scores available (Azure Search semantic scores):
          score > 1.5  →  good result, weighted high
          score > 0.5  →  decent result
          score ≤ 0.5  →  likely noise
      - Cohere rerank scores (0–1 range) used when present
      - Falls back to counting results when no scores exist (mock mode)
    """
    if not results:
        return {"confidence": 0.0, "knowledge_gap": True}

    # Collect the best available score per result
    scores = []
    for r in results:
        # Try Cohere rerank score first (already normalised 0-1)
        if "rerank_score" in r:
            scores.append(float(r["rerank_score"]))
        # Azure Search semantic score (typically 0-4)
        elif "@search.score" in r:
            raw = float(r["@search.score"])
            scores.append(min(1.0, raw / 3.0))  # normalise to 0-1
        # Pre-formatted mock relevance score
        elif "relevance_score" in r:
            scores.append(float(r["relevance_score"]))

    if not scores:
        # No scoring data (mock mode with results) — assume adequate coverage
        return {"confidence": 0.7, "knowledge_gap": False}

    max_score = max(scores)
    top3_avg = sum(sorted(scores, reverse=True)[:3]) / min(3, len(scores))
    # Weight: 60% best result, 40% top-3 average
    confidence = round(0.6 * max_score + 0.4 * top3_avg, 3)

    return {
        "confidence": confidence,
        "knowledge_gap": confidence < 0.5,
    }
