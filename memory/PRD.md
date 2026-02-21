# Market Ready — Product Requirements Document

## Original Problem Statement
Build a proof-first career readiness platform for students that combines live market signals (GitHub, Adzuna, O*NET) with AI-powered planning to help them answer: "Am I actually hireable?"

## User Personas
- **Primary:** Computer science students (undergrad/grad) preparing for internships and entry-level roles
- **Secondary:** Career coaches and recruiters who want to verify student readiness
- **Tertiary:** University advisors tracking student market alignment

## Tech Stack
- **Frontend:** Next.js 14 (App Router), React, TypeScript, Tailwind CSS v4, shadcn/ui
- **Backend:** FastAPI, Python 3.11, SQLAlchemy ORM
- **Database:** PostgreSQL (not MongoDB — see note)
- **Authentication:** JWT-based (X-Auth-Token header)
- **Deployment:** AWS App Runner (Dockerfiles created)
- **External APIs:** Adzuna (labor market), CareerOneStop/O*NET (federal standards), OpenAI (AI features), GitHub API (unauthenticated)

**NOTE:** This project uses PostgreSQL, NOT MongoDB. The system prompt mentions MongoDB but this project uses PostgreSQL with SQLAlchemy.

## Core Architecture
```
/app/
├── backend/
│   ├── app/
│   │   ├── api/routes/        # All API routes
│   │   ├── core/config.py     # Settings, env vars
│   │   ├── models/entities.py # DB models
│   │   ├── services/          # Business logic
│   │   ├── alembic/versions/  # DB migrations
│   │   └── main.py            # FastAPI app + route registration
│   └── requirements.txt
└── frontend/
    └── src/
        ├── app/               # Next.js pages
        ├── components/        # Shared components
        └── lib/               # API utils, session
```

## What's Been Implemented

### Phase 1: Initial Setup (Jan 2026)
- ✅ PostgreSQL database setup with migrations (0001-0012)
- ✅ FastAPI backend with JWT auth
- ✅ Next.js 14 frontend with TypeScript + Tailwind
- ✅ All env vars, Dockerfiles, AWS App Runner configs
- ✅ Full UI/UX overhaul (dark mode, Space Grotesk fonts, bento grid layout)

### Phase 2: 6 Hackathon Features (Feb 2026)

#### Feature 1: GitHub Signal Auditor
- ✅ Backend: `GET /api/github/audit/:username`
  - Fetches user repos, package.json, requirements.txt
  - Maps dependencies to skills (React, Python, FastAPI, etc.)
  - Analyzes commit messages for skill keywords
  - Computes velocity score (0-100)
  - Detects bulk upload pattern
  - Returns: verified_skills, commit_skill_signals, velocity, warnings
- ✅ Frontend: GitHub audit card on `/student/readiness` page
  - Velocity metrics, verified skills badges, commit signals, warnings

#### Feature 2: MRI (Market-Ready Index) Algorithm
- ✅ Backend: `GET /api/score/mri`
  - Formula: `MRI = (Federal Standards × 0.40) + (Market Demand × 0.30) + (Evidence Density × 0.30)`
  - Federal Standards: based on non-negotiable + strong_signal checklist completion
  - Market Demand: ratio of verified skills to all checklist items (Adzuna proxy)
  - Evidence Density: proof type diversity + recency + GitHub bonus
  - Returns: score, components, gaps, recommendations, band
- ✅ Frontend: Redesigned `/student/readiness` page
  - Animated score ring (SVG)
  - 3-segment bar for each component
  - "What's Dragging Your Score" section with actionable gaps
  - Band: Market Ready / Competitive / Developing / Focus Gaps

#### Feature 3: Sentinel Market Guard
- ✅ Backend: `POST /api/sentinel/run`
  - Uses Adzuna to check demand count for user's target role
  - Compares to previous signal (detects +/- 20% shifts)
  - Creates StudentNotification records with severity and action
  - Also creates profile tips and skills trend alerts
- ✅ Frontend: NavBar notification bell
  - Red unread count badge
  - Dropdown panel showing alerts with color-coded kind labels
  - "Run Scan" button to trigger sentinel
  - Mark read on click
  - "⚡ Market Shift" label for shift alerts

