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
| Notification channels — slack (bot token works) + email | `infra/02_create_channels.sh`; `vcl-drift-alerts-auto` (`type=slack`), `vcl-steward-email-auto` (`type=email`) |
| End-to-end alert delivery — drift → log → policy → **Slack** | P6: real overview drift → `enforce` → `VCL_DRIFT_DETECTED` log (`2026-07-23T19:04:25Z`) → policy → **Slack message received; steward ran the walkthrough re-cert** (user-confirmed). Not rate-limited: first notification after policy creation (`18:25:26Z`). |
| Seal provenance — `sealed_by` (who) + `seal_event_id` (traceable cause) | `src/vcl.py seal` + `schemas/verification_v8_certtext.json` (idx 10–11); round-tripped on the live verification aspect (`sealed_by`, `seal_event_id` populated) |
| Demo agent — verified path delivers, unverified path withholds | `vcl_audience_demo/`; two-run contrast |

## Deferred / not yet proven

- **Scheduled `enforce`.** `enforce` runs manually/locally; it is not on a Cloud Run Job + Cloud Scheduler (Scheduler API not enabled). The alert policy only becomes meaningful once `enforce` runs on a schedule and emits the log regularly. The runner will also need `roles/logging.logWriter` and should export `VCL_STEWARD`.
- **Email delivery not separately confirmed.** The P6 alert targeted both channels and **Slack was confirmed received**; arrival at `vcl-steward-email-auto` was not separately confirmed.
- **`measured_against` divergent case — KNOWN UNTESTED PATH (deliberately not built).** The `measured_against` anchor field supports a quality anchor whose fingerprint is read from a *different* resource than the asset (e.g. the DQ scan runs on the base **table** while the asset is the **view**). This DP seals the quality scan on the same object, so the divergent case is **untested by design** — documented here, not built.
- **Discovery / control plane — SPECIFIED, NOT BUILT.** See [`docs/CONTROL_PLANE_DESIGN.md`](docs/CONTROL_PLANE_DESIGN.md). Why it matters: the **fan-out** case — one source/schema change can drift many anchors across many data products at once, and today there is **no single resolution path** for it (a steward gets *N* per-anchor alerts for one root cause and must re-certify *N* DPs independently). Running at N=1 today hides this. **Implication for existing work (design §7, open question 1):** group-level alerting would have to originate from a **correlation stage** that consumes the per-anchor drift events — *not* per-anchor from `enforce` (giving `enforce` cross-DP awareness would break its deterministic locality, INV-1).
- **IAM-scoped action identity for the demo agent.** Production hardening; tool-scoped today.

## Alerting — primary path and an alternative

- **Primary — Logging → Monitoring:** `enforce` emits `VCL_DRIFT_DETECTED` to `logs/vcl-drift`; the **VCL Drift Detected** policy notifies Slack + email. Its notification documentation carries the Knowledge Catalog SEE url first, then the walkthrough deep link. Proven end-to-end in P6.
- **Alternative (superseded) — Pub/Sub → walkthrough:** `steward/bin/drift_watcher.py` is a local trigger publishing the same walkthrough deep link; superseded by the policy as the notification plane, kept in the repo unchanged.

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
