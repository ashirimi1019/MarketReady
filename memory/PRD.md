# Market Ready — PRD

## Problem Statement
Market Ready is a verification-first career readiness platform that combines federal skill standards, live job market demand, and repo-backed proof signals to answer: "How ready is this user for this role in this location right now, and what is the best next move?"

## Architecture
- **Frontend**: Next.js (dev mode) — `/app/frontend` — port 3000
- **Backend**: FastAPI + Python 3.11 — `/app/backend` — port 8001
- **Database**: PostgreSQL (local, port 5432) — `market_pathways` DB
- **AI**: OpenAI `gpt-4o-mini` via OpenAI API
- **Labor Market APIs**: Adzuna, CareerOneStop, O*NET

## Core Requirements (Static)

### 1. MRI Stress Test
- Formula: `MRI = (0.40 * Skill Match) + (0.30 * Live Demand) + (0.30 * Proof Density)`
- Components: CareerOneStop skill match, Adzuna live demand, internal proof density
- Live + fallback mode (snapshot TTL: skills=168h, adzuna=24h, full result=24h)
- Adzuna recovery engine: exact → role_rewrite → geo_widen → proxy_from_search

### 2. GitHub Proof Auditor
- Input: GitHub repo URL + target job + location
- Output: matched skills, verification confidence, files checked, languages detected
- Integration with CareerOneStop for required skills

### 3. 90-Day Agentic Mission Dashboard
- Full orchestrator flow: stress test + auditor + planner + strategist
- Mission kanban with weekly checkboxes
- Market pivot logic triggered by demand delta

## User Personas
- College students seeking tech jobs
- Bootcamp graduates needing credentialing
- Career switchers validating skills against real demand

## What's Been Implemented (2026-02-21)

### Setup & Infrastructure
- [x] PostgreSQL installed and configured (port 5432, DB: market_pathways)
- [x] `server.py` wrapper created (supervisor requires `server:app`)
- [x] All 11 Alembic migrations run successfully
- [x] Database seeded with initial data
- [x] `/app/backend/.env` configured with all API keys (OpenAI, Adzuna, CareerOneStop, O*NET, S3, AWS)
- [x] `/app/frontend/.env` configured with `NEXT_PUBLIC_API_BASE`
- [x] Frontend switched to `next dev` mode (no build required)
- [x] Backend f-string syntax fix for Python 3.11 compatibility

### Features Verified (All Passing)
- [x] Authentication (register/login/session)
- [x] MRI Stress Test end-to-end (Adzuna + CareerOneStop live data)
- [x] GitHub Proof Auditor with skill verification
- [x] 90-Day Mission Dashboard (orchestrator flow)
- [x] AI Guide, Cert ROI Calculator, Interview Simulator
- [x] Admin routes, market signals, proposals
- [x] Health endpoint: `/api/meta/health`

## Prioritized Backlog

### P0 — Critical / In Progress
- None (all core features working)

### P1 — High Value
- Add `data-testid` attributes to all interactive elements
- PostgreSQL auto-start on container restart (add to supervisor or init script)
- ai_strict_mode: consider setting to `false` for graceful fallbacks

### P2 — Nice to Have
- Auth UX: hide fields when not logged in (guide page)
- Market Pivot UI improvements
- 2027 AI shift simulation personalization
- Email verification flow (SMTP not configured)

## What's Been Implemented (2026-02-21 — Frontend Redesign)

### Complete UI/UX Upgrade
- [x] `globals.css`: Full design system rewrite — blue primary (#3D6DFF), glass morphism panels, clean tokens
- [x] NavBar: Glass floating island, clean text nav links (no orange pills), blue primary CTA "Get Started"
- [x] Homepage: Bold gradient hero headline, `//` live ticker, 2027 simulation section, bento quick-links grid
- [x] Login page: Centered glass card, "Sign in" with SECURE ACCESS badge, collapsible forgot password
- [x] Register page: Password strength indicator bar, clean centered card
- [x] Student layout: Fixed double page-shell, badge sizing fix, mobile hamburger nav
- [x] AWS App Runner deployment files: backend/Dockerfile, frontend/Dockerfile (standalone), apprunner.yaml
- [x] All tests passing: 100% backend, 95%+ frontend

## Next Tasks
1. Add PostgreSQL startup to container init so it persists on restart
2. Push to GitHub → auto-deploys to App Runner (backend) + Netlify (frontend)
3. Set RDS DATABASE_URL env var in App Runner console
4. Consider adding a shareable MRI Report Card URL feature

## API Credentials Configured
- OpenAI: gpt-4o-mini
- Adzuna: APP_ID=54a2e69c
- CareerOneStop: USER_ID=wM5MmQC75vS4dtk
- O*NET: ashirimi1010@outlook.com
- AWS S3: market-pathways-053549819821-uploads (us-east-1)
