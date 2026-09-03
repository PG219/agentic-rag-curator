# Agentic RAG Curator

An agentic pipeline service for curating, indexing, and querying Retrieval-Augmented Generation (RAG) knowledge stores, backed by FastAPI, PostgreSQL, and OpenSearch.

---

## Project Structure

```text
.
├── src/
│   ├── __init__.py
│   ├── main.py              # FastAPI app entrypoint & lifespan
│   ├── config.py            # Settings via pydantic-settings
│   └── routers/
│       ├── __init__.py
│       └── health.py        # GET /health
├── .env.example             # Template for environment configuration
├── .gitignore               # Git ignore rules
├── compose.yml              # Postgres + OpenSearch services
├── pyproject.toml           # Package metadata & dependencies
├── Dockerfile               # Production container image
├── Makefile                 # Development task runner
└── README.md                # Project documentation
```

---

## Getting Started

### 1. Prerequisites
- Python >= 3.11
- Docker & Docker Compose (optional for local services)

### 2. Environment Setup

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Install dependencies:

```bash
pip install -e ".[dev]"
```

### 3. Spin up Storage Services (Docker)

Start PostgreSQL and OpenSearch:

```bash
make docker-up
# Or: docker compose up -d
```

### 4. Run Application

Run the FastAPI development server:

```bash
make dev
# Or: uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

Once running:
- **Interactive API Documentation:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **Alternative API Docs:** [http://localhost:8000/redoc](http://localhost:8000/redoc)
- **Health Check Endpoint:** [http://localhost:8000/health](http://localhost:8000/health)

---

## Testing & Quality

Run tests:
```bash
make test
```

Linting & Formatting:
```bash
make lint
make format
```
