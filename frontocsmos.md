I am adding Azure Cosmos DB chat history support to my existing FastAPI RAG chatbot backend.

Please make all required code changes end to end.

My requirements:
- Use Azure Cosmos DB for NoSQL
- Use key-based auth for now
- Read config from environment variables
- I already manually created these in Azure:
  - database: ragchatdb
  - container: conversations with partition key /user_id
  - container: messages with partition key /thread_id
- Do not auto-create containers unless env flag says so
- Backend is the source of truth
- One user can have many chat threads
- One thread has many messages
- I need persistent chat history like ChatGPT
- I need assistant messages to store citations too
- Keep code clean and production-friendly
- Do not break existing chat endpoint behavior
- If current project structure differs, adapt to it and wire it properly

Please implement the following.

==================================================
1. ADD REQUIRED PACKAGE
==================================================

Add the required Cosmos SDK dependency if missing:

- azure-cosmos
- python-dotenv if not already present

If this project uses requirements.txt, update it.
If it uses pyproject.toml, update that instead.

==================================================
2. ADD ENVIRONMENT VARIABLES SUPPORT
==================================================

Please make the backend read these environment variables:

COSMOS_AUTH_MODE=key
COSMOS_ENDPOINT=
COSMOS_KEY=
COSMOS_DATABASE=ragchatdb
COSMOS_CONVERSATIONS_CONTAINER=conversations
COSMOS_MESSAGES_CONTAINER=messages
COSMOS_AUTO_CREATE_CONTAINERS=false
COSMOS_HISTORY_MAX_TURNS=12
DEFAULT_LOCAL_USER_ID=local-dev
COSMOS_ENABLE_TTL=false
COSMOS_TTL_SECONDS=

Please:
- add them to config handling
- use safe defaults where appropriate
- validate required values when Cosmos history is enabled
- do not hardcode secrets

==================================================
3. CREATE A COSMOS CONFIG MODULE
==================================================

Create or update a config module that exposes strongly named settings, including:

- cosmos_auth_mode
- cosmos_endpoint
- cosmos_key
- cosmos_database
- cosmos_conversations_container
- cosmos_messages_container
- cosmos_auto_create_containers
- cosmos_history_max_turns
- default_local_user_id
- cosmos_enable_ttl
- cosmos_ttl_seconds

Use a clean config pattern already used by the project if one exists.

==================================================
4. CREATE A COSMOS CLIENT MODULE
==================================================

Create a reusable Cosmos DB client module.

Requirements:
- Use CosmosClient from azure.cosmos
- Support only key auth for now
- Create the client once and reuse it
- Expose:
  - get_cosmos_client()
  - get_cosmos_database()
  - get_conversations_container()
  - get_messages_container()
- If COSMOS_AUTO_CREATE_CONTAINERS=true, optionally create database/containers if missing
- If auto-create is false, assume they already exist
- Handle startup errors clearly with useful logs

Important:
- conversations container partition key is /user_id
- messages container partition key is /thread_id

If auto-create is implemented, it must create:
- database: ragchatdb
- conversations container with partition key /user_id
- messages container with partition key /thread_id

But default behavior must be to use existing database and containers.

==================================================
5. CREATE DATA MODELS / SCHEMAS
==================================================

Create clean Pydantic models or dataclasses matching the current project style.

Conversation document shape should support:

- id
- thread_id
- user_id
- user_name
- title
- created_at
- updated_at
- last_message_at
- last_user_message_preview
- last_assistant_message_preview
- message_count
- is_deleted
- metadata

Message document shape should support:

- id
- thread_id
- user_id
- role
- content
- citations
- created_at
- sequence
- status
- metadata

Also create a citation schema with fields like:
- source_id
- file_name
- title
- page
- chunk_id
- snippet
- score

Use UTC timestamps in ISO format.

==================================================
6. CREATE A CHAT HISTORY SERVICE
==================================================

Create a dedicated service module for Cosmos chat history.

Implement these functions or equivalent class methods:

Conversation-level:
- create_conversation(user_id, user_name=None, title=None, metadata=None) -> conversation document
- get_conversation(user_id, thread_id)
- list_conversations_for_user(user_id, limit=50, include_deleted=False)
- update_conversation_after_message(
    user_id,
    thread_id,
    role,
    content,
    created_at,
    increment_message_count=True
  )
- soft_delete_conversation(user_id, thread_id)

Message-level:
- create_message(
    thread_id,
    user_id,
    role,
    content,
    citations=None,
    status="completed",
    metadata=None,
    created_at=None,
    sequence=None
  )
- list_messages_for_thread(thread_id, limit=100, ascending=True)
- get_recent_messages_for_thread(thread_id, max_turns=12)

Behavior requirements:
- For conversations container:
  - id should equal thread_id
  - partition key is user_id
- For messages container:
  - id should be a unique message id
  - partition key is thread_id
- When creating a message, auto-compute sequence if not supplied
- When a message is saved, update the matching conversation summary fields:
  - updated_at
  - last_message_at
  - last_user_message_preview or last_assistant_message_preview
  - message_count
- user messages usually have empty citations
- assistant messages may include citations

Preview helper:
- store preview fields truncated to a reasonable length like 150 to 200 characters

Query behavior:
- list_conversations_for_user should return newest first by last_message_at
- list_messages_for_thread should return ordered by sequence
- get_recent_messages_for_thread should return only the last N turns worth of messages
- Do this efficiently for the chosen partition design

==================================================
7. WIRE COSMOS HISTORY INTO THE EXISTING CHAT FLOW
==================================================

Please integrate Cosmos history into the existing chat endpoint or service.

