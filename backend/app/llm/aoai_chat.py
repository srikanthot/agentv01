"""Azure OpenAI chat completion wrapper for GCC High.

Uses the openai==1.43.0 AzureOpenAI client pointed at the GCC High endpoint
(openai.azure.us). Yields token strings from a streaming completion so the
AgentRuntime can relay them to the SSE stream immediately as they arrive.
"""

import logging
from typing import Generator

from openai import AzureOpenAI

from app.config.settings import (
    AZURE_OPENAI_API_KEY,
    AZURE_OPENAI_API_VERSION,
    AZURE_OPENAI_CHAT_DEPLOYMENT,
    AZURE_OPENAI_ENDPOINT,
)

logger = logging.getLogger(__name__)


def _get_client() -> AzureOpenAI:
    """Return an AzureOpenAI client configured for GCC High."""
    return AzureOpenAI(
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
        api_key=AZURE_OPENAI_API_KEY,
        api_version=AZURE_OPENAI_API_VERSION,
    )


def stream_chat(messages: list[dict]) -> Generator[str, None, None]:
    """Stream a chat completion and yield individual token strings.

    Parameters
    ----------
    messages:
        OpenAI-style message list — typically [system_msg, user_msg].

    Yields
    ------
    str
        Individual token strings as they arrive from the model.

    Raises
    ------
    openai.OpenAIError
        Propagated to the caller (AgentRuntime handles it).
    """
    client = _get_client()

    response = client.chat.completions.create(
        model=AZURE_OPENAI_CHAT_DEPLOYMENT,
        messages=messages,
        stream=True,
        temperature=0.2,
        max_tokens=2048,
    )

    for chunk in response:
        if chunk.choices and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content
