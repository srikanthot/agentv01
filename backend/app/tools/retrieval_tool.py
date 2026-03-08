"""RetrievalTool — hybrid search against Azure AI Search.

Implements the tool module pattern from Microsoft's agent framework:
each tool is a pure function (or thin class) that does one thing.

Pipeline inside retrieve():
  1. Distill the user's query: strip conversational filler so BM25 keyword
     search focuses on technical terms (e.g. "Underground Plastic Piping
     safety measures") not noise words ("Right now, I am installing…").
     The original query is still used for vector embedding (semantic).
  2. Generate query embedding via Azure OpenAI (aoai_embeddings.embed).
  3. Issue a hybrid search against RETRIEVAL_CANDIDATES (wider pool):
       keyword (distilled search_text) + vector (VectorizedQuery).
  4. Optionally apply semantic reranking — falls back silently if unavailable.
  5. Normalise raw Azure Search documents to a canonical dict schema.
  6. Sort by relevance score descending.
  7. Adaptive diversity filter:
       - Detect a "dominant" source (its top score >= DOMINANT_SOURCE_SCORE_RATIO
         × the next source's top score).
       - Allow up to MAX_CHUNKS_DOMINANT_SOURCE chunks from the dominant source;
         all others are still capped at MAX_CHUNKS_PER_SOURCE.
  8. Score-gap filter: discard any remaining chunk whose score falls below
     SCORE_GAP_MIN_RATIO × top_score — removes low-relevance cross-source noise.
  9. Return at most TOP_K final results.

The index is assumed to ALREADY EXIST — this module never creates or
modifies the index.
"""

import logging
import re
from collections import defaultdict

from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery

