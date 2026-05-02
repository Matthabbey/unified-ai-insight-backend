"""
Researcher Agent
Finds and retrieves information from indexed MTN enterprise documents.
Includes Cohere reranking and corrective-RAG knowledge-gap detection.
"""
import json
import logging
from typing import Optional, Annotated
from agents._compat import kernel_function, Kernel
from services.azure_search import get_search_client, rerank_results, check_retrieval_quality

logger = logging.getLogger(__name__)

_KNOWLEDGE_GAP_MESSAGE = (
    "Atlas does not have sufficient documents to answer this question confidently. "
    "Consider uploading relevant documents to the knowledge base."
)


class ResearcherAgent:
    """
    The Researcher is Atlas's information retrieval specialist.
    It searches indexed documents, reranks results via Cohere for true
    relevance, and applies corrective-RAG quality checks to detect when
    Atlas simply doesn't have enough information to answer a question.
    """

    @kernel_function(
        description="""Search across all MTN enterprise documents for information
        relevant to a query. Use this to find facts, contracts, reports, policies,
        complaints, maintenance logs, or any written information. Returns top matching
        document excerpts with source citations."""
    )
    async def search_documents(
        self,
        query: Annotated[str, "The search query — what you're looking for"],
        top_k: Annotated[int, "Number of results to return (default 5)"] = 5,
        department: Annotated[Optional[str], "Filter by department name (optional)"] = None,
        doc_type: Annotated[Optional[str], "Filter by document type: contract, report, policy, complaint, maintenance (optional)"] = None,
    ) -> str:
        """
        Hybrid search (keyword + semantic) with Cohere reranking.
        Retrieves top 20 candidates, reranks to top_k, then checks whether
        the results are actually good enough to answer the question.
        """
        try:
            client = get_search_client()
            if client is None:
                return self._mock_search(query)

            filters = []
            if department:
                filters.append(f"department eq '{department}'")
            if doc_type:
                filters.append(f"doc_type eq '{doc_type}'")
            filter_str = " and ".join(filters) if filters else None

            # Retrieve a larger candidate set for reranking
            raw = list(client.search(
                search_text=query,
                top=20,
                filter=filter_str,
                query_type="semantic",
                semantic_configuration_name="default",
                select=[
                    "id", "title", "department", "doc_type",
                    "content", "created_at", "tags",
                    "section_heading", "page_number",
                ],
            ))

            # ── Corrective RAG: check quality BEFORE reranking ────────────
            quality = check_retrieval_quality(query, raw)
            if quality["knowledge_gap"]:
                logger.warning(
                    f"Knowledge gap detected for query '{query[:80]}' "
                    f"(confidence={quality['confidence']})"
                )
                await self._log_knowledge_gap(query, quality["confidence"], department)
                return json.dumps({
                    "results": [],
                    "knowledge_gap": True,
                    "confidence": quality["confidence"],
                    "message": _KNOWLEDGE_GAP_MESSAGE,
                })

            # ── Rerank top 20 → top_k ─────────────────────────────────────
            reranked = rerank_results(query, raw, top_n=top_k)

            formatted = []
            for r in reranked:
                formatted.append({
                    "document_id": r.get("id"),
                    "title": r.get("title", "Untitled"),
                    "department": r.get("department", "Unknown"),
                    "doc_type": r.get("doc_type", "document"),
                    "excerpt": r.get("content", "")[:600],
                    "section_heading": r.get("section_heading", ""),
                    "page_number": r.get("page_number", 1),
                    "created_at": str(r.get("created_at", "")),
                    "tags": r.get("tags", []),
                    "relevance_score": round(
                        r.get("rerank_score", r.get("@search.score", 0)), 3
                    ),
                })

            if not formatted:
                return json.dumps({"results": [], "message": "No documents found matching this query."})

            return json.dumps({
                "results": formatted,
                "total_found": len(formatted),
                "retrieval_confidence": quality["confidence"],
            })

        except Exception as e:
            logger.error(f"Researcher search failed: {e}")
            return json.dumps({"error": str(e), "results": []})

    @kernel_function(
        description="""Get the complete full text of a specific document by its ID.
        Use this when you need to read the entire document, not just an excerpt."""
    )
    async def get_full_document(
        self,
        document_id: Annotated[str, "The document ID to retrieve"],
    ) -> str:
        try:
            client = get_search_client()
            if client is None:
                return json.dumps({"error": "Search client not configured"})

            doc = client.get_document(key=document_id)
            return json.dumps({
                "id": doc.get("id"),
                "title": doc.get("title"),
                "content": doc.get("content"),
                "department": doc.get("department"),
                "section_heading": doc.get("section_heading", ""),
                "page_number": doc.get("page_number", 1),
                "created_at": str(doc.get("created_at")),
            })
        except Exception as e:
            logger.error(f"Researcher get_document failed: {e}")
            return json.dumps({"error": str(e)})

    @kernel_function(
        description="""List all available documents filtered by department or type.
        Use this to understand what documents exist before searching."""
    )
    async def list_documents(
        self,
        department: Annotated[Optional[str], "Filter by department (optional)"] = None,
        doc_type: Annotated[Optional[str], "Filter by type: contract, report, policy, complaint, maintenance (optional)"] = None,
        limit: Annotated[int, "Maximum number to return"] = 20,
    ) -> str:
        try:
            client = get_search_client()
            if client is None:
                return self._mock_document_list()

            filters = []
            if department:
                filters.append(f"department eq '{department}'")
            if doc_type:
                filters.append(f"doc_type eq '{doc_type}'")

            results = client.search(
                search_text="*",
                top=limit,
                filter=" and ".join(filters) if filters else None,
                select=["id", "title", "department", "doc_type", "created_at"],
            )

            docs = [
                {
                    "id": r["id"],
                    "title": r.get("title"),
                    "department": r.get("department"),
                    "type": r.get("doc_type"),
                    "date": str(r.get("created_at", "")),
                }
                for r in results
            ]

            return json.dumps({"documents": docs, "total": len(docs)})

        except Exception as e:
            return json.dumps({"error": str(e), "documents": []})

    # ── Knowledge Gap Logging ─────────────────────────────────────────────────

    async def _log_knowledge_gap(
        self,
        query: str,
        confidence: float,
        department_filter: Optional[str] = None,
    ) -> None:
        """Persist a knowledge gap record so admins can see unanswerable queries."""
        try:
            from models.database import SessionLocal, KnowledgeGap
            db = SessionLocal()
            try:
                gap = KnowledgeGap(
                    query=query,
                    department_filter=department_filter,
                    confidence_score=confidence,
                )
                db.add(gap)
                db.commit()
                logger.info(f"Knowledge gap logged: '{query[:60]}' (confidence={confidence})")
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Failed to log knowledge gap: {e}")

    # ── Mock data ─────────────────────────────────────────────────────────────

    def _mock_search(self, query: str) -> str:
        mock_results = [
            {
                "document_id": "doc_001",
                "title": "MTN Nigeria Q1 2026 Network Performance Report",
                "department": "Network Operations",
                "doc_type": "report",
                "excerpt": (
                    "Lagos Zone 7 experienced elevated customer complaints in Q1 2026, "
                    "with 847 tickets logged between March 1-31. Tower 4471 in Ikeja "
                    "recorded intermittent failures on March 15, 18, and 22, affecting "
                    "approximately 12,000 subscribers during peak hours (18:00-21:00)."
                ),
                "section_heading": "NETWORK INCIDENTS",
                "page_number": 4,
                "relevance_score": 0.94,
            },
            {
                "document_id": "doc_002",
                "title": "Vendor Contract — TowerCo Nigeria Infrastructure Agreement",
                "department": "Procurement",
                "doc_type": "contract",
                "excerpt": (
                    "Agreement term: January 2024 to December 2026. Renewal notice required "
                    "90 days before expiry. Current monthly fee: NGN 45,000,000. SLA: 99.5% "
                    "uptime guarantee. Penalty clause: 2% fee reduction per 0.1% below SLA."
                ),
                "section_heading": "CONTRACT TERMS",
                "page_number": 2,
                "relevance_score": 0.88,
            },
            {
                "document_id": "doc_003",
                "title": "Customer Complaint Analysis — Lagos Region April 2026",
                "department": "Customer Experience",
                "doc_type": "complaint",
                "excerpt": (
                    "Total complaints received: 1,247. Top complaint categories: "
                    "slow data speeds (43%), dropped calls (28%), billing issues (18%), "
                    "other (11%). Geographic concentration: Ikeja (34%), Victoria Island (22%), "
                    "Lekki (19%). Most affected hours: 6pm-9pm weekdays."
                ),
                "section_heading": "COMPLAINT SUMMARY",
                "page_number": 1,
                "relevance_score": 0.91,
            },
        ]
        return json.dumps({
            "results": mock_results,
            "total_found": len(mock_results),
            "retrieval_confidence": 0.91,
            "source": "mock",
        })

    def _mock_document_list(self) -> str:
        docs = [
            {"id": "doc_001", "title": "Q1 2026 Network Performance Report", "department": "Network Operations", "type": "report"},
            {"id": "doc_002", "title": "TowerCo Vendor Contract", "department": "Procurement", "type": "contract"},
            {"id": "doc_003", "title": "Customer Complaint Analysis April 2026", "department": "Customer Experience", "type": "complaint"},
            {"id": "doc_004", "title": "NCC Regulatory Compliance Framework 2026", "department": "Legal", "type": "policy"},
            {"id": "doc_005", "title": "MTN Data Retention Policy v3.2", "department": "Legal", "type": "policy"},
            {"id": "doc_006", "title": "Tower Maintenance Log — Lagos March 2026", "department": "Network Operations", "type": "maintenance"},
        ]
        return json.dumps({"documents": docs, "total": len(docs)})
