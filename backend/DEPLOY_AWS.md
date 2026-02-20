# Deploy on AWS (us-east-1)

This is the fastest path with your current FastAPI app:

- Backend: **AWS App Runner**
- Database: **Amazon RDS PostgreSQL**
- Files: **S3** (already integrated in code)
- Frontend: keep on Netlify (`https://marketready.netlify.app`)

## 1) Build backend container image

Create `backend/Dockerfile`:

```dockerfile
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && python -m app.seed && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
```

Create `backend/.dockerignore`:

```dockerignore
.env
__pycache__/
.pytest_cache/
uploads/
training/
*.log
```

## 2) Push image to ECR

```bash
aws configure
aws ecr create-repository --repository-name marketready-api --region us-east-1
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com
docker build -t marketready-api ./backend
docker tag marketready-api:latest <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/marketready-api:latest
docker push <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/marketready-api:latest
```

## 3) Create RDS PostgreSQL

In RDS console (`us-east-1`):

- Engine: PostgreSQL
- Template: Free tier (if available)
- DB name: `market_pathways`
- Username/password: create new
- Public access: **Yes** (fastest for initial deploy)
- Save endpoint once created

Build `DATABASE_URL`:

```text
postgresql+psycopg2://<db_user>:<db_pass>@<rds-endpoint>:5432/market_pathways
```

## 4) Create App Runner service (from ECR image)

In App Runner console:

- Source: **Container registry**
- Image URI: `<ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/marketready-api:latest`
- Port: `8000`

Set environment variables:

- `DATABASE_URL`
- `ADMIN_TOKEN`
- `AUTH_SECRET`
- `CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000,https://marketready.netlify.app`
- `AUTH_REQUIRE_EMAIL_VERIFICATION=false`
- `AI_ENABLED=true` (if using AI in production)
- `AI_STRICT_MODE=true` (forces real AI responses; disables rules fallback)
- `LLM_PROVIDER=openai` (or groq)
- `OPENAI_API_KEY` (if OpenAI enabled)
- `OPENAI_MODEL=gpt-5-mini`
- `LLM_TIMEOUT_SECONDS=90`
- `LLM_MAX_RETRIES=3`

S3 vars (if using uploads):

- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `S3_BUCKET`
- `S3_REGION=us-east-1`
- `S3_PRESIGN_EXPIRY_SECONDS=900`

Optional market automation (safe defaults when omitted):

- `MARKET_AUTO_ENABLED=true`
- `MARKET_AUTO_INTERVAL_MINUTES=360`
- `MARKET_AUTO_RUN_ON_STARTUP=false`
- `MARKET_AUTO_PROVIDER_LIST=adzuna,onet,careeronestop`
- `MARKET_AUTO_ROLE_FAMILIES=software engineer,data analyst,cybersecurity analyst`
- `MARKET_AUTO_SIGNAL_LIMIT=25`
- `MARKET_AUTO_PROPOSAL_LOOKBACK_DAYS=30`
- `MARKET_AUTO_PROPOSAL_MIN_SIGNALS=10`
- `MARKET_AUTO_PROPOSAL_COOLDOWN_HOURS=24`

## 5) Verify backend

After deploy:

- Open `https://<apprunner-url>/meta/health`
- Must return `{"ok": true, ...}`
- Open `https://<apprunner-url>/api/admin/market/automation/status` with `X-Admin-Token` and verify scheduler + provider status

## 6) Connect Netlify frontend

In Netlify environment variables:

- `NEXT_PUBLIC_API_BASE=https://<apprunner-url>`

Redeploy Netlify.

---

## Security hardening (do right after first successful deploy)

- Rotate all previously exposed keys (AWS, OpenAI, provider keys).
- Move secrets to **AWS Secrets Manager**.
- Restrict RDS network access (avoid long-term public access).
- Prefer IAM role for App Runner + S3 instead of static access keys.
