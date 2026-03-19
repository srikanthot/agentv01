You are modifying ONLY the frontend of this repository.

Repository context
- This repo has:
  - backend/ -> FastAPI backend
  - frontend/ -> Streamlit frontend
- The backend has already been upgraded (or is being upgraded) to support persistent chat history with conversation/thread APIs.
- The frontend must remain Streamlit in this task.
- Do NOT convert the frontend to React in this task.
- Do NOT modify backend code in this task.
- The frontend should adapt to the new backend capabilities while remaining compatible with local testing.

Primary goal
Upgrade the existing Streamlit frontend from a lightweight test UI into a polished chatbot UI that works with the backend’s persistent history model.

Target user experience
I want the Streamlit UI to behave more like ChatGPT:
1. A user opens the app
2. The user sees a left sidebar with:
   - New Chat button
   - previous chat threads
   - optional feedback link
   - simple backend status
3. The user can start a conversation
4. The user can ask follow-up questions in the same thread
5. The user can click New Chat to create a new thread
6. The user can click an older thread and reload that conversation
7. The app should hide backend implementation details from the UI
8. The app should still be good for local backend testing

Important constraints
1. Frontend only. Do NOT modify backend.
2. Keep Streamlit.
3. Reuse the current frontend structure if possible.
4. Remove any visible backend URL input/display from the UI.
5. Show only a small backend status indicator like:
   - Connected
   - Disconnected
   - Checking...
6. Add support for persistent thread history using backend APIs.
7. Keep the UI clean, professional, and production-shaped, even though it is Streamlit.
8. Preserve current ability to test answers and citations easily.
9. Keep the code easy to replace later with a React frontend if needed.

Assume the backend now supports or will support these endpoints
- GET /health
- POST /chat
- POST /chat/stream
- GET /conversations
- GET /conversations/{thread_id}/messages
- POST /conversations
- DELETE /conversations/{thread_id}
Optional:
- PATCH /conversations/{thread_id}

Important compatibility rule
The frontend must inspect the current backend contract and adapt safely.
If exact response/request shapes differ slightly, update the frontend service layer to match the actual backend code in this repo.

Frontend behavior requirements

A. Sidebar
Build a sidebar with:
1. App logo if already available
2. App title
3. New Chat button
4. Conversation history list
5. Optional Feedback link/button
6. Backend status indicator
7. Optional refresh history button

Rules:
- New Chat should create a new thread through backend if endpoint exists
- If backend conversation creation endpoint does not exist yet, generate a temporary local thread id only as a fallback
- Clicking a conversation in the sidebar should load its messages from backend
- Do not show backend URL in the UI
- Keep the sidebar neat and simple

B. Main chat area
Build a proper chat layout:
- welcome/empty state if no thread selected
- user chat bubbles
- assistant chat bubbles
- citations below assistant messages when available
- loading indicator while waiting
- input text area
- send button

Behavior:
- Enter to send
- allow multi-line input if practical in Streamlit
- auto-refresh/redisplay conversation correctly after each turn
- show helpful empty state text for first use

C. Thread model
The frontend must work with:
- user_id
- thread_id
- messages

Rules:
- maintain currently selected thread_id in Streamlit session state
- maintain loaded conversations list in session state
- maintain loaded message list for active thread in session state
- New Chat must create/reset current thread context
- old threads must remain visible in sidebar
- when user reopens a thread, load full message history from backend

D. User identity support for testing
The frontend should support local testing of user-based history.

Add optional support for:
- FRONTEND_DEBUG_USER_ID or similar env var
- send it as a header like X-Debug-User-Id when calling backend

Rules:
- if debug user id is configured, attach it to backend requests
- if not configured, do nothing
- do not expose this obviously in the UI unless helpful in a small dev-only area
- keep this implementation isolated in the API helper layer

E. API service layer
Refactor frontend code so API calls are not scattered around the Streamlit page.

