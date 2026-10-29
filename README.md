# NEXA

NEXA is a multi-tenant platform for building, running, and voicing AI agents with tools, persistent memory, and retrieval-augmented knowledge.

The repository contains a FastAPI backend, a LiveKit-based voice pipeline, and a standalone browser demo. There is no separate React/Next frontend yet; the primary UI surfaces are Swagger and `voice/demo.html`.

## Architecture

```text
Browser (voice/demo.html)
        |
        | HTTP (session + token)
        v
FastAPI API (:8000) -------- PostgreSQL
        |
        | LiveKit room token
        v
LiveKit server (:7880) <----> Voice worker
                                  |
                                  +-- Silero VAD
                                  +-- faster-whisper STT
                                  +-- agent engine (Ollama/OpenAI/fake)
                                  +-- Piper TTS
```

## Features

- Tenants, users, roles, and permissions
- Agent CRUD, activation, and text runs
- Tool calling with a provider-agnostic agent loop
- Conversation memory
- RAG with document ingestion
- LiveKit voice sessions
- Local speech-to-text with faster-whisper
- Local text-to-speech with Piper
- Standalone browser voice demo

## Repository layout

```text
main.py                     FastAPI application and health endpoints
routers/                    HTTP endpoints
services/                   Business logic and tenant/RBAC services
engine/                     Agent execution loop
llm/                        OpenAI, Ollama, and fake LLM clients
rag/                        Retrieval and document processing
voice/                      LiveKit worker, STT/TTS, demo, compose file
alembic/                    Database migrations
scripts/                    Database/bootstrap utilities and local dev runner
tests/                      Automated pytest suite (disposable PostgreSQL database)
.github/workflows/          GitHub Actions CI
Dockerfile                  Production-style API image
docker-compose.yml          API + PostgreSQL stack
```

## Prerequisites

- Python 3.11+
- PostgreSQL 15+
- Docker Desktop (for the local LiveKit server)
- Ollama (only for `ollama/*` models)

Tested with Python 3.14.1, PostgreSQL 18, Docker Desktop, and Ollama.

## Quick start (Windows PowerShell)

Run these from the repository root.

### Recommended: one command

Make sure Docker Desktop is running, then:

```powershell
.\scripts\dev.ps1 start
```

The script starts LiveKit first, waits for it to become reachable, then starts the API, voice worker, and demo server. It writes logs and PID files under `.dev/` and prints a status table.

If PowerShell blocks the script:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 start
```

Other commands:

```powershell
.\scripts\dev.ps1 status
.\scripts\dev.ps1 restart
.\scripts\dev.ps1 stop
```

`stop` also stops the LiveKit container. It only stops API/worker/demo processes that this script started.

### Manual alternative

#### 1. Start LiveKit

Make sure Docker Desktop is running.

```powershell
docker compose -f voice/docker-compose.livekit.yml up -d
```

#### 2. Start the API

```powershell
.\venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
```

#### 3. Start the voice worker

Start this only when you need voice. LiveKit must be running first.

```powershell
.\venv\Scripts\python.exe -u -m voice.worker dev
```

#### 4. Serve the demo page

```powershell
.\venv\Scripts\python.exe -m http.server 5500 --bind 127.0.0.1
```

### Open the app

| Surface | URL |
|---|---|
| API docs | http://127.0.0.1:8000/docs |
| Health check | http://127.0.0.1:8000/health |
| Voice demo | http://127.0.0.1:5500/voice/demo.html |

## Docker Compose (API + PostgreSQL)

The root `docker-compose.yml` runs PostgreSQL and the API in containers. It applies migrations and seeds RBAC automatically on startup.

```powershell
docker compose up --build
```

Then open http://127.0.0.1:8000/docs.

The database is exposed on host port `5433` by default so it does not conflict with a local PostgreSQL server on `5432`. Override `NEXA_DB_PORT` if needed. Set `JWT_SECRET_KEY`, `LIVEKIT_API_KEY`, and `LIVEKIT_API_SECRET` in `.env` for anything beyond a local demo.

Stop the stack with `docker compose down`. Add `-v` to also delete the PostgreSQL volume and start fresh.

## First-time setup

### 1. Create the Python environment

```powershell
python -m venv venv
.\venv\Scripts\python.exe -m pip install --upgrade pip
.\venv\Scripts\python.exe -m pip install -r requirements-voice.txt
```

`requirements-voice.txt` includes the core API dependencies. For an API-only install, use `requirements.txt`.

### 2. Configure environment variables

```powershell
Copy-Item .env.example .env
notepad .env
```

At minimum, set:

```env
DB_HOST=localhost
DB_PORT=5432
DB_NAME=nexa
DB_USER=postgres
DB_PASSWORD=your-postgres-password

