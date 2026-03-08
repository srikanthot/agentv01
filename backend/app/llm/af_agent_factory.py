"""Microsoft Agent Framework singleton — AzureOpenAIChatClient + Agent.

Reads configuration from environment variables (loaded by settings.py at
import time via python-dotenv):

  AZURE_OPENAI_ENDPOINT            – Azure OpenAI resource URL
  AZURE_OPENAI_API_KEY             – API key
  AZURE_OPENAI_API_VERSION         – e.g. 2024-06-01
  AZURE_OPENAI_CHAT_DEPLOYMENT_NAME – chat model deployment name

The module exposes two singletons used by AgentRuntime:
  af_agent     – the configured Agent instance
  rag_provider – the RagContextProvider instance (shared so AgentRuntime
                 can pre-load results before each agent.run() call)
"""

from agent_framework import InMemoryHistoryProvider
from agent_framework.azure import AzureOpenAIChatClient

from app.agent_runtime.af_rag_context_provider import RagContextProvider
from app.agent_runtime.prompts import SYSTEM_PROMPT

# Shared provider instance — AgentRuntime calls rag_provider.store_results()
# before agent.run() so the provider can inject the pre-fetched chunks.
rag_provider = RagContextProvider()

# AzureOpenAIChatClient reads AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY,
# AZURE_OPENAI_API_VERSION, and AZURE_OPENAI_CHAT_DEPLOYMENT_NAME from env.
_client = AzureOpenAIChatClient()

af_agent = _client.as_agent(
    name="PSEGTechManualAgent",
    instructions=SYSTEM_PROMPT,
    context_providers=[
        # InMemoryHistoryProvider maintains multi-turn conversation memory
        # in session.state — no external storage required locally.
        # Swap for a CosmosDB/Redis provider when ready for production.
        InMemoryHistoryProvider(),
        # RagContextProvider injects the pre-retrieved Azure AI Search chunks
        # as additional instructions before every LLM call.
        rag_provider,
    ],
)
