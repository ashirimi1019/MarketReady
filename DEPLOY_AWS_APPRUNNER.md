# AWS App Runner Deployment Guide

## Architecture on AWS

```
Internet → AWS App Runner (Backend)  ←→  AWS RDS PostgreSQL
          AWS App Runner (Frontend)  ←→  AWS S3 (uploads)
```

## Prerequisites
- AWS CLI configured (`aws configure`)
- Docker installed locally
- ECR repositories created (or use App Runner GitHub auto-deploy)
- AWS RDS PostgreSQL instance running

---

## Step 1: Create RDS PostgreSQL Database

```bash
# Create RDS instance (example via AWS CLI)
aws rds create-db-instance \
  --db-instance-identifier marketready-db \
  --db-instance-class db.t3.micro \
  --engine postgres \
  --master-username market_admin \
  --master-user-password YOUR_SECURE_PASSWORD \
  --allocated-storage 20 \
  --vpc-security-group-ids sg-XXXXXXXX \
  --publicly-accessible

# Get the endpoint after creation (takes ~5 min)
aws rds describe-db-instances \
  --db-instance-identifier marketready-db \
  --query 'DBInstances[0].Endpoint.Address'
```

Your `DATABASE_URL` will be:
```
postgresql+psycopg2://market_admin:YOUR_SECURE_PASSWORD@<RDS_ENDPOINT>:5432/market_pathways
```

---

## Step 2: Create ECR Repositories

```bash
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
AWS_REGION=us-east-1

# Create repos
aws ecr create-repository --repository-name marketready-backend --region $AWS_REGION
aws ecr create-repository --repository-name marketready-frontend --region $AWS_REGION
```

---

## Step 3: Build & Push Docker Images

### Backend

```bash
cd backend

# Login to ECR
aws ecr get-login-password --region $AWS_REGION | \
  docker login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

# Build & push
docker build -t marketready-backend .
docker tag marketready-backend:latest $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/marketready-backend:latest
docker push $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/marketready-backend:latest
```

### Frontend

```bash
cd frontend

# Replace with your actual backend App Runner URL after backend is deployed
BACKEND_URL=https://YOUR_BACKEND_APPRUNNER_URL

docker build \
  --build-arg NEXT_PUBLIC_API_BASE=$BACKEND_URL/api \
  -t marketready-frontend .

docker tag marketready-frontend:latest $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/marketready-frontend:latest
docker push $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/marketready-frontend:latest
```

---

## Step 4: Deploy Backend on App Runner

### Via AWS Console:
1. Go to **App Runner** → **Create service**
2. **Source**: Container registry → Amazon ECR → `marketready-backend`
3. **Port**: `8080`
4. **Health check path**: `/meta/health`
5. **Environment variables** (set these):

| Key | Value |
|-----|-------|
| `DATABASE_URL` | `postgresql+psycopg2://market_admin:PASSWORD@RDS_ENDPOINT:5432/market_pathways` |
| `AUTH_SECRET` | `your-strong-secret-256-bit` |
| `ADMIN_TOKEN` | `your-admin-token` |
| `AI_ENABLED` | `true` |
| `LLM_PROVIDER` | `openai` |
| `OPENAI_API_KEY` | `sk-proj-...` |
| `OPENAI_MODEL` | `gpt-4o-mini` |
| `OPENAI_API_BASE` | `https://api.openai.com/v1` |
| `ADZUNA_APP_ID` | `54a2e69c` |
| `ADZUNA_APP_KEY` | `fa0207c198ea94fe7ad4861a479f0f60` |
| `ADZUNA_COUNTRY` | `us` |
| `CAREERONESTOP_API_KEY` | `AtVdEmdnQ5bmzZ...` |
| `CAREERONESTOP_USER_ID` | `wM5MmQC75vS4dtk` |
| `ONET_USERNAME` | `ashirimi1010@outlook.com` |
| `ONET_PASSWORD` | `gehfA-44cVT-D4d76-60AIK` |
| `AWS_ACCESS_KEY_ID` | `AKIAQY56RM6W2QDEOOX7` |
| `AWS_SECRET_ACCESS_KEY` | `G6ra3xA/dpgNNmlzYK...` |
| `S3_BUCKET` | `market-pathways-053549819821-uploads` |
| `S3_REGION` | `us-east-1` |
| `CORS_ORIGINS` | `https://YOUR_FRONTEND_APPRUNNER_URL,http://localhost:3000` |
| `AUTH_REQUIRE_EMAIL_VERIFICATION` | `false` |
| `AI_STRICT_MODE` | `false` |

6. Click **Create & Deploy**
7. Note the App Runner URL (e.g., `https://abc123.us-east-1.awsapprunner.com`)

---

## Step 5: Deploy Frontend on App Runner

1. Rebuild frontend Docker image with the actual backend URL:
```bash
docker build \
  --build-arg NEXT_PUBLIC_API_BASE=https://YOUR_BACKEND_URL/api \
  -t marketready-frontend .
docker push ...
```

2. Create new App Runner service:
   - **Source**: ECR → `marketready-frontend`
   - **Port**: `3000`
   - **Environment variables**:
     - `NEXT_PUBLIC_API_BASE` = `https://YOUR_BACKEND_URL/api`

---

## Step 6: Verify Deployment

```bash
# Health check
curl https://YOUR_BACKEND_URL/meta/health

# Expected: {"ok":true,"database":{"ok":true},...}
```

---

## GitHub Auto-Deploy (Alternative to Manual ECR)

App Runner can auto-deploy from GitHub on every push:
1. In App Runner console → **Source**: GitHub (connect your repo)
2. **Branch**: `main`
3. **Source directory**: `backend` (for backend service)
4. App Runner will use `backend/Dockerfile` automatically
5. Set all env vars in App Runner console

---

## IAM Role for App Runner

App Runner needs an IAM role to pull from ECR:
```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {"Service": "build.apprunner.amazonaws.com"},
    "Action": "sts:AssumeRole"
  }]
}
```
With policy: `AmazonEC2ContainerRegistryReadOnly`

---

## Cost Estimate
- App Runner Backend: ~$25/month (1 vCPU, 2GB RAM)
- App Runner Frontend: ~$18/month (0.25 vCPU, 0.5GB RAM)
- RDS PostgreSQL t3.micro: ~$15/month
- S3 uploads: ~$1/month
- **Total: ~$59/month**
