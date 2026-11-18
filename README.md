# NEXA

NEXA is a multi-tenant platform for building and running AI agents with tools, conversation memory, knowledge retrieval, and live voice calls.

> **Status:** functional MVP. It is not a production-ready public service. Read [`PRODUCTION.md`](PRODUCTION.md) for launch gates and known limitations.

## Architecture

```text
Browser / API client
        |
        v
FastAPI (:8000)  <---->  PostgreSQL
        |
        v
LiveKit (:7880)  <---->  Voice worker
                           - Silero VAD + local EOT turn detection
                           - STT: Groq Whisper (fallback: faster-whisper)
                           - LLM: streaming agent engine
                           - TTS: Piper (streamed)
```

Text generation, tools, memory, and retrieval are shared by the API and the voice worker. Voice turns stream from the first LLM token to audio playback.

## Components

| Path | Purpose |
|---|---|
| `main.py`, `routers/`, `schemas.py` | HTTP API, auth, validation |
| `services/`, `engine/` | Business logic, RBAC, agent loop |
| `llm/` | OpenAI-compatible, Groq, xAI, Ollama, and fake clients |
| `rag/`, `tools/` | Retrieval and tool registry |
| `voice/` | LiveKit worker, STT/TTS, browser demo |
| `frontend/` | Next.js web application (optional) |
| `alembic/`, `models.py`, `database.py` | Schema and migrations |
| `tests/`, `.github/workflows/` | Test suite and CI |

## Prerequisites

- Python 3.11+
- PostgreSQL 15+
- Docker Desktop (LiveKit server)
- Optional: Ollama, and API keys for `OPENAI_API_KEY`, `GROQ_API_KEY`, or `XAI_API_KEY`
- Optional: Node.js 18+ for the Next.js frontend

## Quick start (Windows PowerShell)

From the repository root, with Docker Desktop running:

```powershell
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements-voice.txt
Copy-Item .env.example .env
.\scripts\dev.ps1 start
```

Edit `.env` before starting: set `JWT_SECRET_KEY` and your database credentials.

| Surface | URL |
|---|---|
| API docs | http://127.0.0.1:8000/docs |
| Health | http://127.0.0.1:8000/health |
| Voice demo | http://127.0.0.1:5500/voice/demo.html |
| Web app (`cd frontend; npm install; npm run dev`) | http://127.0.0.1:3000 |

Other commands: `.\scripts\dev.ps1 status`, `restart`, `stop`. Logs and PID files are written to `.dev/`.

To run services manually, start LiveKit (`docker compose -f voice/docker-compose.livekit.yml up -d`), then the API (`python -m uvicorn main:app --host 127.0.0.1 --port 8000`), the worker (`python -u -m voice.worker dev`), and the demo (`python -m http.server 5500 --bind 127.0.0.1`).

## Configuration

Copy `.env.example` to `.env`. Key settings:

| Variable | Purpose |
|---|---|
| `DATABASE_URL` or `DB_HOST`/`DB_PORT`/`DB_NAME`/`DB_USER`/`DB_PASSWORD` | PostgreSQL connection |
| `JWT_SECRET_KEY` | Signing secret; change before any shared deployment |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | Token lifetime (default 30) |
| `CORS_ORIGINS` | Comma-separated origins; `*` is local-only |
| `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET` | Voice server credentials |
| `STT_PROVIDER` | `auto` (Groq when `GROQ_API_KEY` is set), `groq`, or `local` |
| `VAD_EOT_ENABLED`, `VAD_EOT_THRESHOLD`, `VAD_MIN_SILENCE_SECONDS` | Turn endpointing |
| `WHISPER_MODEL_SIZE`, `WHISPER_LANGUAGE` | Local STT fallback |
| `PIPER_VOICE`, `PIPER_LENGTH_SCALE` | Voice and speaking pace |

Model prefixes: `fake` (offline), `ollama/<model>`, `gpt-*`/`openai/<model>`, `groq/<model>`, `xai/<model>`/`grok/*`. For low-latency voice, `groq/qwen/qwen3.8-27b` is recommended.

See `.env.example` for the full list, including rate limits and RAG tuning.

## First tenant and agent

Tenant creation is invite-only. Create a one-time code (shown once; only its hash is stored):

```powershell
.\venv\Scripts\python.exe -m scripts.create_tenant_invite --description "Pilot" --days 7
```

Apply migrations for a local install:

```powershell
.\venv\Scripts\python.exe -m alembic upgrade head
.\venv\Scripts\python.exe -m scripts.seed_rbac
```

Use `POST /tenants` with `{name, admin_email, admin_password, invite_code}`, then `POST /users/login` to get a bearer token. Create an agent with `POST /agents` and activate it with `PATCH /agents/{id}/status` — voice sessions reject draft agents.

## Voice calls

Open the demo, enter the API URL, an active agent ID, and the raw JWT (without `Bearer`). The browser must reach LiveKit on `ws://localhost:7880`.

STT defaults to Groq Whisper when `GROQ_API_KEY` is set and falls back to local faster-whisper. Voice replies use a dedicated conversational prompt (`VOICE_SYSTEM_PROMPT` overrides it); text API prompts are unchanged. Models are pre-warmed at worker startup, and the worker logs per-stage timings for latency tuning.

## Testing and CI

```powershell
.\venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\venv\Scripts\python.exe -m pytest
.\venv\Scripts\ruff.exe check tests
```

Tests use a disposable PostgreSQL database and the deterministic `fake` client; no external provider is required. GitHub Actions runs lint, migrations, `alembic check`, tests, and a Docker build on every push.

## Production

The root `docker-compose.yml` has no development fallbacks and refuses to start without `POSTGRES_PASSWORD`, `JWT_SECRET_KEY`, `CORS_ORIGINS`, and the LiveKit credentials. Use an untracked environment file:

```powershell
docker compose --env-file .env.production up --build
```

The API binds to `127.0.0.1:8000` by default; place a TLS reverse proxy in front. PostgreSQL is not exposed to the host. For LiveKit, copy `voice/livekit-config.production.example.yaml` to `voice/livekit-config.yaml` and replace all placeholders.

## Security

- Never commit `.env` or production credentials.
- Change `JWT_SECRET_KEY` and the LiveKit secret before sharing the app.
- `CORS_ORIGINS=*` and the committed LiveKit dev credentials are local-only.
- Do not expose the development LiveKit server or PostgreSQL port publicly.
- Expose NEXA publicly only after completing the gates in [`PRODUCTION.md`](PRODUCTION.md).
