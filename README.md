<div align="center">
  <img src="logo.jpg" alt="ChangePilot" width="88" style="border-radius: 18px;" />

  <h1>ChangePilot</h1>

  <p><strong>ChangePilot tells engineering teams what a code change can break — before it reaches production.</strong></p>

  [![Live Demo](https://img.shields.io/badge/Live%20Demo-changepilot--frontend.onrender.com-0ea5e9?style=flat-square)](https://changepilot-frontend.onrender.com/)
  [![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?style=flat-square)](https://fastapi.tiangolo.com)
  [![Next.js](https://img.shields.io/badge/Next.js-15-000000?style=flat-square)](https://nextjs.org/)
  [![Python](https://img.shields.io/badge/Python-3.12+-3776AB?style=flat-square)](https://www.python.org/)
  [![License](https://img.shields.io/badge/License-MIT-16a34a?style=flat-square)](LICENSE)

  **[Live Demo](https://changepilot-frontend.onrender.com/) · [Source](https://github.com/swapwarick/ChangePilot)**

</div>

---

ChangePilot analyzes git diffs, AST structure, dependency graphs, blast radius, test coverage gaps, and security signals to produce a **deterministic change-risk assessment**. An LLM then explains that assessment in plain language.

**AI explains. Deterministic evidence decides.**

---

## The Problem

Standard CI tells you whether tests passed. It does not tell you:

- **What else is affected** — which files and modules are transitively impacted beyond those you directly changed
- **How far the change propagates** — the architectural blast radius through dependency chains
- **Which structural dependencies are involved** — hub nodes, bridge chokepoints, high fan-out modules
- **Whether tests cover the affected area** — test gap detection based on repository structure
- **Why the change carries risk** — security signals, database schema changes, API contract breaks, missing rollback plans

ChangePilot answers all five questions using only verifiable repository evidence.

---

## How It Works

```
Git Diff / Local Repository
          │
          ▼
   Diff Parser (unified diff → changed files + line ranges)
          │
          ▼
   Tree-sitter AST Parser (imports, classes, functions, DB models)
          │
          ▼
   Dependency Graph Builder (nodes: files, modules, functions, services)
          │
          ▼
   Blast Radius Traversal (BFS up to depth 3, hub + bridge node detection)
          │
          ▼
   Deterministic Risk Engine (weighted rule set → reproducible 0–100 score)
          │
          ▼
   Evidence Ledger (FACT → INFERENCE → RECOMMENDATION)
          │
          ▼
   AI Explanation Layer (LLM synthesizes evidence; does not alter the score)
          │
          ▼
   Risk Report + Export (PDF / JSON / CSV / Markdown)
```

The score is computed **before** any LLM is invoked. AI is only called to explain what the engine already found.

---

## Why ChangePilot?

### The score is not AI-generated

Most AI code review tools use an LLM to assess risk. LLMs produce non-deterministic outputs — the same change analyzed twice can return different scores. That is inappropriate for engineering decisions.

ChangePilot separates two concerns that should never be mixed:

| Component | Responsibility |
|---|---|
| Deterministic Risk Engine | Scores the change using a weighted rule set applied to measurable repository evidence |
| AI Explanation Layer | Reads the finalized evidence ledger and produces a human-readable report |

The LLM cannot modify the risk score. It reads facts and explains them.

### The output is auditable

Every risk score is backed by a structured evidence ledger. Each item in the ledger contains:

- **FACT** — a directly measured observation (e.g. "7 files modified", "authentication module changed")
- **INFERENCE** — a deterministic conclusion derived from evidence (e.g. "blast radius spans 4 modules")
- **RECOMMENDATION** — an engineering action classified as `EVIDENCE_BACKED`, `POLICY_BASED`, or `GENERIC_BEST_PRACTICE`

This makes the report traceable: you can verify every claim against the repository.

---

## Capabilities

### Deterministic Risk Scoring

- Risk index from 0–100 computed by a weighted rule set. Score is always reproducible for the same input.
- Diminishing-returns normalization prevents evidence double-counting.
- Four risk levels: `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`.
- Evidence completeness metric indicates how much of the repository was parseable.
- The system explicitly records when coverage data is unavailable rather than treating it as zero risk.

### Risk Signal Categories

| Category | Signals |
|---|---|
| **Security** | Authentication change, authorization change, credential handling, session management, cryptography, system permissions, secrets / `.env` files |
| **Database** | Schema changes (ORM models, `.sql` files, Alembic migrations), migration scripts, destructive operations (`DROP COLUMN`, `DROP TABLE`) without rollback |
| **API Contracts** | Route definition changes, deleted public endpoints, OpenAPI / GraphQL / Protobuf changes |
| **Architecture** | Large blast radius (downstream dependency count), multi-module impact, hub node in impact set, bridge / chokepoint node modified, circular imports, high fan-out modules, critical business components (auth, payment, billing, order) |
| **Infrastructure** | Dockerfile changes, CI/CD workflow changes (`.github/workflows/`), Terraform (`.tf`), Kubernetes manifests, environment variable configuration |
| **Testing** | No related test changes alongside source changes (structural heuristic, not coverage instrumentation) |
| **Dependencies** | Package manager files modified (`package.json`, `requirements.txt`, `build.gradle`, `pom.xml`) |

### Blast Radius Analysis

- BFS traversal of the in-memory dependency graph up to depth 3.
- Hub node detection: nodes ranked by total degree (in + out). High-degree nodes have many consumers; changes propagate widely.
- Bridge node detection: betweenness centrality identifies architectural chokepoints that connect otherwise separate subsystems.
- Analysis depth levels: `minimal` (fast, no graph traversal), `standard` (full graph + blast radius), `deep` (standard + execution flow tracing).

### AST Code Intelligence

The Tree-sitter parser extracts:

- Package declarations, imports (direct, aliased, relative)
- Class hierarchies, interface implementations, superclasses
- Function and method definitions, annotations
- Database entity markers (`@Entity`, `@Table`, SQLAlchemy `Model`, Room `@Database`)
- API route registrations
- Framework signals (Composable annotations, entrypoint heuristics)

### Repository Knowledge Graph

- Persistent in-database graph (PostgreSQL) of module-level dependencies and file relationships.
- Health metrics: circular dependency detection, orphan candidate detection, dead code symbols, god class detection (high method count), high fan-out / fan-in files, potential test gap heuristics.
- Architectural violation detection: coupling density, cyclomatic complexity indicators.

### GitHub Integration

Connect with a GitHub personal access token. Select repository, branches, commits, or pull requests directly in the UI. The diff is retrieved via GitHub API and passed to the analysis pipeline.

### Local Repository Analysis

Scan any local directory or git repository from disk without GitHub credentials. Select branches and compare any two commits using the local git binary.

### AI Report Generation

When an LLM provider is configured, it receives only the finalized evidence ledger as grounding context. It cannot alter risk scores or invent findings not present in the ledger. If no provider is configured, a deterministic fallback report is generated from the evidence.

Supported provider kinds:

| Kind | Notes |
|---|---|
| `openai_compatible` | Any OpenAI-compatible `/v1/chat/completions` endpoint (OpenAI, Azure OpenAI, Together AI, etc.) |
| `ollama` | Local Ollama instance (any model) |
| `groq` | Groq API |
| `openrouter` | OpenRouter |
| `custom_rest` | Custom REST endpoint |

### Risk Policy Engine

Configurable risk policies with weighted signals. Policies can be compared and versioned. The UI includes a policy comparison tool and branch impact simulator.

### Export System

Exports are generated from the canonical `ChangeAnalysisResult` — no data is re-calculated during export.

| Format | Description |
|---|---|
| PDF | Multi-page ReportLab document with evidence table, risk breakdown, and recommendations |
| JSON | Complete machine-readable analysis snapshot |
| CSV | Tabular data (risk breakdown + evidence statements) delivered as a ZIP |
| Markdown | GitHub-compatible report suitable for PR comments |

---

## Supported Languages

| Language | AST Parser | Dependency Analysis | Notes |
|---|---|---|---|
| Python | Full (Tree-sitter) | Yes | Imports, classes, functions |
| TypeScript | Full (Tree-sitter) | Yes | Imports, classes, interfaces, functions |
| TSX | Full (Tree-sitter) | Yes | Same as TypeScript |
| JavaScript | Full (Tree-sitter) | Yes | Shares TypeScript grammar |
| Kotlin / KTS | Full (Tree-sitter + lexical fallback) | Yes | Classes, Composables, `@Entity`, Android Manifest |
| Java | Tree-sitter (optional install) | Partial | Requires `tree-sitter-java` binding |
| Other source files (.rs, .go, .cs, .rb, .php, .swift, .scala, .m) | File-level only (GenericParser) | No | Recognized and classified; no symbol extraction |

**Limitation:** Go, Rust, C#, Ruby, PHP, Swift, and Scala are recognized and classified but do not receive AST-level symbol extraction or dependency graph edges. Risk signals that depend on path/file-name matching (security, database, infrastructure rules) still apply.

---

## Technical Architecture

```
changepilot/
├── backend/
│   ├── app/
│   │   ├── analysis/          # Diff parser, AST parser, blast radius, file classifier
│   │   ├── api/routes/        # FastAPI route handlers (auth, analysis, export, github, local, jobs, policies)
│   │   ├── core/              # Configuration, auth, JWT
│   │   ├── database/          # SQLAlchemy 2.0 async ORM, Alembic migrations
│   │   ├── graph/             # Knowledge graph, blast radius, centrality, Neo4j engine (optional)
│   │   ├── models/            # Pydantic schemas for analysis, risk, graph, export
│   │   ├── providers/         # LLM provider registry (Ollama, OpenAI-compatible, Groq, OpenRouter)
│   │   ├── repositories/      # Data access layer
│   │   ├── risk/              # Deterministic risk engine + rule registry
│   │   └── services/          # Export service (PDF, JSON, CSV, Markdown)
│   └── alembic/               # Database migrations
└── frontend/
    ├── app/                   # Next.js 15 App Router
    ├── components/            # Shared UI components
    ├── features/              # Dashboard, analysis, export, GitHub integration
    ├── lib/                   # API config, auth client, A/B testing framework
    └── types/                 # TypeScript API type definitions
```

### Technology Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 15, React 19, TypeScript |
| Backend | FastAPI (Python 3.12), async SQLAlchemy 2.0 |
| Primary Database | PostgreSQL (Alembic migrations) |
| Graph (optional) | Neo4j Aura (Cypher blast radius traversal; in-memory fallback used by default) |
| AST Parsing | Tree-sitter (`tree-sitter-python`, `tree-sitter-typescript`, `tree-sitter-javascript`, `tree-sitter-kotlin`, `tree-sitter-java`) |
| GitHub API | GitHub REST API v3 via personal access token |
| LLM Providers | Ollama, OpenAI-compatible, Groq, OpenRouter |
| Job Queue | Redis (background analysis jobs) |
| Deployment | Render (Docker, Blueprint YAML included) |

---

## Quick Start

### Prerequisites

- Python 3.12+
- Node.js 20+
- PostgreSQL 15+
- Git (required for local repository scanning)

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate         # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env: set DATABASE_URL, JWT_SECRET_KEY (min 32 chars)
# Optional: OPENAI_API_KEY, GROQ_API_KEY, OLLAMA_BASE_URL, NEO4J_URI

alembic upgrade head

uvicorn app.main:app --reload --port 8000
```

API available at `http://localhost:8000`. Swagger UI at `http://localhost:8000/docs`.

### Frontend

```bash
cd frontend
npm install

cp .env.example .env.local
# Set: NEXT_PUBLIC_API_BASE_URL=http://localhost:8000

npm run dev
```

Open `http://localhost:3000`.

### Run Your First Analysis

1. Register or sign in (or use guest mode).
2. Click **Scan Repository / Local Folder**.
3. Choose **GitHub** (enter a personal access token) or **Local** (enter the path to a local git repo).
4. Select two commits or branches to compare.
5. Submit — the analysis pipeline runs and the result appears in the dashboard.

---

## Environment Variables

### Backend

| Variable | Required | Description |
|---|---|---|
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `JWT_SECRET_KEY` | Yes | JWT signing key (minimum 32 characters) |
| `OPENAI_API_KEY` | No | For OpenAI-compatible AI reports |
| `GROQ_API_KEY` | No | For Groq AI reports |
| `OLLAMA_BASE_URL` | No | Local Ollama endpoint (e.g. `http://localhost:11434`) |
| `NEO4J_URI` | No | Neo4j Aura URI (optional; in-memory graph used if absent) |
| `NEO4J_USER` | No | Neo4j username |
| `NEO4J_PASSWORD` | No | Neo4j password |
| `REDIS_URL` | No | Redis connection string for background job workers |

### Frontend

| Variable | Required | Description |
|---|---|---|
| `NEXT_PUBLIC_API_BASE_URL` | Yes (local) | Backend API URL. Auto-detected on Render. |

---

## Deployment

A Render Blueprint (`render.yaml`) is included. It provisions:

- FastAPI backend (Docker)
- Next.js frontend (Docker)
- PostgreSQL database
- Redis instance

```bash
# 1. Push to GitHub
# 2. Render Dashboard → New → Blueprint → connect repo
# 3. Set NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD in Render dashboard (if using Neo4j)
# 4. All other secrets are auto-generated or wired between services
```

---

## Project Status

**Beta — active development.** Deployed and functional at [changepilot-frontend.onrender.com](https://changepilot-frontend.onrender.com/).

### Verified and working

- GitHub repository connection (branches, commits, pull requests)
- Local repository scanning (local git diff)
- AST parsing for Python, TypeScript/TSX, JavaScript, Kotlin, Java
- Dependency graph construction and persistence
- Blast radius traversal with hub and bridge node detection
- Deterministic risk scoring with full evidence ledger
- AI report generation (Ollama, OpenAI-compatible, Groq, OpenRouter)
- Export to PDF, JSON, CSV, Markdown
- Risk policy configuration and comparison
- Analysis history with persistent storage

### Screenshots

> No screenshots are currently stored in this repository. Screenshots of the risk dashboard, dependency graph, evidence report, and export output should be added to `docs/screenshots/` and linked here.

---

## Known Limitations

- **Language coverage gap.** Go, Rust, C#, Ruby, PHP, Swift, and Scala are classified by file extension but receive no AST symbol extraction. Dependency graph edges are not built for these languages. File-path-based risk signals (security, database, infrastructure) still fire.

- **Coverage data.** No runtime test coverage instrumentation is integrated. Test gap detection is a structural heuristic: if no test file was included in the change set, the `missing_tests` signal fires. This is conservative by design — it may flag false positives for projects with separate test automation.

- **Graph calibration.** The risk score is described in the source code itself as "a deterministic change-risk index, not a statistical probability of production failure." It has not been calibrated against historical production failure data.

- **Neo4j is optional.** The default deployment uses an in-memory dependency graph. Neo4j is only used when `NEO4J_URI` is configured. The in-memory graph supports all current features.

- **GitHub token scope.** GitHub integration requires a personal access token with `repo` scope. Fine-grained tokens may have limited access to private repository content.

- **Android / Manifest parsing.** Android project analysis (`AndroidManifest.xml`) is supported via a dedicated parser. Kotlin Composable and `@Entity` annotations are detected. Complex multi-module Android project graphs may have incomplete edges.

---

## Roadmap

### Implemented

- Deterministic risk engine with 22+ rules across 6 categories
- Tree-sitter AST parsing (Python, TypeScript, JavaScript, Kotlin, Java)
- Blast radius traversal with hub/bridge node detection
- Evidence ledger with FACT / INFERENCE / RECOMMENDATION classification
- AI explanation layer (OpenAI-compatible, Ollama, Groq, OpenRouter)
- PDF / JSON / CSV / Markdown export
- GitHub and local repository integration
- Risk policy engine

### In Progress

- Screenshot documentation
- Expanded test coverage

### Planned

- GitHub App integration (webhook-driven PR analysis without manual token entry)
- Go and Rust AST parser bindings
- Runtime coverage integration (LCOV / Cobertura import)
- Statistical score calibration against historical failure data

---

## Contributing

```bash
# Backend setup
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest                            # Run tests

# Frontend setup
cd frontend
npm install
npm run dev

# Linting
cd backend && ruff check .
cd frontend && npx eslint .
```

Pull requests should:

1. Include tests for new backend logic (pytest, `backend/tests/`)
2. Not modify the risk score calculation to incorporate AI outputs
3. Keep the evidence ledger structure intact (FACT / INFERENCE / RECOMMENDATION)

---

## License

MIT License. See [LICENSE](LICENSE).
