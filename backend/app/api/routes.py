"""FastAPI routes — intentionally thin per the agent framework pattern.

The route does exactly three things:
  1. Validate the incoming request (Pydantic does this automatically).
  2. Create an AgentSession.
  3. Hand off to AgentRuntime.run_stream() and return StreamingResponse.

No business logic lives here. Adding a new endpoint means adding a new
thin route that delegates to a new AgentRuntime method.
"""

import logging

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.agent_runtime.agent import AgentRuntime
from app.agent_runtime.session import AgentSession
from app.api.schemas import ChatRequest

logger = logging.getLogger(__name__)
router = APIRouter()

# Single shared runtime instance — stateless, safe for concurrent requests
_runtime = AgentRuntime()


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest) -> StreamingResponse:
    """Stream a grounded answer with citations via Server-Sent Events.

    Request body: ``{"question": "...", "session_id": "optional-uuid"}``

    Response: ``text/event-stream``
    - Token data lines:      ``data: <token>\\n\\n``
    - Keepalive ping:        ``event: ping\\ndata: keepalive\\n\\n``
    - Structured citations:  ``event: citations\\ndata: {...}\\n\\n``
    - End sentinel:          ``data: [DONE]\\n\\n``
    """
    logger.info(
        "POST /chat/stream | session=%s | question=%s",
        request.session_id, request.question,
    )

    session = AgentSession(question=request.question)
    if request.session_id:
        session.session_id = request.session_id

    return StreamingResponse(
        _runtime.run_stream(request.question, session),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
