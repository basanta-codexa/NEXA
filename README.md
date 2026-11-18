# NEXA

FastAPI service for multi-tenant AI agents. Agents can call tools, keep chat history, search uploaded documents, and run over LiveKit voice.

This is a working prototype, not a public service. See [PRODUCTION.md](PRODUCTION.md) before deploying.

## Layout

- `main.py`, `routers/` — API routes and auth
- `services/`, `engine/` — business logic and the agent loop
- `llm/` — model clients: `fake`, Ollama, OpenAI, Groq, xAI
- `rag/`, `tools/` — document search and tool registry
- `voice/` — LiveKit worker, STT, TTS, browser demo
- `frontend/` — Next.js UI
- `alembic/` — migrations
- `tests/` — pytest suite

## Requirements

Python 3.11+, PostgreSQL 15+, Docker Desktop for LiveKit. Ollama for local models, or an API key for OpenAI, Groq, or xAI. Node 18+ for the web UI.

## Local setup

From the repo root:

```powershell
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements-voice.txt
Copy-Item .env.example .env
```

Edit `.env`: set `JWT_SECRET_KEY` and your database credentials. Then, with Docker running:

```powershell
.\scripts\dev.ps1 start
```

That starts LiveKit, the API, the voice worker, and the demo page. Use `.\scripts\dev.ps1 status`, `restart`, or `stop` afterwards.

| URL | What |
|---|---|
| http://127.0.0.1:8000/docs | API docs |
| http://127.0.0.1:8000/health | Health check |
| http://127.0.0.1:5500/voice/demo.html | Voice demo |
| http://127.0.0.1:3000 | Web UI (`cd frontend; npm install; npm run dev`) |

## Configuration

A few settings you will actually change:

| Variable | Meaning |
|---|---|
| `DATABASE_URL` or `DB_*` | Postgres connection |
| `JWT_SECRET_KEY` | Token signing secret |
| `CORS_ORIGINS` | Allowed origins; `*` is local only |
| `LIVEKIT_*` | Voice server credentials |
| `STT_PROVIDER` | `auto` uses Groq if `GROQ_API_KEY` is set; `local` uses faster-whisper |
| `VAD_EOT_THRESHOLD`, `VAD_MIN_SILENCE_SECONDS` | When a voice turn ends |
| `WHISPER_MODEL_SIZE`, `WHISPER_LANGUAGE` | Local STT fallback |
| `PIPER_VOICE` | TTS voice |

The rest are listed in `.env.example`.

Model names in agent config: `fake`, `ollama/<model>`, `gpt-*`, `openai/<model>`, `groq/<model>`, `xai/<model>`, `grok/*`. For voice, `groq/qwen/qwen3.8-27b` is the low-latency option.

## First tenant and agent

Tenant creation needs an invite code. Create one, then pass it to `POST /tenants` with `name`, `admin_email`, `admin_password`, and `invite_code`:

```powershell
.\venv\Scripts\python.exe -m scripts.create_tenant_invite --description "Pilot" --days 7
.\venv\Scripts\python.exe -m alembic upgrade head
.\venv\Scripts\python.exe -m scripts.seed_rbac
```

Log in at `POST /users/login`. Use the returned token as `Authorization: Bearer <token>`. Create an agent with `POST /agents` and activate it with `PATCH /agents/{id}/status`. Voice sessions refuse draft agents.

## Voice

Open the demo and enter the API URL, an active agent ID, and the raw token. The browser must reach LiveKit at `ws://localhost:7880`.

STT uses Groq when `GROQ_API_KEY` is set and falls back to local Whisper. Voice replies use a separate prompt (`VOICE_SYSTEM_PROMPT` overrides it). The worker loads models on startup and logs per-stage timings in `.dev/logs/worker.out.log`.

## Tests

```powershell
.\venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\venv\Scripts\python.exe -m pytest
.\venv\Scripts\ruff.exe check tests
```

Tests use a temporary Postgres database and the `fake` model. No API keys or LiveKit needed. CI runs lint, migrations, `alembic check`, tests, and a Docker build on every push.

## Deploying

`docker-compose.yml` has no dev defaults. It requires `POSTGRES_PASSWORD`, `JWT_SECRET_KEY`, `CORS_ORIGINS`, `TRUSTED_PROXY_HOSTS`, and the LiveKit credentials. `TRUSTED_PROXY_HOSTS` is the proxy address as seen from inside the container, usually the Docker bridge gateway for a host proxy. Without it, all clients share one rate-limit bucket.

```powershell
docker compose --env-file .env.production up --build
```

It binds to `127.0.0.1:8000`. Put a TLS proxy in front. Postgres is not exposed. For LiveKit, copy `voice/livekit-config.production.example.yaml` to `voice/livekit-config.yaml` and replace the placeholders.

Do not expose this publicly until the gates in [PRODUCTION.md](PRODUCTION.md) are met. Never commit `.env` or production credentials. The dev LiveKit secret and `CORS_ORIGINS=*` are for local use only.
