# Validation Matrix

| Claim | Endpoint | Required Field(s) | Validation Method | Screenshot Slot |
|---|---|---|---|---|
| MRI is proprietary and formula-backed | `/user/ai/market-stress-test` | `mri_formula`, `components`, `weights`, `score` | `backend/scripts/hackathon_validate.ps1` checks contract + formula presence | `docs/screenshots/mri_formula.png` |
| MRI survives provider outages | `/user/ai/market-stress-test` | `source_mode`, `snapshot_timestamp`, `snapshot_age_minutes`, `provider_status` | Fallback unit tests + validation script report | `docs/screenshots/mri_snapshot_badge.png` |
| GitHub Proof Auditor verifies real code evidence | `/user/ai/proof-checker` | `match_count`, `verified_by_repo_skills`, `files_checked`, `repos_checked`, `languages_detected` | Contract checks + metadata persistence unit test | `docs/screenshots/proof_verified_badge.png` |
| Pivot logic is deterministic and threshold-driven | `/user/ai/orchestrator` | `pivot_applied`, `pivot_target_role`, `pivot_delta`, `market_alert` | `test_orchestrator_pivot_logic.py` + validation script | `docs/screenshots/pivot_result.png` |
| Mission dashboard is actionable (not generic chat) | `/user/ai/orchestrator` | `mission_dashboard.day_0_30`, `day_31_60`, `day_61_90` | Script asserts non-empty mission tasks | `docs/screenshots/mission_kanban.png` |
| UI exposes live vs snapshot source | Frontend guide/proofs | `source_mode` badges and snapshot freshness text | Manual demo check + report evidence | `docs/screenshots/source_badges.png` |

## Artifact Output
- Automated report: `backend/validation_report.json`
- Command: `powershell backend/scripts/hackathon_validate.ps1`
