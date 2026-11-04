# NEXA Frontend

The NEXA web application: a Next.js 14 + TypeScript multi-tenant SaaS UI for the NEXA AI workforce platform.

## Stack

- **Next.js 14** (App Router)
- **TypeScript**
- **Vanilla CSS** — no framework; a single design system in `src/app/globals.css`
- **JWT auth** via `localStorage` (`nexa.token` / `nexa.user`)

## Prerequisites

- Node.js 18+
- The NEXA backend running on port 8000 (see the repository root README)

## Quick start

```bash
cd frontend
npm install
cp .env.example .env.local   # points NEXT_PUBLIC_API_BASE at the backend
npm run dev
```

Then open http://localhost:3000.

## Environment

| Variable | Default | Purpose |
|---|---|---|
| `NEXT_PUBLIC_API_BASE` | `http://localhost:8000` | Base URL of the NEXA FastAPI backend |

## Routes

| Route | Purpose |
|---|---|
| `/` | Marketing landing page |
| `/login` | Sign in |
| `/signup` | Invite-only tenant creation |
| `/dashboard` | Tenant overview (agents, docs, team, health) |
| `/agents` | Create, edit, activate, pause and delete agents |
| `/agents/[id]` | Agent detail, live playground, activation/deletion |
| `/knowledge` | Upload documents, semantic search, delete |
| `/users` | Team list (admin-only create) |

## Scripts

```bash
npm run dev     # develop
npm run build   # production build (verified clean)
npm run start   # serve production build
```