Desired behavior:
- If thread_id is missing in a new request, create a new conversation automatically
- If thread_id is present, continue that thread
- Resolve user_id like this:
  - if real auth/user context already exists in the project, use that
  - otherwise use DEFAULT_LOCAL_USER_ID from env
- Before sending the prompt to the LLM, load recent messages for that thread using COSMOS_HISTORY_MAX_TURNS
- Convert stored history into the format already expected by the current chat pipeline
- After the user message is received, save it into Cosmos
- After the assistant response is generated, save the assistant message into Cosmos
- If assistant response includes citations/sources/context references, map them into the message.citations field and persist them
- Return thread_id in the API response so the frontend can continue the same thread later

Important:
- do not break current RAG retrieval logic
- do not break Azure AI Search logic
- do not break Azure OpenAI logic
- only add persistent history support around the existing chat flow

==================================================
8. ADD HISTORY API ENDPOINTS
==================================================

Add simple FastAPI endpoints for chat history, matching existing router style.

Please add endpoints similar to:

1) GET /api/chat/threads
- returns threads for current user
- query params:
  - limit optional
- uses user_id from auth if available, otherwise DEFAULT_LOCAL_USER_ID

2) GET /api/chat/threads/{thread_id}
- returns conversation metadata for one thread

3) GET /api/chat/threads/{thread_id}/messages
- returns messages for one thread
- query params:
  - limit optional

4) DELETE /api/chat/threads/{thread_id}
- soft delete conversation

If route names should match the current project naming style, adapt accordingly.

==================================================
9. ADD A SIMPLE COSMOS HEALTH / TEST ENDPOINT
==================================================

Add a small endpoint like:

GET /api/health/cosmos

Behavior:
- attempts to read the configured database and both containers
- returns success/failure JSON
- include database and container names in the response
- do not expose secrets

This is for local verification.

==================================================
10. ADD STARTUP LOGGING
==================================================

On app startup, log useful non-secret information:
- Cosmos history enabled or not
- Cosmos endpoint host only, not the key
- database name
- container names
- auth mode

If config is incomplete, log a clear warning or fail fast depending on current project style.

==================================================
11. ADD ERROR HANDLING
==================================================

Please handle common Cosmos errors cleanly:
- missing config
- connection failure
- container not found
- partition key mismatch
- query/read errors

Return safe API errors and useful logs.
Do not expose secrets.

==================================================
12. ADD A SMALL MANUAL TEST SCRIPT
==================================================

Create a standalone script file like scripts/test_cosmos_history.py

It should:
- load env vars
- connect to Cosmos
- verify database and containers
- upsert one sample conversation
- upsert one sample user message
- upsert one sample assistant message with citations
- read them back
- print success output

Use:
- user_id = local-dev
- thread_id = thread_test_001

This is for quick local testing.

==================================================
13. SAMPLE DOCUMENT SHAPES TO FOLLOW
==================================================

Conversation example:
{
  "id": "thread_test_001",
  "thread_id": "thread_test_001",
  "user_id": "local-dev",
  "user_name": "Local Dev User",
  "title": "Test Conversation",
  "created_at": "2026-03-19T19:10:00Z",
  "updated_at": "2026-03-19T19:14:32Z",
  "last_message_at": "2026-03-19T19:14:32Z",
  "last_user_message_preview": "How do I reset the relay panel safely?",
  "last_assistant_message_preview": "Based on section 4.2, isolate power first and confirm lockout...",
  "message_count": 2,
  "is_deleted": false,
  "metadata": {
    "source": "fastapi",
    "channel": "web",
    "rag_enabled": true
  }
}

Assistant message example:
{
  "id": "msg_test_002",
  "thread_id": "thread_test_001",
  "user_id": "local-dev",
  "role": "assistant",
  "content": "Based on section 4.2, isolate power first and confirm lockout before opening the panel.",
  "citations": [
    {
      "source_id": "manual-001",
      "file_name": "switchgear_manual.pdf",
      "chunk_id": "chunk-000245",
      "title": "Panel Reset Procedure",
      "page": 42,
      "snippet": "Before performing a reset, isolate upstream power and verify lockout/tagout conditions.",
      "score": 0.93
    }
  ],
  "created_at": "2026-03-19T19:14:32Z",
  "sequence": 2,
  "status": "completed",
  "metadata": {
    "source": "local-test",
    "model": "gpt-4.1"
  }
}

==================================================
14. ENV FILE VALUES TO EXPECT
==================================================

The code should work with this .env layout:

COSMOS_AUTH_MODE=key
COSMOS_ENDPOINT=https://<account>.documents.azure.com:443/
COSMOS_KEY=<primary-key>
COSMOS_DATABASE=ragchatdb
COSMOS_CONVERSATIONS_CONTAINER=conversations
COSMOS_MESSAGES_CONTAINER=messages
COSMOS_AUTO_CREATE_CONTAINERS=false
COSMOS_HISTORY_MAX_TURNS=12
DEFAULT_LOCAL_USER_ID=local-dev
COSMOS_ENABLE_TTL=false
COSMOS_TTL_SECONDS=

==================================================
15. IMPORTANT IMPLEMENTATION RULES
==================================================

- Keep all code changes complete and runnable
- Print the full updated code for each changed file
- If the project already has config, routers, service classes, and models, integrate with that structure instead of creating random duplicates
- Do not remove existing features
- Do not rewrite unrelated code
- Keep naming clean and consistent
- Add comments only where useful
- If any existing file path differs, adapt intelligently
- At the end, provide:
  1. list of changed files
  2. full code for each changed file
  3. exact steps to run locally
  4. exact curl commands or test steps for validation

Please start by inspecting the existing repository structure and then make the full implementation accordingly.