JWT_SECRET_KEY=replace-with-a-long-random-secret

LIVEKIT_URL=ws://localhost:7880
LIVEKIT_API_KEY=devkey
LIVEKIT_API_SECRET=secret

OLLAMA_HOST=http://localhost:11434
```

`LIVEKIT_API_KEY` and `LIVEKIT_API_SECRET` must match `voice/livekit-config.yaml`. The committed values are development defaults only.

### 3. Create the database

Using `psql`:

```powershell
psql -U postgres -c "CREATE DATABASE nexa;"
```

Or create a database named `nexa` in pgAdmin. If `psql` is not on your `PATH`, use pgAdmin or the full path under `C:\Program Files\PostgreSQL\<version>\bin`.

### 4. Run migrations and seed RBAC

```powershell
.\venv\Scripts\python.exe -m alembic upgrade head
.\venv\Scripts\python.exe -m scripts.seed_rbac
```

New tenants seed their own roles automatically. `seed_rbac` is mainly useful for tenants created before RBAC seeding was added.

For a quick local bootstrap, the following is also available, but Alembic is preferred:

```powershell
.\venv\Scripts\python.exe -m scripts.init_db
```

### 5. Pull an Ollama model

```powershell
ollama pull llama3.2:3b
```

If Ollama is not running:

```powershell
ollama serve
```

### 6. Start the services

Follow the Quick start section above.

## Create a tenant and agent

Tenant creation is public and creates the first admin user. There is no signup UI yet.

### 1. Create the tenant and admin

```powershell
$tenantBody = @{
  name = "Acme"
  description = "Demo tenant"
  admin_email = "admin@acme.com"
  admin_password = "ChangeMe123!"
} | ConvertTo-Json

Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/tenants" `
  -ContentType "application/json" -Body $tenantBody
```

### 2. Log in

```powershell
$loginBody = @{
  email = "admin@acme.com"
  password = "ChangeMe123!"
} | ConvertTo-Json

$login = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/users/login" `
  -ContentType "application/json" -Body $loginBody

$token = $login.access_token
$headers = @{ Authorization = "Bearer $token" }
```

The default token lifetime is 30 minutes. To make local demo tokens last longer, set this before starting the API:

```env
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=720
```

### 3. Create an agent

```powershell
$agentBody = @{
  name = "Demo Agent"
  role = "Assistant"
  language = "English"
  description = "Local voice demo"
  system_prompt = "You are a helpful voice assistant. Keep answers short and conversational."
  model_name = "ollama/llama3.2:3b"
  temperature = 0.3
  max_tokens = 300
  top_p = 0.9
} | ConvertTo-Json

$agent = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/agents" `
  -Headers $headers -ContentType "application/json" -Body $agentBody
```

### 4. Activate the agent

New agents are created as `draft`. Voice sessions reject agents that are not active.

```powershell
Invoke-RestMethod -Method Patch -Uri "http://127.0.0.1:8000/agents/$($agent.id)/status" `
  -Headers $headers -ContentType "application/json" -Body '{"status":"active"}'
```

### 5. Test text chat

