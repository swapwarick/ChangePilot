<div align="center">

# 🚀 ChangePilot

### *Deterministic Change Impact Analysis with Explainable AI*

[![Live Demo](https://img.shields.io/badge/Live%20Demo-changepilot--frontend.onrender.com-blue?style=for-the-badge&logo=render&logoColor=white)](https://changepilot-frontend.onrender.com/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Next.js](https://img.shields.io/badge/Next.js-15.x%20%7C%20React%2019-000000?style=for-the-badge&logo=next.js&logoColor=white)](https://nextjs.org/)
[![Tree-sitter](https://img.shields.io/badge/AST-Tree--sitter-333333?style=for-the-badge&logo=tree-sitter&logoColor=white)](https://tree-sitter.github.io)
[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)

<p align="center">
  <strong>ChangePilot</strong> evaluates code changes, calculates architectural blast radius, executes deterministic risk formulas, and generates evidence-grounded AI explanations across local repositories, git diffs, and GitHub Pull Requests.
</p>

[**Explore Live Deployment**](https://changepilot-frontend.onrender.com/) • [**Key Features**](#-key-features) • [**Architecture**](#-architecture) • [**Quick Start**](#-quick-start) • [**Configuration**](#-configuration) • [**API Reference**](#-api-reference)

---

</div>

## 🌐 Live Deployment

ChangePilot is deployed live and accessible in the cloud:

> **Frontend Application:** [https://changepilot-frontend.onrender.com/](https://changepilot-frontend.onrender.com/)  
> **Infrastructure:** Hosted on Render with Next.js frontend, FastAPI backend, PostgreSQL, and Redis job workers.

---

## 💡 Core Philosophy

Traditional AI code analysis often hallucinates risk levels or gives inconsistent outputs between runs. ChangePilot solves this with strict **Clean Architecture boundaries**:

1. **Deterministic Risk Calculation:** Mathematical risk scoring (0–100) based strictly on code complexity, dependency centrality, AST diffs, database migrations, security markers, and test coverage signals.
2. **AI Explains, Never Scores:** Large Language Models (LLMs) are used *only* to synthesize, summarize, and explain deterministic evidence. AI cannot alter risk scores or invent findings.
3. **Local & Cloud First:** First-class support for local models (Ollama, LM Studio, vLLM) and cloud providers (OpenAI, Anthropic Claude, Google Gemini, Groq, Together AI, OpenRouter).

---

## ✨ Key Features

### 🔍 Deterministic Risk & Blast Radius Engine
- **Multi-Factor Scoring:** Combines blast radius size, graph centrality (PageRank, betweenness), critical file paths, and test coverage.
- **Granular Security Detection:** Detects changes in authentication, authorization, cryptography, credentials, session handling, permissions, and secrets.
- **Database & Schema Impact:** Automatically flags schema migrations, ORM entity changes (`@Entity`, Room, SQLAlchemy, Prisma), and breaking queries.

### 🌳 Multilingual AST Code Intelligence (Tree-sitter)
- **Deep Syntax Tree Parsing:** Extracts classes, interfaces, composables, function signatures, database models, and route declarations.
- **Language Support:** Native parsers for **Python**, **TypeScript**, **JavaScript**, **Kotlin** (`.kt`, `.kts`), and **Java** (`.java`).

### 🕸️ Interactive Dependency & Knowledge Graph
- **React Flow (`@xyflow/react`) Visualization:** Interactive nodes, edges, module clustering, and flow tracing from entry points to sinks.
- **Graph Backends:** Neo4j graph database support with automatic fallback to high-speed in-memory NetworkX graphs.

### 🤖 Hot-Swappable AI Provider Hub
- **Universal Provider Adapter:** Seamlessly switch between OpenAI, Anthropic, Gemini, Ollama, Groq, Together AI, OpenRouter, or any OpenAI-compatible endpoint.
- **Runtime Reconfigurability:** Update fallback chains, priorities, temperature, and tokens dynamically without service restarts.

### 🛡️ Risk Policies & Quality Gates
- **Custom Policy Rules:** Define risk thresholds per team or service.
- **Automated CI/CD Quality Gates:** Enforce `PASS`, `WARNING`, or `BLOCK` decisions on PRs based on deterministic risk metrics.

### 🐙 Git, GitHub & Local Analysis
- **GitHub Integration:** Analyze repositories and pull requests directly via GitHub URLs or webhooks.
- **Local Directory & Diff Upload:** Inspect local repositories, zipped codebases, or raw `.patch` / `.diff` files.

### 📊 Comprehensive Reporting & Export
- **Multi-Format Export:** Export audits and change impact reports to **PDF** (via ReportLab), **JSON**, or **Markdown**.

---

## 🏗️ Architecture

```mermaid
flowchart TB
    subgraph Client["Frontend (Next.js 15 + React 19)"]
        UI[Dashboard & UI Components]
        GraphUI[React Flow Dependency Graph]
        AuthUI[Better Auth / JWT Client]
    end

    subgraph API["Backend API (FastAPI)"]
        Routes[API Routes / Controllers]
        AuthService[Auth & Quota Management]
        JobQueue[Redis Async Job Queue]
    end

    subgraph Engine["Core Analysis Engine"]
        TreeSitter[Tree-sitter AST Parser<br/>Python, TS, JS, Java, Kotlin]
        GraphBuilder[Knowledge Graph Builder<br/>Neo4j / In-Memory]
        RiskEngine[Deterministic Risk Engine<br/>Security, Schema, Centrality Rules]
    end

    subgraph AI["AI Provider Strategy Layer"]
        Registry[AI Provider Registry]
        Providers[OpenAI • Gemini • Anthropic<br/>Ollama • Groq • LM Studio • vLLM]
    end

    subgraph Data["Persistence Layer"]
        Postgres[(PostgreSQL / SQLite)]
        Neo4jDB[(Neo4j Graph DB)]
        RedisDB[(Redis Cache & Queue)]
    end

    UI -->|HTTP / REST| Routes
    Routes --> AuthService
    Routes --> JobQueue
    JobQueue --> Engine
    Engine --> TreeSitter
    Engine --> GraphBuilder
    Engine --> RiskEngine
    RiskEngine -->|Deterministic Evidence| Registry
    Registry --> Providers
    Providers -->|Synthesized Explanation| Routes
    AuthService --> Postgres
    GraphBuilder --> Neo4jDB
    JobQueue --> RedisDB
```

---

## 🛠️ Technology Stack

| Layer | Technology |
|---|---|
| **Frontend** | [Next.js 15](https://nextjs.org/), [React 19](https://react.dev/), [TypeScript](https://www.typescriptlang.org/), [Tailwind CSS](https://tailwindcss.com/), [@xyflow/react](https://reactflow.dev/), [TanStack Query](https://tanstack.com/query), [Zustand](https://zustand-demo.pmnd.rs/), [Lucide Icons](https://lucide.dev/) |
| **Backend** | [FastAPI](https://fastapi.tiangolo.com/), [Pydantic v2](https://docs.pydantic.dev/), [SQLAlchemy 2.0 (asyncio)](https://www.sqlalchemy.org/), [Alembic](https://alembic.sqlalchemy.org/), [Uvicorn](https://www.uvicorn.org/) |
| **Code Parsing** | [Tree-sitter](https://tree-sitter.github.io/) (Python, TypeScript, JavaScript, Java, Kotlin) |
| **Graph & Storage** | [Neo4j](https://neo4j.com/), [PostgreSQL](https://www.postgresql.org/) (with SQLite local fallback), [Redis](https://redis.io/) |
| **AI Integration** | OpenAI API, Anthropic Claude, Google Gemini, Ollama, Groq, Together AI, OpenRouter, vLLM |
| **Reporting & Export** | [ReportLab](https://www.reportlab.com/) (PDF Generation), JSON, Markdown |
| **Deployment** | [Docker](https://www.docker.com/), [Docker Compose](https://docs.docker.com/compose/), [Render](https://render.com/) |

---

## 🚀 Quick Start

### Option 1: Docker Compose (Recommended)

Run the entire stack (PostgreSQL, Neo4j, Redis, Backend, and Frontend) with a single command:

```bash
# 1. Clone the repository
git clone https://github.com/your-username/ChangePilot.git
cd ChangePilot

# 2. Copy environment file
cp .env.example .env

# 3. Start all services
docker compose up --build
```

- **Frontend App:** [http://localhost:3000](http://localhost:3000)
- **Backend API Docs:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **Neo4j Browser:** [http://localhost:7474](http://localhost:7474)

---

### Option 2: Local Development Setup

#### 1. Backend (FastAPI)

```bash
cd backend

# Create & activate virtual environment
python -m venv .venv
# On Windows (PowerShell):
.\.venv\Scripts\Activate.ps1
# On Linux/macOS:
# source .venv/bin/activate

# Install dependencies (including dev tools)
pip install -e ".[dev]"

# Run database migrations
alembic upgrade head

# Start FastAPI server with live reload
uvicorn app.main:app --reload --port 8000
```

#### 2. Frontend (Next.js)

```bash
# In a new terminal
cd frontend

# Install dependencies
npm install

# Start Next.js development server
npm run dev
```

The application will be running at [http://localhost:3000](http://localhost:3000).

---

## ⚙️ Configuration

ChangePilot is configured via environment variables. Create a `.env` file in the root directory:

```env
# Application
APP_ENV=development
BACKEND_CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000

# Database (PostgreSQL with SQLite local dev fallback)
DATABASE_URL=postgresql+psycopg://changepilot:changepilot@localhost:5432/changepilot

# Graph Database (Neo4j)
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=changepilot-password

# Cache & Job Queue (Redis)
REDIS_URL=redis://localhost:6379/0

# Authentication
JWT_SECRET_KEY=generate-a-secure-secret-with-openssl-rand-hex-32
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
REFRESH_TOKEN_EXPIRE_DAYS=30

# Storage Quota & Mode
STORAGE_QUOTA_BYTES=31457280
IS_CLOUD=false

# Frontend Configuration
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
NEXT_PUBLIC_IS_CLOUD=false
BETTER_AUTH_SECRET=generate-a-secure-secret
BETTER_AUTH_URL=http://localhost:3000
```

---

## 📡 API Reference

Interactive Swagger documentation is available at `/docs` when running the backend.

### Key Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Healthcheck and service connectivity status |
| `POST` | `/auth/register` | Register a new user account |
| `POST` | `/auth/login` | Authenticate and obtain JWT tokens |
| `POST` | `/analysis/run` | Execute change impact analysis on a repository |
| `GET` | `/analysis/{id}` | Retrieve analysis results, risk scores, and evidence |
| `GET` | `/analysis/{id}/export/pdf` | Export analysis report as a formatted PDF |
| `GET` | `/analysis/{id}/export/markdown` | Export analysis summary as Markdown |
| `POST` | `/github/analyze-pr` | Analyze a GitHub Pull Request by URL |
| `POST` | `/local/analyze-path` | Analyze a local directory path (self-hosted mode) |
| `GET` | `/ai-providers` | List configured AI providers and priority chains |
| `POST` | `/ai-providers` | Add or update an AI provider configuration |
| `GET` | `/risk-policies` | List active risk policies and quality gate thresholds |
| `POST` | `/risk-policies` | Create or customize risk policy rules |

---

## 🧪 Testing & Code Quality

ChangePilot includes comprehensive test suites for AST parsing, risk rules, graph centrality, and API routes.

```bash
# Run backend tests
cd backend
pytest

# Format & Lint
ruff format app tests
ruff check app tests

# Run frontend typecheck & linting
cd ../frontend
npm run typecheck
npm run lint
```

---

## ☁️ Deployment (Render)

ChangePilot includes an infrastructure-as-code **Render Blueprint** (`render.yaml`).

1. Fork or push this repository to GitHub.
2. Log in to [Render](https://render.com/) and go to **Dashboard → New → Blueprint**.
3. Connect your repository.
4. Render will automatically provision:
   - `changepilot-api` (FastAPI Docker Web Service)
   - `changepilot-frontend` (Next.js Docker Web Service)
   - `changepilot-db` (PostgreSQL Database)
   - `changepilot-redis` (Redis Instance)
5. Set any custom secrets (`NEO4J_URI`, `JWT_SECRET_KEY`) in the Render dashboard.

---

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