from app.config.settings import (
    AZURE_SEARCH_API_KEY,
    AZURE_SEARCH_ENDPOINT,
    AZURE_SEARCH_INDEX,
    DIVERSITY_BY_SOURCE,
    DOMINANT_SOURCE_SCORE_RATIO,
    MAX_CHUNKS_DOMINANT_SOURCE,
    MAX_CHUNKS_PER_SOURCE,
    QUERY_LANGUAGE,
    RETRIEVAL_CANDIDATES,
    SCORE_GAP_MIN_RATIO,
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

# ---------------------------------------------------------------------------
# Query distillation — strip conversational filler before BM25 keyword search
# ---------------------------------------------------------------------------
# BM25 scores every token. Noise words ("Right now, I am installing…") dilute
# the weight of the technical phrase ("Underground Plastic Piping safety").
# We strip them so keyword search focuses on what matters.
# Vector search still uses the original question (embeddings are semantic).
_FILLER_RE = re.compile(
    r"\b(right now|currently|at this (moment|time)|i am|i'm|i need to|i want to|"
    r"can you|what should( i)?|how do i|what are the|please|tell me|help me|"
    r"so |just |i was told|could you|would you|i have to|what do i)\b",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Noise/TOC chunk detection
# ---------------------------------------------------------------------------
# TOC pages score high on keyword search because they list exact section titles
# (e.g. "Underground Plastic Piping . . . . . . 2-11"), but contain no real
# procedural content. They confuse the LLM by making it think the context
# is just an index with no instructions.
_TOC_CHUNK_PATTERNS = [
    re.compile(r"Table\s+of\s+Contents", re.IGNORECASE),
    re.compile(r"(\. ){5,}"),          # dot leaders: ". . . . . . 2-11"
    re.compile(r"^Index\b", re.IGNORECASE | re.MULTILINE),
]


def _is_toc_chunk(content: str) -> bool:
    """Return True if this chunk looks like a Table of Contents / index page."""
    sample = content[:400]
    return any(p.search(sample) for p in _TOC_CHUNK_PATTERNS)


# ---------------------------------------------------------------------------
# Heading extraction — detect section headings inside chunk content
# ---------------------------------------------------------------------------
# Technical manuals use numbered sections (7.1 Title), ALL-CAPS lines, or
# short Title-Case lines as headings. We check the first 3 lines of each
# chunk. Used in TRACE logging to identify which section a chunk belongs to.
_NUMBERED_SECTION_RE = re.compile(r"^\d+(\.\d+)*\s+\S")


def _distill_keyword_query(question: str) -> str:
    """Remove conversational filler to improve BM25 keyword recall.

    Returns the distilled string if it is still meaningful (≥10 chars);
    otherwise falls back to the original to avoid an empty search_text.
    """
    distilled = _FILLER_RE.sub(" ", question)
    distilled = re.sub(r"[,\s]+", " ", distilled).strip()
    return distilled if len(distilled) >= 10 else question


def _extract_heading(content: str) -> str:
    """Try to extract a section heading from the first few lines of a chunk.

    Matches:
    - Numbered sections: "7.1 Underground Gas Piping Installations"
    - ALL-CAPS lines: "STORAGE AND HANDLING PRECAUTIONS"
    - Short Title-Case lines: "Pressure Testing Requirements"

    Returns the first matching line, or "" if none found.
    """
    for line in content.strip().splitlines()[:4]:
        line = line.strip()
        if not line or len(line) > 80:
            continue
        if _NUMBERED_SECTION_RE.match(line):
            return line
        if line.isupper() and len(line) >= 5:
            return line
        words = line.split()
        if (2 <= len(words) <= 9
                and all(w[0].isupper() for w in words if len(w) > 3)):
            return line
    return ""


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


def _adaptive_diversity(results: list[dict]) -> list[dict]:
    """Adaptive per-source cap that rewards a clearly dominant source.

    Standard behaviour (no dominant source): cap every source at
    MAX_CHUNKS_PER_SOURCE (default 2).

    Dominant-source behaviour: if one source's top score is >=
    DOMINANT_SOURCE_SCORE_RATIO × the next source's top score, that source
    may contribute up to MAX_CHUNKS_DOMINANT_SOURCE chunks (default 4).
    This lets the clearly-matching manual (e.g. gas_appliances_gas_piping.pdf)
    provide fuller grounding context instead of being truncated at 2.
    """
    if not results:
        return results

    # Find the best score per source (results are already sorted descending)
    source_top: dict[str, float] = {}
    for r in results:
        src = r["source"]
        if src not in source_top:
            source_top[src] = r["score"]

    sorted_sources = sorted(source_top.items(), key=lambda x: x[1], reverse=True)
    dominant_source = sorted_sources[0][0]
    dominant_score = sorted_sources[0][1]
    second_score = sorted_sources[1][1] if len(sorted_sources) > 1 else 0.0

    is_dominant = (
        second_score == 0.0
        or dominant_score >= DOMINANT_SOURCE_SCORE_RATIO * second_score
    )
    cap_for_dominant = MAX_CHUNKS_DOMINANT_SOURCE if is_dominant else MAX_CHUNKS_PER_SOURCE

    if TRACE_MODE:
        ratio_str = (
            f"{dominant_score / second_score:.2f}x"
            if second_score > 0 else "∞"
        )
        logger.info(
            "TRACE | dominant_source=%s  score_ratio=%s  dominant=%s  cap=%d",
            dominant_source, ratio_str, is_dominant, cap_for_dominant,
        )

    counts: defaultdict[str, int] = defaultdict(int)
    filtered: list[dict] = []
    for r in results:
        src = r["source"]
        cap = cap_for_dominant if src == dominant_source else MAX_CHUNKS_PER_SOURCE
        if counts[src] < cap:
            filtered.append(r)
            counts[src] += 1
    return filtered


def _filter_score_gap(results: list[dict]) -> list[dict]:
    """Remove chunks that score below SCORE_GAP_MIN_RATIO × top_score.

    After diversity filtering, secondary-source chunks may remain that are far
    less relevant than the best chunk. These add noise to the LLM context and
    can cause the model to cite wrong documents or extrapolate from them.

    Example: gas_appliances top=0.0333, PEPP=0.0167 → ratio 0.50.
    With SCORE_GAP_MIN_RATIO=0.55, the PEPP chunk is removed (0.50 < 0.55).
    """
    if not results or SCORE_GAP_MIN_RATIO <= 0:
        return results

    top_score = results[0]["score"]
    if top_score == 0:
        return results

    threshold = SCORE_GAP_MIN_RATIO * top_score
    filtered = [r for r in results if r["score"] >= threshold]

    removed = len(results) - len(filtered)
    if TRACE_MODE and removed:
        logger.info(
            "TRACE | score_gap_filter: removed %d chunk(s) below %.4f "
            "(%.0f%% of top score %.4f)",
            removed, threshold, SCORE_GAP_MIN_RATIO * 100, top_score,
        )
    return filtered


def retrieve(question: str, top_k: int = TOP_K) -> list[dict]:
    """Run a hybrid search and return normalised, filtered results.

    Parameters
    ----------
    question:
        The user's question. Used verbatim for vector embedding (semantic).
        A distilled version (conversational filler stripped) is used for
        the BM25 keyword search so technical terms score higher.
    top_k:
        Maximum number of chunks to return after all filters.

    Returns
    -------
    list[dict]
        Normalised result dicts with keys: content, source, page, url,
        chunk_id, score. Ordered by relevance score descending.
    """
    # ── 1. Distill keyword query (keep original for vector embedding) ─────────
    keyword_query = _distill_keyword_query(question)
    if TRACE_MODE and keyword_query != question:
        logger.info("TRACE | keyword_query=%r", keyword_query)

    # ── 2. Generate query embedding (uses original question, not distilled) ───
    query_vector: list[float] | None = None
    try:
        query_vector = embed(question)
    except Exception:
        logger.exception(
            "Embedding generation failed — falling back to keyword-only search"
        )

    # ── 3. Build search arguments ─────────────────────────────────────────────
    # Ask for RETRIEVAL_CANDIDATES from the index (wider pool so diversity
    # filter has more to work with); trim to top_k after all filters.
    client = _get_search_client()
    select = _select_fields()

    search_kwargs: dict = {
        "search_text": keyword_query,
        "top": RETRIEVAL_CANDIDATES,
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

    # ── 4. Execute search (with optional semantic reranking) ──────────────────
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

    # ── 5. Normalise and sort ─────────────────────────────────────────────────
    results = [_normalize(doc) for doc in raw_results]
    results.sort(key=lambda r: r["score"], reverse=True)

    # ── 5b. Filter TOC / index pages ─────────────────────────────────────────
    # TOC pages score high because they list exact section titles as keywords,
    # but they contain no procedural content and confuse the LLM.
    before_toc = len(results)
    results = [r for r in results if not _is_toc_chunk(r["content"])]
    if TRACE_MODE and len(results) < before_toc:
        logger.info(
            "TRACE | toc_filter: removed %d TOC/index chunk(s)",
            before_toc - len(results),
        )

    # ── 6. Adaptive diversity filter (dominant source gets higher cap) ────────
    if DIVERSITY_BY_SOURCE:
        results = _adaptive_diversity(results)

    # ── 7. Score-gap filter (remove low-relevance cross-source noise) ─────────
    results = _filter_score_gap(results)

    # ── 8. Trim to top_k ──────────────────────────────────────────────────────
    results = results[:top_k]

    # ── 9. Trace logging — ranked chunks with heading, source, score, preview ─
    if TRACE_MODE:
        logger.info("TRACE | final_chunks=%d (top_k=%d)", len(results), top_k)
        for i, r in enumerate(results, start=1):
            heading = _extract_heading(r["content"])
            preview = r["content"][:120].replace("\n", " ")
            logger.info(
                "TRACE | [%d] source=%s  page=%s  score=%.4f  heading=%r | %s",
                i, r["source"], r["page"], r["score"], heading, preview,
            )

    return results