Create or improve a service/helper module for:
- backend status check
- create conversation
- list conversations
- get messages for thread
- send non-streaming chat request
- optionally consume streaming response if current frontend already supports SSE

Requirements:
- read BACKEND_URL from env
- read FEEDBACK_URL from env if provided
- read optional DEBUG_USER_ID from env if provided
- centralize headers and request logic
- handle errors cleanly
- timeouts should be reasonable
- code should be easy to extend later

F. Streaming behavior
If the current frontend already has streaming support and it is stable, preserve it.
If streaming support is too brittle for the new history flow, use the existing backend in the safest way while keeping the service layer ready for streaming.

Priority order:
1. correct thread/history behavior
2. reliable citations display
3. streaming support if practical

G. Citation display
For assistant messages:
- show citations beneath the answer
- make them visually separate and readable
- if citation data includes source/page/section information, render that clearly
- if no citations exist, fail gracefully

Do not make citations ugly or cluttered.

H. Session state design
Use Streamlit session state cleanly.

Suggested session state keys:
- current_thread_id
- current_user_id
- conversations
- messages
- backend_status
- is_loading
- feedback_url
- selected_thread_title

Rules:
- avoid ad-hoc state keys spread randomly
- initialize state in one place
- keep reruns predictable
- preserve selected thread across reruns within a Streamlit session

I. UI polish
Keep it Streamlit, but make it look cleaner and more product-like:
- clear title/header
- clean chat spacing
- readable citations
- sidebar organization
- no developer clutter on main page
- optional small “Testing Mode” note only if debug user id is being used
- status badge only, not backend URL

J. Delete / manage conversation behavior
If backend supports delete:
- add a small delete/archive affordance per conversation or for selected conversation
- refresh sidebar after delete
- if deleted selected thread is active, clear current selection gracefully

If backend does not support delete yet:
- do not fake it in the frontend

K. Required environment variables
Use or create frontend/.env.example entries such as:
- BACKEND_URL=http://localhost:8000
- FEEDBACK_URL=
- DEBUG_USER_ID=local-dev

If the current frontend env naming differs, preserve compatibility where practical.

L. File structure
Inspect the current frontend folder and refactor cleanly.
Likely keep or create:
- frontend/app.py
- frontend/requirements.txt
- optional helper modules like:
  - frontend/api_client.py
  - frontend/ui_helpers.py
  - frontend/state.py

Do not over-engineer, but do separate concerns cleanly.

M. Backward compatibility
The frontend must still work even if:
- no previous conversation exists
- backend returns empty conversation list
- backend health is down
- backend history endpoints are temporarily unavailable

In those cases:
- show a clean error or empty state
- avoid crashing
- keep chat testing possible if /chat still works

N. Deliverables after changes
After making the changes, provide:
1. List of all created/modified frontend files
2. Full updated code for each changed file
3. Summary of frontend architecture changes
4. Sample frontend/.env values
5. Local run commands
6. Manual test plan
7. Any assumptions made about backend response shapes

O. Manual test plan
After implementation, I want to test:
1. Start backend locally
2. Start Streamlit frontend locally
3. Confirm backend status is shown
4. Create a New Chat
5. Send first question
6. See answer and citations
7. Send follow-up in same thread
8. Confirm continuity
9. Create another New Chat
10. Confirm second thread appears separately
11. Reopen first thread from sidebar
12. Confirm full old history loads
13. Restart backend
14. Reload frontend and confirm history can still be fetched from backend
15. Change DEBUG_USER_ID and confirm a different user’s history is isolated

P. What NOT to do
- Do NOT convert to React
- Do NOT hardcode backend URL
- Do NOT show backend URL prominently in the UI
- Do NOT keep history only in Streamlit memory
- Do NOT duplicate backend storage logic in frontend
- Do NOT modify backend code in this task

Now inspect the current frontend code under frontend/ and implement these changes end-to-end while keeping Streamlit as the frontend.
