# VCL — Status

_Companion to [README.md](README.md); see the repository map there. Updated 2026-07-23._

This is a **reference architecture** on generally-available primitives — a demonstration of
*verification currency* as a platform property, not a shipped product. "Proven" below means
a live round-trip read confirmed it (INV-7), not that a command merely returned success.

## Built and proven

| Capability | Proven by |
|---|---|
| Deterministic verifier — technical/quality/semantic anchors, drift + staleness | `src/vcl.py` seal/check/enforce; live `verified → drift → unverified` round-trips |
| Whole-or-nothing wrapper gate — delivers only when `source_tier=verified` | `src/vcl_wrapper.py` on Cloud Run (`vcl-wrapper`), 3 read-only roles found by live 403 |
| LLM triage — advisory cosmetic vs substantive, never gates | `src/vcl_triage.py` (INV-3) |
| Advisory audit store — separate from the verdict | `audit/` Firestore `vcl-audit` DB; audit doc round-tripped; DB-scoped IAM proven (200 to `vcl-audit`, 403 to a throwaway DB) |
| Governance Drift display aspect — display-only, gate never reads it | `steward/bin/write_drift_aspect.py`; `PENDING_REVIEW`/`RESOLVED` round-tripped |
| Steward re-cert loop | `steward/` walkthroughs + `drift_watcher.py`; browser rehearsal + live `seal && resolve` (`verified` + `RESOLVED`) |
| Structured drift telemetry — one WARNING log per divergence | `vcl.py enforce` → `logs/vcl-drift`; 2 entries round-tripped from Cloud Logging, `freshness_sla_hours` omit rule proven both ways |
| Cloud Monitoring alert policy — log-match, 1h rate limit, slack+email | `infra/03_create_policy.sh`; gate shows `conditionMatchedLog` + `notificationRateLimit.period=3600s` + both channels |
| Notification channels — bot token accepted as `auth_token` at creation | `infra/02_create_channels.sh`; `vcl-drift-alerts-auto` created `type=slack` |
| Demo agent — verified path delivers, unverified path withholds | `vcl_audience_demo/`; two-run contrast |

## Deferred / not yet proven

- **Slack live delivery.** The bot token is *accepted at channel creation*, but whether it actually posts to Slack is untested — there is no gcloud send-test; it needs a firing alert policy or the Console "Send test notification" button.
- **Scheduled `enforce`.** `enforce` runs manually/locally; it is not on a Cloud Run Job + Cloud Scheduler (Scheduler API not enabled). The alert policy only becomes meaningful once `enforce` runs on a schedule and emits the log regularly. The runner will also need `roles/logging.logWriter` and should export `VCL_STEWARD`.
- **Email channel delivery.** `vcl-steward-email-auto` exists (address from env); delivery not verified.
- **Discovery / control plane.** Catalog-scale graph traversal to find related DPs; deferred by design (N=1 today).
- **IAM-scoped action identity for the demo agent.** Production hardening; tool-scoped today.

## Two alerting paths (both fire on the same drift; independent)

1. **Human re-cert (Pub/Sub → walkthrough):** `steward/bin/drift_watcher.py` reads the verdict and publishes a Cloud Shell deep link to the AI-classified walkthrough. Routes a steward to the exact re-cert action.
2. **Ops alert (Logging → Monitoring):** `enforce` emits `VCL_DRIFT_DETECTED` to `logs/vcl-drift`; the **VCL Drift Detected** policy notifies slack + email.

`enforce` is the common trigger. Neither path is the gate — the wrapper reads only the verification aspect.

## Demo run sequence

1. **SEE** — open the Data Product entry in the Console:
   `https://console.cloud.google.com/dataplex/govern/data-products/projects/<project>/locations/us-central1/dataProducts/ecommerce-customer-intelligence?project=<project>`
   → the **Governance Drift** aspect shows `PENDING_REVIEW / [semantic] / cosmetic`; **verification** shows `source_tier=unverified` (VCL is withholding).
2. **Walkthrough** — open the Cloud Shell deep link:
   `https://ssh.cloud.google.com/cloudshell/open?cloudshell_git_repo=<public-repo>&cloudshell_tutorial=steward/walkthrough_cosmetic.md`
   → set the project, then run the re-certify command.
3. **Seal** — the command runs `vcl.py seal` → `source_tier=verified`.
4. **RESOLVED** — the chained `write_drift_aspect.py --resolve` flips the Governance Drift aspect `PENDING_REVIEW → RESOLVED` (display-only; the gate ignores it).
5. **Wrapper delivers** — with `source_tier=verified`, `vcl_wrapper.py` delivers the governed context to agents again.

The substantive branch (`steward/walkthrough_substantive.md`) has **no** seal command by construction: a substantive change cannot be one-click re-certified.
