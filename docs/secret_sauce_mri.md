# Secret Sauce: Market-Ready Index (MRI)

## Formula
`MRI = (0.40 × Skill Match) + (0.30 × Live Demand) + (0.30 × Proof Density)`

## Components
- `Skill Match (40%)`
  - Source: CareerOneStop skills for target role.
  - Signal: overlap between required role skills and user-verified skills.
- `Live Demand (30%)`
  - Source: Adzuna history/histogram market benchmarks.
  - Signal: vacancy trend score for target role and location.
- `Proof Density (30%)`
  - Source: verified user proofs + GitHub repo verification metadata.
  - Signal: weighted evidence score from verification outcomes.

## Why This Is Non-Generic
- Uses external, role-specific labor data instead of static prompt text.
- Uses federal standards + live demand + repository evidence in one score.
- Includes deterministic fallback mode (`snapshot_fallback`) for demo reliability.
- Exposes component scores and source metadata directly in UI and API.
