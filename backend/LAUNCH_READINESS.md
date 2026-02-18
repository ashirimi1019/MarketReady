# Launch Readiness Checklist

## Monitoring
- Use `GET /meta/health` for runtime health checks.
- Track API logs and alert on 5xx spikes.
- Track AI failures and rate-limit events.

## Data Protection
- Run `scripts/db_backup.ps1` daily.
- Keep S3 bucket private and use signed URLs only.
- Rotate API and cloud keys regularly.

## Auth/Security
- Enforce email verification in production.
- Enforce short access token TTL + refresh token rotation.
- Review `auth_audit_logs` periodically for suspicious activity.

## Market Data Pipelines
- Configure provider keys for `adzuna`, `onet`, `careeronestop`.
- Run periodic external ingest and review proposal diffs before publishing.

## Release Gate
- Run `scripts/deploy_check.ps1`.
- Run frontend lint/type checks.
- Validate onboarding, checklist, readiness, and AI guide flows manually.
