$ErrorActionPreference = "Stop"

Write-Output "Running backend deploy checks..."

python -m py_compile app/main.py app/api/routes/auth.py app/api/routes/ai.py app/api/routes/market.py app/api/routes/user.py
if ($LASTEXITCODE -ne 0) { throw "Python compile check failed." }

python -m alembic upgrade head
if ($LASTEXITCODE -ne 0) { throw "Migration check failed." }

Write-Output "Deploy checks passed."
