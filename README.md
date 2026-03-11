# DocForge AI 📄

An AI-powered enterprise document generator that converts a natural language prompt into professional **Word documents** and **Excel spreadsheets** — with per-section refinement, Notion push, and full document history.

---

## Tech Stack

| Layer | Technology |
|---|---|
| LLM | Azure OpenAI (GPT-4o) via LangChain |
| Backend | FastAPI + uvicorn |
| Frontend | Streamlit |
| Database | PostgreSQL (psycopg2) |
| Cache / Rate Limit | Redis |
| Containerisation | Docker + Docker Compose |

---

## How It Works

```
User prompt (plain text)
    ↓
/plan       → LLM returns { title, sections[], doc_format }
    ↓
/questions  → LLM returns { "Section": ["Q1?", "Q2?"] }
    ↓
User fills answers
    ↓
/generate   → LLM returns JSON sections (Word) or JSON sheets (Excel)
    ↓
Export .docx / .xlsx  →  Save to PostgreSQL  →  Push to Notion (optional)
```

All LLM responses are converted to JSON before being stored or returned — except `/refine-section` which returns plain text directly.

---

## Project Structure

```
├── main.py                              # FastAPI — all 15 endpoints
├── mainstream.py                        # Streamlit UI
├── backend/
│   ├── database.py                      # PostgreSQL pool + CRUD
│   └── services/
│       ├── redis_service.py             # Redis: cache, throttle, backoff (single file)
│       ├── planner_agent.py             # Plans document structure
│       ├── question_agent.py            # Generates clarifying questions
│       ├── generator_agent.py           # Generates Word content
│       ├── excel_generator_agent.py     # Generates Excel sheet data
│       ├── excel_exporter.py            # JSON → .xlsx via openpyxl
│       ├── refinement_agent.py          # Rewrites a single section
│       ├── notion_service.py            # Notion API integration
│       └── langchain_service.py         # Shared Azure LLM instance
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env
```

---

## Setup

### Local

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Terminal 1
uvicorn main:app --reload --port 8080

# Terminal 2
streamlit run mainstream3.py
```

---

## Environment Variables

```env
# Azure OpenAI
AZURE_OPENAI_LLM_KEY=
AZURE_OPENAI_LLM_ENDPOINT=
AZURE_OPENAI_LLM_API_VERSION=
AZURE_OPENAI_LLM_DEPLOYMENT=

# PostgreSQL
POSTGRES_HOST=db          # use 'db' inside Docker, 'localhost' for local
POSTGRES_PORT=5432
POSTGRES_DB=docforge
POSTGRES_USER=postgres
POSTGRES_PASSWORD=

# Redis
REDIS_HOST=redis          # use 'redis' inside Docker, 'localhost' for local
REDIS_PORT=6379

# Notion (optional)
NOTION_TOKEN=
NOTION_PAGE_ID=
```

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| POST | `/plan` | Plan document structure from prompt |
| POST | `/questions` | Generate clarifying questions per section |
| POST | `/generate` | Generate full document content |
| POST | `/refine-section` | Rewrite one section (throttled: 10/min) |
| POST | `/export/excel` | Export JSON sheet data to .xlsx |
| POST | `/documents/save` | Save document to PostgreSQL |
| GET | `/documents` | List document history |
| GET | `/documents/{id}/download` | Download .docx or .xlsx |
| DELETE | `/documents/{id}` | Delete a document |
| POST | `/notion/push` | Push document to Notion |
| POST | `/notion/update` | Update existing Notion page |
| GET | `/health` | Health check |
| GET | `/redis/status` | Redis availability |

---

## Redis Features

- **Dedupe cache** — identical prompts return cached results instantly (plan/questions: 5 min TTL, generate: 60 min TTL)
- **Rate limiting** — max 10 refinements/min per section, max 3 Notion API calls/sec
- **Exponential backoff** — Notion API retries up to 4 attempts (1s → 2s → 4s → 8s)
- **Graceful degradation** — app runs normally if Redis is unavailable

---

## Database Schema

```sql
CREATE TABLE documents (
    id          SERIAL PRIMARY KEY,
    title       TEXT NOT NULL,
    doc_type    TEXT NOT NULL,       -- 'word' | 'excel'
    doc_format  TEXT NOT NULL,
    content     JSONB NOT NULL,      -- generated sections or sheet data
    file_bytes  BYTEA,               -- exported .docx / .xlsx binary
    file_ext    TEXT,                -- 'docx' | 'xlsx'
    created_at  TIMESTAMP DEFAULT NOW()
);