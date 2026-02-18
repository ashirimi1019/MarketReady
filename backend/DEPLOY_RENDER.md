# Deploy Backend on Render

## 1) Push this project to your GitHub repo

From project root:

```powershell
cd "C:\Users\ashir\Career App"
# Remove nested frontend git metadata so frontend files are included in this repo.
if (Test-Path ".\\frontend\\.git") { Remove-Item -Recurse -Force ".\\frontend\\.git" }
git init
git branch -M main
git remote add origin https://github.com/ashirimi1019/MarketReady.git
git add .
git commit -m "Prepare Render deployment"
git push -u origin main
```

## 2) Create Render Web Service

- In Render dashboard: `New` -> `Blueprint`.
- Select `ashirimi1019/MarketReady`.
- Render will read `render.yaml`.

## 3) Set environment variables in Render

Required:

- `DATABASE_URL` (Render Postgres external URL or your own Postgres URL)
- `AUTH_SECRET` (long random string)
- `ADMIN_TOKEN` (random admin token)
- `CORS_ORIGINS` (include frontend URL, comma-separated)

Optional (only if needed):

- `OPENAI_API_KEY`, `OPENAI_MODEL`, `AI_ENABLED=true`
- S3 settings if using S3 uploads
- Mail settings if enabling email

## 4) Verify after deploy

- `GET https://<your-render-service>/meta/health` should return `ok: true`.
- In frontend host (Netlify), set:
  - `NEXT_PUBLIC_API_BASE=https://<your-render-service>`
