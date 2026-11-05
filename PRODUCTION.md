# NEXA Production Readiness

This document defines what “production-ready” means for NEXA and what is currently not safe to claim.

## Definition of done

NEXA may be called production-ready only after all of the following are true:

### Security and access control
- Public tenant creation is either removed, invite-based, rate-limited, or email-verified.
- `agent:run` and voice session creation require dedicated permissions, not `agent:read`.
- All money-spending endpoints have rate limits and per-tenant quotas.
- Production secrets never use committed defaults.
- JWT strategy includes expiry, revocation or refresh, and tenant consistency checks.
- Upload parsing is safe against decompression and XML attacks.
- Dependency and container vulnerabilities are scanned in CI.

### Data and retrieval
- Document creation and chunk/embedding writes are atomic.
- Failed ingestion leaves no orphan documents or partial chunks.
- Ingestion is asynchronous and retryable.
- Embeddings use a real provider and vector index (pgvector or equivalent).
- Retrieval is benchmarked for tenant isolation and relevance.

### Cost and quotas
- Every LLM call records token usage per tenant.
- Every tenant has a monthly/daily spend limit.
- The API returns a clear quota-exceeded response.
- An owner can inspect current usage and current spend.

### Operations
- Structured logs include request id, tenant id, agent id, and latency.
- Errors and ingestion failures are reported to an error tracker.
- Backup and restore are tested, not just configured.
- Rollback procedure is documented and rehearsed.
- Health/readiness checks reflect real dependencies.
- Production and staging environments are separated.

### Product and trust
- The README accurately states known limitations.
- There is a clear support/contact path.
- Privacy/data retention terms are written.
- Security reporting instructions are published.
- A v1 release checklist is completed and signed off.

## Current known limitations

### Security
- Tenant signup is invite-only and codes are one-time. Login, signup, invite creation, agent runs, and uploads now have in-memory per-client sliding-window rate limits (see `.env.example`); multi-instance deployments still need an edge/Redis-backed limiter.
- Security headers (nosniff, frame-deny, referrer policy, permissions-policy, HSTS, CSP with a relaxed policy on /docs) are applied to every response.
- Login still has no lockout or end-to-end brute-force protection beyond rate limiting.
- Email uniqueness is global rather than per-tenant.
- JWT has no refresh/revocation workflow.
- Production Compose refuses missing secrets and does not publish PostgreSQL, but a TLS proxy, secret manager, and real deployment validation are still required.

### Cost and LLM operations
- LLM usage is not accumulated across all agent iterations in a run.
- There is no tenant-level quota or hard cost cap.
- Tool failures are recorded in the response but not connected to alerting.

### RAG and storage
- Default embeddings are deterministic rather than semantic.
- Embeddings are stored in JSON columns and retrieved with full-table scans.
- No pgvector ANN index.
- Ingestion is synchronous and can leave partial documents on failure.
- File parsing limits decompressed XML insufficiently.

### Voice
- Voice room registry is in-memory and process-local.
- Voice depends on external LiveKit and local models.
- It is suitable for a controlled deployment demo, not a broad unmanaged deployment until load/failure testing is complete.

### Operations
- No managed observability stack.
- No tested backup restore runbook.
- No horizontal scaling story for voice session state.
- CI does not perform full SAST or dependency vulnerability scanning.

## Launch gates

Use these as hard gates before exposing NEXA to real customers:

1. Security gate: signup, login, run, voice, upload, and quotas reviewed.
2. Data gate: pgvector, atomic ingestion, backup/restore test.
3. Cost gate: per-tenant usage ledger and hard quota enforcement.
4. Ops gate: monitoring, alerting, rollback drill, incident runbook.
5. Legal gate: privacy terms, acceptable use, security reporting, data deletion.

## Suggested launch sequence

1. Staging deployment with real secrets and no public signup.
2. Load test `/run`, ingestion, and voice session handling.
3. Tenant isolation adversarial tests.
4. Backup restore test.
5. Limited beta with one controlled tenant.
6. Billing/quota alerts and support process.
7. Public launch only after all gates pass.
