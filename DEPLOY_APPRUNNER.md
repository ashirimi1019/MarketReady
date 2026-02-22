# Deploy on AWS App Runner (Backend + Frontend)

## Architecture
- **Backend** → App Runner Service 1 (reads `apprunner.yaml` at repo root)
- **Frontend** → App Runner Service 2 (reads `frontend/apprunner.yaml`)
- **Database** → Amazon RDS PostgreSQL (or Neon.tech free tier)

---

## Step 0 — Database Setup (Do this first)

### Option A: Amazon RDS (AWS, paid)
1. RDS → Create database → PostgreSQL → Free tier
2. Set username: `market_admin`, password: your choice
3. Create DB name: `market_pathways`
4. Note the endpoint URL → your `DATABASE_URL` will be:
   `postgresql+psycopg2://market_admin:<password>@<rds-endpoint>:5432/market_pathways`

### Option B: Neon.tech (Free, easiest)
1. Go to neon.tech → New Project → PostgreSQL
2. Copy the connection string → replace `postgresql://` with `postgresql+psycopg2://`

---

## Step 1 — Deploy Backend

1. **AWS Console → App Runner → Create Service**
2. Source: **GitHub** → connect repo `ashirimi1019/MarketReady`
3. Branch: `main`
4. Configuration file: **Use configuration file** → it will find `apprunner.yaml` at root
5. Add Environment Variables:

| Key | Value |
|-----|-------|
| `DATABASE_URL` | `postgresql+psycopg2://user:pass@host:5432/market_pathways` |
| `AUTH_SECRET` | any 32+ char random string |
| `ADMIN_TOKEN` | any random token |
| `OPENAI_API_KEY` | `sk-...` |
| `ADZUNA_APP_ID` | your ID |
| `ADZUNA_APP_KEY` | your key |
| `CORS_ORIGINS` | `https://your-frontend.awsapprunner.com` (add after frontend deploys) |
| `AI_ENABLED` | `true` |
| `AUTH_REQUIRE_EMAIL_VERIFICATION` | `false` |

6. Click **Create and Deploy**
7. Note your backend URL: `https://xxxxxxx.us-east-1.awsapprunner.com`

---

## Step 2 — Deploy Frontend

1. **AWS Console → App Runner → Create Service**
2. Source: **GitHub** → same repo, branch `main`
3. Configuration file: **Use configuration file** → set path to `frontend/apprunner.yaml`
4. Add Environment Variables:

| Key | Value |
|-----|-------|
| `NEXT_PUBLIC_API_BASE` | `https://your-backend.us-east-1.awsapprunner.com/api` |

5. Click **Create and Deploy**
6. Note your frontend URL: `https://yyyyyyy.us-east-1.awsapprunner.com`

---

## Step 3 — Update CORS

Go back to your **backend** App Runner service → Environment Variables:
- Update `CORS_ORIGINS` to include your frontend URL:
  ```
  https://yyyyyyy.us-east-1.awsapprunner.com,https://marketready.netlify.app
  ```
- Click **Deploy** (manual trigger)

---

## Auto-Deploy on Push

Once set up, every push to `main` on GitHub automatically triggers a new deployment in App Runner.

---

## Troubleshooting

- **Health check failing**: Check App Runner logs → Activity tab → click failed deployment
- **Database connection error**: Verify RDS security group allows inbound from `0.0.0.0/0` on port 5432
- **CORS errors**: Update `CORS_ORIGINS` env var in App Runner to include your frontend URL
- **Build failing**: Check the build logs in App Runner console
