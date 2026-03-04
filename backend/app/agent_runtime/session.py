"""AgentSession — lightweight per-request state carrier.

Created by the route, passed into AgentRuntime.run_stream(), and populated
as the pipeline executes. Nothing is persisted between requests (no DB yet).
"""

import uuid
from dataclasses import dataclass, field


@dataclass
class AgentSession:
    """Holds the question and any state accumulated during agent execution."""

    question: str
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    # Populated by AgentRuntime after retrieval
    retrieved_results: list[dict] = field(default_factory=list)

    # Populated by AgentRuntime after generation
    answer_text: str = ""
