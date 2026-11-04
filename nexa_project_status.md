# NEXA — Project Status

This file is the honest, current snapshot of the repository. It is not a marketing page.

## What NEXA is today

NEXA is a **multi-tenant agent API MVP** with an optional LiveKit voice pipeline.

It supports:

- Tenants and users
- JWT authentication
- Database-backed roles and permissions
- Agent CRUD and lifecycle management
- Provider-agnostic LLM clients (`fake`, Ollama, OpenAI-compatible/OpenAI)
- A bounded tool-calling agent loop
- Per-agent tool scoping
- Conversation memory
- Document ingestion and grounded retrieval
- Voice session creation and a LiveKit worker (STT → agent → TTS)
- PostgreSQL migrations with Alembic
- CI: migration verification, `alembic check`, lint gates, pytest, Docker build

## What is not production-ready

- Public tenant onboarding is unauthenticated and unthrottled
- No rate limiting or per-tenant token quotas
- Default embeddings are deterministic vectors, not production semantic embeddings
- Embeddings are stored as JSON and scanned in Python; pgvector/ANN is not implemented
- Ingestion is not atomic or asynchronous; a failed embedding can leave an unsearchable document
- No billing, spend tracking, or hard cost guardrails
- Voice room registry is process-local; it does not work across multiple API replicas
- No refresh tokens, revocation, logout, or breach-checked passwords
- Limited observability: logs exist, but no product metrics, alerts, or tracing
- No real frontend or admin console; API docs and a raw-JWT demo are the only UI

## Verified status

- Local test suite: **48 passed, 1 skipped** (Ollama integration)
- Database migrations and `alembic check` are part of CI
- Production deployment readiness: **not yet**; see `PRODUCTION.md`

## Immediate priorities

See `PRODUCTION.md` for the full launch checklist. The first hard blockers are:

1. Close public signup/run/voice authorization and add rate limits
2. Build transactional, asynchronous ingestion
3. Move retrieval to pgvector with real embeddings
4. Add per-tenant usage ledger and quota enforcement
5. Harden deployment secrets and observability

## Deliberately deferred

- AI employee swarm / autonomous multi-agent organization
- Full web application and customer-facing onboarding
- AWS-scale deployment automation until the security and data layers are safe

## How to update this document

Update it only when a phase has a tested, merged, and documented result. Do not list aspirations as completed work.
