"""AgentRuntime — central orchestrator for the PSEG Tech Manual agent.

Implements the Microsoft agent framework architecture pattern for self-hosted
deployment (Azure AI Foundry Managed Agents are not available in GCC High):

  1. RETRIEVE  — RetrievalTool: embed query → hybrid search Azure AI Search.
  2. GATE      — Confidence check: abort early if evidence is too thin.
  3. CONTEXT   — ContextProvider: format chunks into numbered evidence blocks.
  4. COMPOSE   — Prompts: inject context into grounded system + user prompt.
  5. GENERATE  — LLM: stream answer tokens from Azure OpenAI.
  6. CITE      — CitationProvider: dedup + emit structured citations SSE event.

The FastAPI route is intentionally thin — it creates a session and calls
AgentRuntime.run_stream(). All business logic lives here, not in the route.
"""

import json
import logging
import time
from collections.abc import Generator

from app.agent_runtime.citation_provider import build_citations
from app.agent_runtime.context_providers import build_context_blocks
from app.agent_runtime.prompts import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
from app.agent_runtime.session import AgentSession
from app.api.schemas import CitationsPayload
from app.config.settings import MIN_AVG_SCORE, MIN_RESULTS, TOP_K, TRACE_MODE
from app.llm.aoai_chat import stream_chat
from app.tools.retrieval_tool import retrieve

logger = logging.getLogger(__name__)

# Emit a keepalive ping every N seconds during long streaming answers.
# Prevents proxy / load-balancer / browser SSE timeout on slow networks.
_PING_INTERVAL_SECONDS = 20


def _sse_data(payload: str) -> str:
    """Encode a string as an SSE data line.

    Newlines inside *payload* are replaced by the two-character literal ``\\n``
    so SSE's blank-line event-boundary is never confused with content newlines.
    The frontend decodes them back before rendering.
    """
    encoded = payload.replace("\n", "\\n")
    return f"data: {encoded}\n\n"


def _sse_event(event_name: str, payload: str) -> str:
    """Encode a named SSE event."""
    return f"event: {event_name}\ndata: {payload}\n\n"


class AgentRuntime:
    """Orchestrates the full retrieve → generate → cite pipeline."""

    def run_stream(
        self,
        question: str,
        session: AgentSession,
        top_k: int = TOP_K,
    ) -> Generator[str, None, None]:
        """Execute the pipeline and yield SSE-formatted strings.

        Designed to be passed directly into FastAPI's StreamingResponse.

        Yields
        ------
        str
            SSE-formatted strings: token data lines, named events (citations,
            ping), and the final ``[DONE]`` sentinel.
        """
        logger.info(
            "AgentRuntime.run_stream | session=%s | question=%s",
            session.session_id, question,
        )

        # ── 1. RETRIEVE ───────────────────────────────────────────────────────
        try:
            results = retrieve(question, top_k=top_k)
        except Exception:
            logger.exception("Retrieval failed")
            yield _sse_data(
                "I'm sorry — an error occurred while searching the knowledge base. "
                "Please try again."
            )
            yield _sse_event("citations", json.dumps({"citations": []}))
            yield _sse_data("[DONE]")
            return

        session.retrieved_results = results

        # ── 2. GATE — confidence check ────────────────────────────────────────
        avg_score = (
            sum(r["score"] for r in results) / len(results)
            if results else 0.0
        )

        if TRACE_MODE:
            logger.info(
                "TRACE | n_results=%d  avg_score=%.4f  gate=(%d results, %.2f score)",
                len(results), avg_score, MIN_RESULTS, MIN_AVG_SCORE,
            )

        if len(results) < MIN_RESULTS or avg_score < MIN_AVG_SCORE:
            logger.info(
                "Confidence gate: insufficient evidence "
                "(n=%d avg=%.4f threshold_n=%d threshold_avg=%.2f)",
                len(results), avg_score, MIN_RESULTS, MIN_AVG_SCORE,
            )
            yield _sse_data(
                "I don't have enough evidence from the technical manuals to answer "
                "your question confidently.\n\n"
                "Could you provide more detail — for example, the equipment name, "
                "model number, or the specific procedure you are looking for?"
            )
            yield _sse_event(
                "citations",
                CitationsPayload(citations=[]).model_dump_json(),
            )
            yield _sse_data("[DONE]")
            return

        # ── 3. CONTEXT — format evidence blocks ───────────────────────────────
        context_blocks = build_context_blocks(results)

        # ── 4. COMPOSE — build grounded prompt ───────────────────────────────
        user_message = USER_PROMPT_TEMPLATE.format(
            question=question,
            context_blocks=context_blocks,
        )
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": user_message},
        ]

        # ── 5. GENERATE — stream tokens with keepalive ────────────────────────
        last_ping_at = time.monotonic()
        answer_buf: list[str] = []

        try:
            for token in stream_chat(messages):
                # Emit a keepalive ping if the answer is taking a while
                now = time.monotonic()
                if now - last_ping_at >= _PING_INTERVAL_SECONDS:
                    yield _sse_event("ping", "keepalive")
                    last_ping_at = now

                answer_buf.append(token)
                yield _sse_data(token)

        except Exception:
            logger.exception("LLM streaming failed")
            yield _sse_data(
                "\n\nI'm sorry — an error occurred while generating the answer. "
                "Please try again."
            )

        session.answer_text = "".join(answer_buf)

        # ── 6. CITE — structured citations event ─────────────────────────────
        citations = build_citations(results)
        payload = CitationsPayload(citations=citations)
        yield _sse_event("citations", payload.model_dump_json())
        yield _sse_data("[DONE]")
