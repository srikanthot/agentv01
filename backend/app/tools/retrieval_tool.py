"""RetrievalTool — hybrid search against Azure AI Search.

Implements the tool module pattern from Microsoft's agent framework:
each tool is a pure function (or thin class) that does one thing.

Pipeline inside retrieve():
  1. Generate query embedding via Azure OpenAI (aoai_embeddings.embed).
  2. Issue a hybrid search: keyword (search_text) + vector (VectorizedQuery).
  3. Optionally apply semantic reranking — falls back silently if unavailable.
  4. Normalise raw Azure Search documents to a canonical dict schema.
  5. Sort by relevance score descending.
  6. Apply source-diversity filter (cap chunks per source file).

The index is assumed to ALREADY EXIST — this module never creates or
modifies the index.
"""

import logging
from collections import defaultdict

from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery

from app.config.settings import (
    AZURE_SEARCH_API_KEY,
    AZURE_SEARCH_ENDPOINT,
    AZURE_SEARCH_INDEX,
    DIVERSITY_BY_SOURCE,
    MAX_CHUNKS_PER_SOURCE,
    QUERY_LANGUAGE,
    SEARCH_CHUNK_ID_FIELD,
    SEARCH_CONTENT_FIELD,
    SEARCH_FILENAME_FIELD,
    SEARCH_PAGE_FIELD,
    SEARCH_SECTION_FIELD,
    SEARCH_URL_FIELD,
    SEARCH_VECTOR_FIELD,
    SEMANTIC_CONFIG_NAME,
    TOP_K,
    TRACE_MODE,
    USE_SEMANTIC_RERANKER,
    VECTOR_K,
)
from app.llm.aoai_embeddings import embed

logger = logging.getLogger(__name__)


def _get_search_client() -> SearchClient:
    return SearchClient(
        endpoint=AZURE_SEARCH_ENDPOINT,
        index_name=AZURE_SEARCH_INDEX,
        credential=AzureKeyCredential(AZURE_SEARCH_API_KEY),
    )


def _select_fields() -> list[str]:
    """Return only the fields that are configured (non-empty env values)."""
    return [
        f for f in [
            SEARCH_CONTENT_FIELD,
            SEARCH_FILENAME_FIELD,
            SEARCH_PAGE_FIELD,
            SEARCH_CHUNK_ID_FIELD,
            SEARCH_URL_FIELD,
            SEARCH_SECTION_FIELD,
        ]
        if f
    ]


def _normalize(doc: dict) -> dict:
    """Map a raw Azure Search document to the canonical result schema."""
    return {
        "content": doc.get(SEARCH_CONTENT_FIELD) or "",
        "source": doc.get(SEARCH_FILENAME_FIELD) or "",
        "page": str(doc.get(SEARCH_PAGE_FIELD) or ""),
        "url": doc.get(SEARCH_URL_FIELD) or "",
        "chunk_id": doc.get(SEARCH_CHUNK_ID_FIELD) or "",
        "score": doc.get("@search.score") or 0.0,
    }


def _apply_diversity(results: list[dict]) -> list[dict]:
    """Keep at most MAX_CHUNKS_PER_SOURCE per source file.

    Results are already sorted by score descending, so we keep the
    highest-scoring chunks per source and discard the rest.
    """
    counts: defaultdict[str, int] = defaultdict(int)
    filtered: list[dict] = []
    for r in results:
        src = r["source"]
        if counts[src] < MAX_CHUNKS_PER_SOURCE:
            filtered.append(r)
            counts[src] += 1
    return filtered


def retrieve(question: str, top_k: int = TOP_K) -> list[dict]:
    """Run a hybrid search and return normalised, diversity-filtered results.

    Parameters
    ----------
    question:
        The user's question (used as both keyword query and embedding input).
    top_k:
        Maximum number of chunks to return after diversity filtering.

    Returns
    -------
    list[dict]
        Normalised result dicts with keys: content, source, page, url,
        chunk_id, score. Ordered by relevance score descending.
    """
    # ── 1. Generate query embedding ───────────────────────────────────────────
    query_vector: list[float] | None = None
    try:
        query_vector = embed(question)
    except Exception:
        logger.exception(
            "Embedding generation failed — falling back to keyword-only search"
        )

    # ── 2. Build search arguments ─────────────────────────────────────────────
    client = _get_search_client()
    select = _select_fields()

    search_kwargs: dict = {
        "search_text": question,
        "top": top_k,
        "select": select,
    }

    if query_vector:
        search_kwargs["vector_queries"] = [
            VectorizedQuery(
                vector=query_vector,
                k_nearest_neighbors=VECTOR_K,
                fields=SEARCH_VECTOR_FIELD,
            )
        ]

    # ── 3. Execute search (with optional semantic reranking) ──────────────────
    raw_results: list[dict] = []

    if USE_SEMANTIC_RERANKER:
        try:
            from azure.search.documents.models import QueryType  # noqa: PLC0415

            search_kwargs["query_type"] = QueryType.SEMANTIC
            search_kwargs["semantic_configuration_name"] = SEMANTIC_CONFIG_NAME
            search_kwargs["query_language"] = QUERY_LANGUAGE
            raw_results = list(client.search(**search_kwargs))
            logger.info("Semantic reranker active — %d raw results", len(raw_results))
        except Exception:
            logger.warning(
                "Semantic reranking unavailable — falling back to hybrid search"
            )
            search_kwargs.pop("query_type", None)
            search_kwargs.pop("semantic_configuration_name", None)
            search_kwargs.pop("query_language", None)
            raw_results = list(client.search(**search_kwargs))
    else:
        raw_results = list(client.search(**search_kwargs))

    # ── 4. Normalise ──────────────────────────────────────────────────────────
    results = [_normalize(doc) for doc in raw_results]
    results.sort(key=lambda r: r["score"], reverse=True)

    # ── 5. Diversity filter ───────────────────────────────────────────────────
    if DIVERSITY_BY_SOURCE:
        results = _apply_diversity(results)

    # ── 6. Trace logging (no secrets) ─────────────────────────────────────────
    if TRACE_MODE:
        for r in results:
            logger.info(
                "TRACE | source=%s  page=%s  chunk=%s  score=%.4f",
                r["source"], r["page"], r["chunk_id"], r["score"],
            )

    return results
