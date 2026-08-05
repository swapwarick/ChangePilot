# ChangePilot

ChangePilot is an AI-powered Change Impact Analysis platform. It analyzes repositories or uploaded projects, builds dependency graphs, computes deterministic risk scores, and uses AI only to explain the evidence.

## Principles

- AI explains findings, but never calculates risk.
- Risk scoring is deterministic and reproducible.
- External services are behind interfaces and adapters.
- AI providers are configurable, prioritized, and replaceable.
- Local models through Ollama, LM Studio, vLLM, or any OpenAI-compatible server are first-class.

## Repository Layout

- `frontend/` - Next.js 15, React 19, TypeScript, Tailwind, shadcn-style primitives, React Flow, TanStack Query, Zustand.
- `backend/` - FastAPI, Pydantic, deterministic risk engine, provider strategy layer, repository analysis services.
- `docs/` - architecture notes and extension contracts.
- `docker-compose.yml` - local PostgreSQL/pgvector, Neo4j, Redis, frontend, and backend.

## Quick Start

```powershell
cp .env.example .env
docker compose up --build
```

Frontend: http://localhost:3000

Backend API: http://localhost:8000/docs

## Local Development

```powershell
npm install
npm run dev
```

Backend only:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

Frontend only:

```powershell
cd frontend
npm install
npm run dev
```

## Testing

```powershell
cd backend
pytest
```

## AI Provider Model

Business logic depends on `AIProvider` and `AIProviderRegistry`, never concrete SDKs. OpenAI, Anthropic, Gemini, OpenRouter, Groq, Together AI, LM Studio, vLLM, and custom REST endpoints can be represented as OpenAI-compatible providers when they expose that protocol. Ollama has a dedicated local adapter.

Provider configuration is runtime data: enabled state, priority, fallback chain, timeout, retry policy, custom headers, temperature, and max tokens can all be changed without restarting the app once persistent storage is wired in.

## Risk Model

The risk engine consumes deterministic evidence:

- Changed files
- Dependency graph impact
- Critical path matches
- Test coverage signals
- API, auth, database, infrastructure, and configuration changes

AI reports may summarize or explain this evidence, but must reference it and cannot introduce new scoring factors.

