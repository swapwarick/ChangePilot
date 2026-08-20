<div align="center">
  <img src="logo.jpg" alt="ChangePilot" width="96" style="border-radius: 18px;" />
  <h1>ChangePilot</h1>
  <p>Deterministic Change Impact Analysis with Explainable AI</p>

[![Live Demo](https://img.shields.io/badge/Live%20Demo-changepilot--frontend.onrender.com-blue?style=flat-square)](https://changepilot-frontend.onrender.com/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?style=flat-square)](https://fastapi.tiangolo.com)
[![Next.js](https://img.shields.io/badge/Next.js-15.x-000000?style=flat-square)](https://nextjs.org/)
[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?style=flat-square)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)

</div>

---

ChangePilot evaluates code changes, calculates architectural blast radius, executes deterministic risk formulas, and generates evidence-grounded AI explanations across local repositories, git diffs, and GitHub Pull Requests.

**Live deployment:** [https://changepilot-frontend.onrender.com/](https://changepilot-frontend.onrender.com/)

---

## Table of Contents

- [Core Philosophy](#core-philosophy)
- [Key Features](#key-features)
- [Architecture](#architecture)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [API Reference](#api-reference)
- [Deployment](#deployment)

---

## Core Philosophy

Traditional AI code analysis often hallucinates risk levels or gives inconsistent outputs between runs. ChangePilot addresses this with strict Clean Architecture boundaries:

1. **Deterministic Risk Calculation.** Mathematical risk scoring (0–100) based on code complexity, dependency centrality, AST diffs, database migrations, security markers, and test coverage signals.
2. **AI Explains, Never Scores.** Large Language Models are used only to synthesize and explain deterministic evidence. AI cannot alter risk scores or invent findings.
3. **Local and Cloud First.** First-class support for local models (Ollama, LM Studio, vLLM) and cloud providers (OpenAI, Anthropic Claude, Google Gemini, Groq, Together AI, OpenRouter).

---

## Key Features

### Deterministic Risk and Blast Radius Engine

- Multi-factor scoring combining blast radius size, graph centrality (PageRank, betweenness), critical file paths, and test coverage
- Granular security detection: authentication, authorization, cryptography, credentials, session handling, permissions, and secrets
- Automatic flagging of schema migrations, ORM entity changes, and breaking database queries

### Multilingual AST Code Intelligence (Tree-sitter)

- Native language parsers for Python, TypeScript, JavaScript, Java, Go, Rust, C/C++, C#, Ruby, Kotlin, Swift, PHP, Scala, and HTML/CSS
- Extracts function definitions, class hierarchies, import graphs, method calls, and decorators from actual parse trees
- Detects structural changes: renamed functions, new public APIs, removed interfaces

### Repository Knowledge Graph

- Persistent in-database graph capturing module-level dependencies and file-to-file relationships
- Graph health metrics: cyclomatic complexity, cohesion scores, coupling density, God-module detection, circular dependency tracking
- Graph diffing between commits: added nodes, removed edges, newly orphaned modules

### Evidence Ledger Architecture

Every risk score is backed by an immutable evidence ledger containing:

- **Facts** — verified statements extracted directly from code
- **Inferences** — logical conclusions derived from the dependency graph
- **Recommendations** — actionable review guidance tied to specific evidence

### AI Report Generation

- Configurable LLM provider routing with fallback chains
- Grounded prompting: AI is constrained to the evidence ledger and cannot fabricate findings
- Deterministic fallback report when no LLM is configured

### Export System

Exports analysis results in four formats: PDF (ReportLab, enterprise-grade), JSON (complete machine-readable snapshot), CSV (tabular data as ZIP), and Markdown (GitHub/PR-friendly).

### Enterprise Risk Policy Engine

- Configurable YAML-style risk policies with weighted signals
- Policy versioning and comparison tooling
- A/B testing framework for UI experiments and policy evaluation

---

## Architecture

```
changepilot/
├── backend/
│   ├── app/
│   │   ├── analysis/           # AST parsing, graph building, risk engine
│   │   ├── api/routes/         # FastAPI route handlers
│   │   ├── core/               # Auth, config, security
│   │   ├── database/           # SQLAlchemy ORM tables and session management
│   │   ├── models/             # Pydantic request/response schemas
│   │   ├── providers/          # LLM provider registry with fallback chains
│   │   ├── repositories/       # Data access layer
│   │   └── services/           # Export, report, storage services
│   └── alembic/                # Database migrations
└── frontend/
    ├── app/                    # Next.js App Router
    ├── components/             # Shared UI components
    ├── features/               # Feature modules (dashboard, analysis, export)
    ├── lib/                    # Utilities: API config, auth, A/B testing
    └── types/                  # TypeScript API type definitions
```

### Technology Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 15, React 19, TypeScript, Tailwind CSS |
| Backend | FastAPI, Python 3.12, SQLAlchemy 2.0 (async) |
| Database | PostgreSQL with Alembic migrations |
| AST Parsing | Tree-sitter (15+ language grammars) |
| AI Providers | OpenAI, Anthropic, Gemini, Groq, Ollama, vLLM |
| Infrastructure | Render (frontend + backend), Redis (job queue) |

---

## Quick Start

### Prerequisites

- Python 3.12+
- Node.js 20+
- PostgreSQL 15+

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your DATABASE_URL, JWT_SECRET_KEY, and optional AI provider keys

# Apply migrations
alembic upgrade head

# Start the API server
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install

# Configure environment
cp .env.example .env.local
# Set NEXT_PUBLIC_API_BASE_URL=http://localhost:8000

npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

---

## Configuration

### Backend Environment Variables

| Variable | Required | Description |
|---|---|---|
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `JWT_SECRET_KEY` | Yes | Secret key for JWT signing (min 32 chars) |
| `OPENAI_API_KEY` | No | OpenAI API key for AI report generation |
| `ANTHROPIC_API_KEY` | No | Anthropic Claude API key |
| `GEMINI_API_KEY` | No | Google Gemini API key |
| `GROQ_API_KEY` | No | Groq API key |
| `OLLAMA_BASE_URL` | No | Ollama endpoint for local model inference |
| `REDIS_URL` | No | Redis connection for background job workers |

### Frontend Environment Variables

| Variable | Required | Description |
|---|---|---|
| `NEXT_PUBLIC_API_BASE_URL` | Yes (local) | Backend API base URL |

On Render, the frontend auto-detects the backend URL from `window.location`.

---

## API Reference

The backend exposes a RESTful API documented at `/docs` (Swagger UI) when running locally.

### Core Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/repositories` | List connected repositories |
| `POST` | `/repositories` | Register a new repository |
| `GET` | `/analysis` | List analysis runs for a repository |
| `POST` | `/analysis/changes` | Run a new change analysis |
| `GET` | `/analysis/{id}` | Get a specific analysis result |
| `GET` | `/analysis/{id}/export/{format}` | Export analysis (pdf, json, csv, markdown) |
| `GET` | `/jobs/repositories/{id}/knowledge-graph` | Get repository knowledge graph |
| `GET` | `/risk-policies` | List risk policies |
| `POST` | `/auth/guest` | Create a guest session |
| `POST` | `/auth/register` | Register a user account |
| `POST` | `/auth/login` | Authenticate and obtain tokens |

---

## Deployment

ChangePilot is designed for zero-configuration deployment on Render.

### Render Setup

1. Fork this repository
2. Create a PostgreSQL database on Render
3. Deploy the backend as a Web Service:
   - Build command: `pip install -r requirements.txt && alembic upgrade head`
   - Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
4. Deploy the frontend as a Static Site or Web Service:
   - Build command: `npm install && npm run build`
   - Start command: `npm start`
5. Set environment variables in each service's dashboard

---

## License

MIT License. See [LICENSE](LICENSE) for details.
