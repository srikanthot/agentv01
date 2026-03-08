"""Application settings loaded from environment variables.

All configuration is driven by .env so the same codebase works across
dev / staging / production without code changes.
"""

import os

from dotenv import load_dotenv

load_dotenv(override=True)

# ---------------------------------------------------------------------------
# Azure OpenAI (GCC High — openai.azure.us)
# ---------------------------------------------------------------------------
AZURE_OPENAI_ENDPOINT: str = os.getenv("AZURE_OPENAI_ENDPOINT", "")
AZURE_OPENAI_API_KEY: str = os.getenv("AZURE_OPENAI_API_KEY", "")
AZURE_OPENAI_API_VERSION: str = os.getenv("AZURE_OPENAI_API_VERSION", "2024-06-01")
AZURE_OPENAI_CHAT_DEPLOYMENT: str = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT", "")
# Agent Framework SDK reads AZURE_OPENAI_CHAT_DEPLOYMENT_NAME; fallback to legacy var
AZURE_OPENAI_CHAT_DEPLOYMENT_NAME: str = os.getenv(
    "AZURE_OPENAI_CHAT_DEPLOYMENT_NAME",
    os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT", ""),
)
AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT: str = os.getenv("AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT", "")

# ---------------------------------------------------------------------------
# Azure AI Search (GCC High — search.azure.us)
# ---------------------------------------------------------------------------
AZURE_SEARCH_ENDPOINT: str = os.getenv("AZURE_SEARCH_ENDPOINT", "")
AZURE_SEARCH_API_KEY: str = os.getenv("AZURE_SEARCH_API_KEY", "")
AZURE_SEARCH_INDEX: str = os.getenv("AZURE_SEARCH_INDEX", "")

# ---------------------------------------------------------------------------
# Index field mappings — set these to match your actual index schema.
# Leave SEARCH_SECTION_FIELD blank if your index has no section field.
# ---------------------------------------------------------------------------
SEARCH_CONTENT_FIELD: str = os.getenv("SEARCH_CONTENT_FIELD", "content")
SEARCH_VECTOR_FIELD: str = os.getenv("SEARCH_VECTOR_FIELD", "contentVector")
SEARCH_FILENAME_FIELD: str = os.getenv("SEARCH_FILENAME_FIELD", "source_file")
SEARCH_PAGE_FIELD: str = os.getenv("SEARCH_PAGE_FIELD", "page_number")
SEARCH_CHUNK_ID_FIELD: str = os.getenv("SEARCH_CHUNK_ID_FIELD", "chunk_id")
SEARCH_URL_FIELD: str = os.getenv("SEARCH_URL_FIELD", "source_url")
SEARCH_SECTION_FIELD: str = os.getenv("SEARCH_SECTION_FIELD", "")

# ---------------------------------------------------------------------------
# Retrieval tuning
# ---------------------------------------------------------------------------
TOP_K: int = int(os.getenv("TOP_K", "5"))
# How many candidates to fetch from Azure AI Search before the diversity
# filter trims to TOP_K. A wider pool ensures the diversity filter has enough
# variety — especially when multiple relevant chunks share one source file.
RETRIEVAL_CANDIDATES: int = int(os.getenv("RETRIEVAL_CANDIDATES", "15"))
VECTOR_K: int = int(os.getenv("VECTOR_K", "50"))

# ---------------------------------------------------------------------------
# Retrieval quality
# ---------------------------------------------------------------------------
USE_SEMANTIC_RERANKER: bool = os.getenv("USE_SEMANTIC_RERANKER", "false").lower() == "true"
SEMANTIC_CONFIG_NAME: str = os.getenv("SEMANTIC_CONFIG_NAME", "default")
QUERY_LANGUAGE: str = os.getenv("QUERY_LANGUAGE", "en-us")
MIN_RESULTS: int = int(os.getenv("MIN_RESULTS", "2"))
MIN_AVG_SCORE: float = float(os.getenv("MIN_AVG_SCORE", "0.02"))
DIVERSITY_BY_SOURCE: bool = os.getenv("DIVERSITY_BY_SOURCE", "true").lower() == "true"
MAX_CHUNKS_PER_SOURCE: int = int(os.getenv("MAX_CHUNKS_PER_SOURCE", "2"))
# When one source file's top score is >= DOMINANT_SOURCE_SCORE_RATIO × the
# next source's top score, that source is "dominant". Dominant sources are
# allowed up to MAX_CHUNKS_DOMINANT_SOURCE chunks instead of the usual cap,
# so a clearly-matched manual can contribute more grounding context.
DOMINANT_SOURCE_SCORE_RATIO: float = float(os.getenv("DOMINANT_SOURCE_SCORE_RATIO", "1.5"))
MAX_CHUNKS_DOMINANT_SOURCE: int = int(os.getenv("MAX_CHUNKS_DOMINANT_SOURCE", "4"))
# After diversity filtering, discard any chunk whose score is below
# SCORE_GAP_MIN_RATIO × top_score.  This removes low-relevance cross-source
# noise (e.g. PEPP chunks scoring 0.017 when gas_appliances chunks score 0.033).
SCORE_GAP_MIN_RATIO: float = float(os.getenv("SCORE_GAP_MIN_RATIO", "0.55"))
TRACE_MODE: bool = os.getenv("TRACE_MODE", "true").lower() == "true"
