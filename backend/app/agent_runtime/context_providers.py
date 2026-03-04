"""ContextProvider — formats retrieved evidence into grounded prompt context.

Mirrors the AIContextProvider pattern from Microsoft's agent framework:
each retrieved chunk is labeled with its source metadata (source file,
page, URL, chunk ID) so the LLM can cite it accurately and the user can
trace every claim back to a specific page.
"""


def build_context_blocks(results: list[dict]) -> str:
    """Format retrieved chunks into numbered, labeled evidence blocks.

    Each block carries a header with source metadata and the raw chunk
    content below it. The LLM prompt instructs the model to answer only
    from these blocks and to reference them by their [N] label.

    Parameters
    ----------
    results:
        Normalised result dicts from RetrievalTool — keys: content, source,
        page, url, chunk_id, score.

    Returns
    -------
    str
        A single string with one evidence block per chunk, separated by
        horizontal rules.
    """
    blocks: list[str] = []
    for i, r in enumerate(results, start=1):
        header_parts = [f"[{i}] Source: {r['source']}"]
        if r.get("page"):
            header_parts.append(f"Page: {r['page']}")
        if r.get("url"):
            header_parts.append(f"URL: {r['url']}")
        if r.get("chunk_id"):
            header_parts.append(f"ChunkID: {r['chunk_id']}")
        header = " | ".join(header_parts)
        blocks.append(f"{header}\n{r['content']}")

    return "\n\n---\n\n".join(blocks)