```powershell
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/agents/$($agent.id)/run" `
  -Headers $headers -ContentType "application/json" `
  -Body '{"message":"Hello, what can you do?"}'
```

## Voice demo

Open:

```text
http://127.0.0.1:5500/voice/demo.html
```

Enter:

- **API Base URL:** `http://localhost:8000`
- **Agent ID:** the ID of an `active` agent
- **JWT Token:** the raw token, without the word `Bearer`

The browser must be able to reach the LiveKit server on `ws://localhost:7880`. The compose file advertises `127.0.0.1` as the LiveKit node IP so a browser on the same machine can reach the published UDP/TCP media ports.

## Testing

Install the development dependencies once:

```powershell
.\venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

Run the suite:

```powershell
.\venv\Scripts\python.exe -m pytest
```

The tests create a disposable PostgreSQL database named `nexa_test_<id>` from the `DB_*` or `DATABASE_URL` settings in `.env`, apply every Alembic migration, run the tests, and drop the database afterward. Your development database (`nexa`) is never touched. The database user needs permission to create databases.

The API tests use `TestClient`, the deterministic `fake` LLM client, and deterministic embeddings, so Ollama, OpenAI, and LiveKit are not required.

Optional live Ollama integration test:

```powershell
$env:RUN_OLLAMA_TESTS = "1"
.\venv\Scripts\python.exe -m pytest -m integration
```

Lint checks used by CI:

```powershell
.\venv\Scripts\ruff.exe check tests
.\venv\Scripts\ruff.exe check . --select E9,F63,F7,F82
```

GitHub Actions runs the lint checks, migrations, `alembic check`, the full test suite, and a Docker image build on every push and pull request.

### Manual smoke checks

```powershell
# API and database
Invoke-RestMethod http://127.0.0.1:8000/health

# List agents for the logged-in tenant
Invoke-RestMethod -Uri "http://127.0.0.1:8000/agents" -Headers $headers

# Run a text turn
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/agents/$($agent.id)/run" `
  -Headers $headers -ContentType "application/json" `
  -Body '{"message":"Reply with one short sentence."}'
```

## Troubleshooting

### The voice worker exits with `failed to connect to livekit`

LiveKit is not running yet, or the worker was started before LiveKit. Start LiveKit, wait for port `7880`, then restart the worker.

```powershell
docker compose -f voice/docker-compose.livekit.yml up -d
docker ps --filter "name=nexa-livekit"
```

The repeated `Event loop is closed` messages after the worker exits are shutdown noise, not the root cause.

### `couldn't establish pc connection`

Check that the LiveKit container is running and that the compose command includes:

```text
--node-ip=127.0.0.1
```

Recreate the container after changing the compose file:

```powershell
docker compose -f voice/docker-compose.livekit.yml up -d --force-recreate
```

### `400 Agent '...' is not active`

Activate the agent before starting a voice session.

### `401 Authentication required`

The JWT is missing, malformed, or expired. Log in again and paste the raw token.

### `404 Agent not found`

The JWT belongs to a different tenant than the agent.

### First voice turn is slow

The worker downloads Whisper and Piper models on first use. On CPU, STT and TTS are also the main latency contributors. `WHISPER_MODEL_SIZE=tiny` is faster but less accurate than `base`.

LiveKit may log `event loop blocked` warnings while resampling or running model work. These are performance warnings, not startup failures.

### LiveKit logs `secret is too short`

The development secret is only `secret`. LiveKit still starts, but any shared or production deployment should use a 32+ character secret in both `.env` and `voice/livekit-config.yaml`.

## Security notes

- Never commit `.env`.
- Change `JWT_SECRET_KEY` and the LiveKit API secret before sharing the app.
- `CORS_ORIGINS=*` is for local development only.
- The demo accepts a raw JWT for convenience; a real frontend should use a login flow and short-lived tokens.
- Do not expose the development LiveKit server or PostgreSQL port directly to the internet.
