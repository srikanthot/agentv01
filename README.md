# Streaming RAG Chatbot — SSE + FastAPI

> A streaming RAG chatbot: ask a question and watch a grounded, citation-backed answer stream in token-by-token over Server-Sent Events. FastAPI backend on the Microsoft Agent Framework, with a Streamlit UI.

![python](https://img.shields.io/badge/python-3.11-blue) ![cloud](https://img.shields.io/badge/Azure-commercial-0078D4) ![license](https://img.shields.io/badge/license-MIT-lightgrey)

## What this project is
A focused demonstration of a **low-latency streaming** RAG pipeline — the retrieval → confidence-gate → stream loop that makes a chatbot feel responsive while staying grounded.

## What it actually does (implemented)
- **SSE token streaming** with keepalive pings (no long blank waits).
- **Hybrid + vector retrieval** via Azure AI Search.
- **Confidence gate** — abstains when retrieval evidence is weak instead of guessing.
- **Citations** drawn only from retrieved chunks.
- **Microsoft Agent Framework SDK** orchestration; **Streamlit** front end.

## Architecture
```mermaid
flowchart LR
  UI[Streamlit UI] -->|/chat/stream| API[FastAPI]
  API --> RET[Retrieval · Azure AI Search]
  RET --> GATE{Confidence gate}
  GATE -->|ok| GEN[Azure OpenAI · stream tokens]
  GATE -->|weak| ABS[Abstain]
  GEN -->|SSE| UI
```

## Run it
```bash
cp .env.example .env
pip install -r backend/requirements.txt
uvicorn app.main:app --reload
streamlit run frontend/app.py
```

---
