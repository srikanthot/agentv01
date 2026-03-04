"""CitationProvider — deduplicates and structures citations.

Converts the raw list of retrieved result dicts into a clean, deduplicated
list of Citation objects ready for the structured SSE citations event.

Deduplication key is (source, page) — multiple chunks from the same page
of the same document produce a single citation entry. Results are assumed
to arrive ordered by relevance score descending, so the first occurrence of
each key is the most relevant chunk.
"""

from app.api.schemas import Citation


def build_citations(results: list[dict]) -> list[Citation]:
    """Build a deduplicated, ordered citation list from retrieved results.

    Parameters
    ----------
    results:
        Normalised result dicts from RetrievalTool — keys: source, page,
        url, chunk_id, score. Expected to be ordered highest score first.

    Returns
    -------
    list[Citation]
        One Citation per unique (source, page) pair, in order of first
        appearance (i.e. highest relevance).
    """
    seen: set[str] = set()
    citations: list[Citation] = []

    for r in results:
        key = f"{r['source']}|{r['page']}"
        if key not in seen:
            seen.add(key)
            citations.append(
                Citation(
                    source=r["source"],
                    page=r.get("page", ""),
                    url=r.get("url", ""),
                    chunk_id=r.get("chunk_id", ""),
                )
            )

    return citations