#### Feature 4: Interactive 90-Day Pivot Kanban
- ✅ Backend: Full CRUD at `/api/kanban/...`
  - `GET /api/kanban/board` - 3-column board
  - `POST /api/kanban/tasks` - create task
  - `PUT /api/kanban/tasks/:id` - update (drag-drop, edit)
  - `DELETE /api/kanban/tasks/:id` - delete
  - `POST /api/kanban/generate` - AI-powered 12-task 90-day plan (gpt-4o-mini)
  - `POST /api/kanban/sync-github` - auto-complete tasks via GitHub
- ✅ Frontend: `/student/kanban` page
  - @hello-pangea/dnd drag-and-drop
  - Week filter
  - Add task inline
  - AI generate + GitHub sync buttons
  - Priority indicators, AI/GitHub badges on cards

#### Feature 5: 2027 Future-Shock Simulator
- ✅ Backend: `POST /api/simulator/future-shock`
  - Takes acceleration (0-100)
  - Uses RESILIENCE_MULTIPLIERS to adjust skill values
  - Classifies skills as resilient/at_risk/stable
  - Returns adjusted_score, delta, risk_level, recommendations
- ✅ Frontend: Slider on `/student/readiness` page
  - Debounced API call (400ms)
  - Animated score display
  - Skill risk profile grid (green=resilient, red=at_risk)
  - Recommended pivots section

#### Feature 6: Recruiter Truth-Link
- ✅ Backend:
  - `POST /api/profile/generate-share-link` - generates unique 10-char slug
  - `GET /api/public/:slug` - public profile data (no auth)
  - `share_slug` column added to `student_profiles` (migration 0012)
- ✅ Frontend:
  - Share panel on `/student/profile` page
  - QR code generation (qrcode.react)
  - Copy link button
  - Public profile at `/profile/[slug]` (no auth required)
  - Shows MRI score, verified skills, GitHub link

#### Cross-feature Integrations
- ✅ GitHub Audit feeds MRI (evidence_density bonus for GitHub username)
- ✅ Sentinel creates notifications that reference Kanban actions
- ✅ NavBar updated with Kanban and MRI Score links
- ✅ All features interconnected

## Key API Endpoints

### Auth
- `POST /api/auth/register`
- `POST /api/auth/login`
- `POST /api/auth/logout`

### New Feature APIs (Phase 2)
- `GET /api/github/audit/:username`
- `GET /api/score/mri`
- `POST /api/sentinel/run`
- `GET /api/kanban/board`
- `POST /api/kanban/tasks`
- `PUT /api/kanban/tasks/:id`
- `DELETE /api/kanban/tasks/:id`
- `POST /api/kanban/generate`
- `POST /api/kanban/sync-github`
- `POST /api/simulator/future-shock`
- `POST /api/profile/generate-share-link`
- `GET /api/public/:slug`

## DB Schema (Key Tables)
- `student_accounts` - auth
- `student_profiles` - profile info, github_username, **share_slug** (new)
- `career_pathways` - pathway definitions
- `user_pathways` - user's selected pathway
- `checklist_versions`, `checklist_items` - skill requirements
- `proofs` - user's evidence artifacts
- `student_notifications` - sentinel alerts
- **`kanban_tasks`** (new) - 90-day plan tasks

## Environment Variables
- `DATABASE_URL` - PostgreSQL connection
- `ADZUNA_APP_ID`, `ADZUNA_APP_KEY` - Adzuna market data
- `OPENAI_API_KEY` - AI features (kanban generate, etc.)
- `NEXT_PUBLIC_API_BASE` - Frontend API URL
- `PUBLIC_APP_BASE_URL` - For generating public share links

## Deployment
- AWS App Runner via Dockerfiles
- `backend/Dockerfile` + `backend/apprunner.yaml`
- `frontend/Dockerfile.frontend` + `frontend/apprunner.yaml`
- PostgreSQL must be externally hosted (e.g., RDS)

## Prioritized Backlog

### P0 (Critical - Done)
- ✅ All 6 hackathon features

### P1 (Important - Upcoming)
- Add real Adzuna salary data to MRI Market Demand score
- GitHub OAuth flow (vs manual username entry)
- Kanban task editing (click to edit title/description)
- Persistent PostgreSQL for production (move from local)

### P2 (Nice to have)
- Email notifications for sentinel alerts (via SendGrid/Resend)
- Shareable Kanban board view (public link)
- Historical MRI score tracking (chart over time)
- Export profile as PDF
- LinkedIn integration for verified skills

### P3 (Future/Backlog)
- Admin dashboard for university advisors
- Cohort comparison (anonymized MRI rankings)
- Job application tracker integration
- Video proof submissions
